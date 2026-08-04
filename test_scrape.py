import requests
import urllib3
import re
import json
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr"
}

def clean_html(content):
    text = re.sub(r'&nbsp;', ' ', content)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_company_tax_pairs(text):
    pattern = (
        r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9\.\,&/\- ]{2,80}?'
        r'(?:A\.Ş\.?|ANONİM ŞİRKETİ|LTD\.?\s?ŞTİ\.?|LİMİTED ŞİRKETİ|KOLLEKTİF ŞİRKETİ|KOMANDİT ŞİRKETİ|TAAHHÜT LİMİTED ŞİRKETİ))'
        r'\s*\(?\s*(?:V\.?K\.?N\.?|Vergi\s*Kimlik\s*No|Vergi\s*No)\s*[:.]?\s*(\d{10})\s*\)?'
    )
    matches = re.findall(pattern, text)
    pairs = []
    for company, tax_no in matches:
        if ',' in company:
            company = company.split(',')[-1]
        pairs.append({"firma": company.strip(), "vergiNo": tax_no})
    return pairs

def extract_standalone_tax_numbers(text, used_numbers):
    all_numbers = re.findall(r'\b\d{10}\b', text)
    return [n for n in all_numbers if n not in used_numbers]

def extract_mahkeme(raw_content):
    pattern = r'([A-ZÇĞİÖŞÜ0-9İ][A-ZÇĞİÖŞÜ0-9\.\s]{3,60}?(?:MAHKEMESİ(?:\s+HAKİMLİĞİ)?))'
    match = re.search(pattern, raw_content)
    return match.group(1).strip() if match else None

def infer_durum(title):
    t = title.lower()
    if "geçici mühlet" in t:
        return "Geçici Mühlet"
    if "kesin mühlet" in t:
        return "Kesin Mühlet"
    if "tasdik" in t:
        return "Tasdik"
    if "ret" in t:
        return "Ret"
    if "duruşma" in t:
        return "Duruşma"
    if "alacaklı" in t:
        return "Alacaklı Bildirimi"
    return title

def get_esas_no(ad_type_filters):
    for f in (ad_type_filters or []):
        if f.get("key") == "Dosya Numarası":
            return f.get("value", "").strip()
    return None

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
print(f"Bugünün tarihi (UTC): {today_str}")

list_url = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
page_size = 20
skip = 0
today_ads = []
max_pages = 20

for page in range(max_pages):
    payload = {"keys": {"txv": [49]}, "skipCount": skip, "maxResultCount": page_size}
    response = requests.post(list_url, json=payload, headers=headers, verify=False, timeout=15)
    response.raise_for_status()
    ads = response.json()["result"]["ads"]

    if not ads:
        break

    reached_older_date = False
    for ad in ads:
        if ad["publishStartDate"].startswith(today_str):
            today_ads.append(ad)
        else:
            reached_older_date = True
            break

    if reached_older_date:
        break
    skip += page_size

print(f"Bugüne ait ilan sayısı: {len(today_ads)}")

detail_url = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"
all_records = []

for ad in today_ads:
    ad_id = ad["id"]
    detail_response = requests.get(detail_url, params={"id": ad_id}, headers=headers, verify=False, timeout=15)
    detail_response.raise_for_status()
    raw_content = detail_response.json()["result"]["content"]
    clean_content = clean_html(raw_content)

    pairs = extract_company_tax_pairs(clean_content)
    used_numbers = {p["vergiNo"] for p in pairs}
    leftover_numbers = extract_standalone_tax_numbers(clean_content, used_numbers)

    link = "https://www.ilan.gov.tr" + ad["urlStr"]
    durum = infer_durum(ad["title"])
    esas_no = get_esas_no(ad.get("adTypeFilters"))
    tarih = ad["publishStartDate"][:10]
    sehir = ad["addressCityName"]
    mahkeme = extract_mahkeme(raw_content)

    for p in pairs:
        all_records.append({
            "ilanId": ad_id, "vergiNo": p["vergiNo"], "firma": p["firma"],
            "durum": durum, "tarih": tarih, "sehir": sehir,
            "mahkeme": mahkeme, "esasNo": esas_no, "link": link
        })

    for n in leftover_numbers:
        all_records.append({
            "ilanId": ad_id, "vergiNo": n, "firma": None,
            "durum": durum, "tarih": tarih, "sehir": sehir,
            "mahkeme": mahkeme, "esasNo": esas_no, "link": link
        })

output = {"olusturmaTarihi": datetime.now(timezone.utc).isoformat(), "ilanlar": all_records}

with open("ilanlar.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Toplam {len(all_records)} kayıt ilanlar.json dosyasına yazıldı.")
