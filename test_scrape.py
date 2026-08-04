import requests
import urllib3
import re
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
    """HTML etiketlerini ve &nbsp; gibi entity'leri temizler"""
    text = re.sub(r'&nbsp;', ' ', content)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_tax_numbers(text):
    """10 haneli vergi no adaylarını çıkarır (birincil eşleştirme yöntemi)"""
    return re.findall(r'\b\d{10}\b', text)

def extract_company_names(text):
    """Firma unvanı adaylarını çıkarır (vergi no bulunamayan durumlar için yedek yöntem)"""
    pattern = r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9\.\,&/\- ]{2,80}?(?:A\.Ş\.?|ANONİM ŞİRKETİ|LTD\.?\s?ŞTİ\.?|LİMİTED ŞİRKETİ|KOLLEKTİF ŞİRKETİ|KOMANDİT ŞİRKETİ|TAAHHÜT LİMİTED ŞİRKETİ))'
    matches = re.findall(pattern, text)
    cleaned = []
    for m in matches:
        if ',' in m:
            m = m.split(',')[-1]
        cleaned.append(m.strip())
    return list(set(cleaned))

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
print(f"Bugünün tarihi (UTC): {today_str}\n")

list_url = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
page_size = 20
skip = 0
today_ads = []
max_pages = 20

for page in range(max_pages):
    payload = {
        "keys": {"txv": [49]},
        "skipCount": skip,
        "maxResultCount": page_size
    }

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

print(f"Toplam bugüne ait ilan sayısı: {len(today_ads)}\n")

if not today_ads:
    print("Bugün için yeni ilan bulunamadı.")
else:
    detail_url = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"

    for ad in today_ads:
        ad_id = ad["id"]
        advertiser = ad["advertiserName"]

        detail_response = requests.get(detail_url, params={"id": ad_id}, headers=headers, verify=False, timeout=15)
        detail_response.raise_for_status()
        raw_content = detail_response.json()["result"]["content"]
        clean_content = clean_html(raw_content)

        tax_numbers = extract_tax_numbers(clean_content)
        company_names = extract_company_names(clean_content)

        print(f"İlan ID: {ad_id}")
        print(f"Advertiser (ham): {advertiser}")
        print(f"Vergi No Adayları: {tax_numbers}")
        print(f"Firma Adı Adayları: {company_names}")
        print("-" * 50)
