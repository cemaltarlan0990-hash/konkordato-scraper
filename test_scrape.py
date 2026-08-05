import requests
import urllib3
import re
import json
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------
GERIYE_DONUK_GUN = 0      # bugün + kaç gün geriye bakılsın
SAYFA_BOYUTU = 20
MAKS_SAYFA = 30

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr"
}

LISTE_URL = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
DETAY_URL = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"


# ---------------------------------------------------------------
# YARDIMCI FONKSIYONLAR
# ---------------------------------------------------------------
def clean_html(content):
    text = re.sub(r'&nbsp;', ' ', content or '')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def gecerli_vkn(vkn):
    """Turkiye vergi kimlik numarasi dogrulama algoritmasi.

    10 haneli her sayiyi kabul etmek yerine kontrol hanesini dogrular.
    Boylece telefon numaralari, dosya numaralari ve diger 10 haneli
    sayilar buyuk olcude elenir.
    """
    if not vkn or len(vkn) != 10 or not vkn.isdigit():
        return False
    if vkn == "0000000000":
        return False

    d = [int(c) for c in vkn]
    toplam = 0
    for i in range(9):
        gecici = (d[i] + (9 - i)) % 10
        if gecici == 0:
            continue
        carpim = (gecici * (2 ** (9 - i))) % 9
        if carpim == 0:
            carpim = 9
        toplam += carpim

    return (10 - (toplam % 10)) % 10 == d[9]


def firma_vkn_ciftleri(text):
    """Sirket unvani ile hemen ardindan gelen VKN'yi birlikte yakalar."""
    pattern = (
        r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9\.\,&/\- ]{2,80}?'
        r'(?:A\.Ş\.?|ANONİM ŞİRKETİ|LTD\.?\s?ŞTİ\.?|LİMİTED ŞİRKETİ|'
        r'KOLLEKTİF ŞİRKETİ|KOMANDİT ŞİRKETİ|TAAHHÜT LİMİTED ŞİRKETİ))'
        r'\s*\(?\s*(?:V\.?K\.?N\.?|Vergi\s*Kimlik\s*No|Vergi\s*No)\s*[:.]?\s*(\d{10})\s*\)?'
    )
    ciftler = {}
    for unvan, vkn in re.findall(pattern, text):
        if not gecerli_vkn(vkn):
            continue
        if ',' in unvan:
            unvan = unvan.split(',')[-1]
        ciftler.setdefault(vkn, unvan.strip())
    return ciftler


def serbest_vkn_bul(text, kullanilanlar):
    """Unvanla eslesmeyen, metinde tek basina duran gecerli VKN'ler."""
    adaylar = re.findall(r'\b\d{10}\b', text)
    sonuc = []
    for vkn in adaylar:
        if vkn in kullanilanlar or vkn in sonuc:
            continue
        if gecerli_vkn(vkn):
            sonuc.append(vkn)
    return sonuc


def mahkeme_bul(text):
    pattern = r'([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\.\s]{3,60}?(?:MAHKEMESİ(?:\s+HAKİMLİĞİ)?))'
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def durum_bul(baslik):
    t = (baslik or '').lower()
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
    return baslik


def esas_no_bul(filtreler):
    for f in (filtreler or []):
        if f.get("key") == "Dosya Numarası":
            return (f.get("value") or "").strip()
    return None


# ---------------------------------------------------------------
# 1. ADIM - ILAN LISTESINI TOPLA
# ---------------------------------------------------------------
bugun = datetime.now(timezone.utc).date()
tarih_penceresi = {
    (bugun - timedelta(days=i)).isoformat()
    for i in range(GERIYE_DONUK_GUN + 1)
}
print(f"Tarih penceresi: {sorted(tarih_penceresi)}")

secilen_ilanlar = {}
skip = 0

for sayfa in range(MAKS_SAYFA):
    payload = {"keys": {"txv": [49]}, "skipCount": skip, "maxResultCount": SAYFA_BOYUTU}
    try:
        yanit = requests.post(LISTE_URL, json=payload, headers=headers,
                              verify=False, timeout=20)
        yanit.raise_for_status()
        ilanlar = yanit.json()["result"]["ads"]
    except Exception as e:
        print(f"UYARI: Sayfa {sayfa} alinamadi -> {e}")
        break

    if not ilanlar:
        break

    sayfada_uygun = 0
    for ilan in ilanlar:
        tarih = (ilan.get("publishStartDate") or "")[:10]
        if tarih in tarih_penceresi:
            secilen_ilanlar[ilan["id"]] = ilan
            sayfada_uygun += 1

    # Sayfanin TAMAMI pencere disindaysa artik eskiye gidiyoruz demektir.
    # Tek bir eski ilan gorunce durmuyoruz - eski kodun veri kaybettigi nokta buydu.
    if sayfada_uygun == 0:
        break

    skip += SAYFA_BOYUTU

print(f"Pencereye giren benzersiz ilan sayisi: {len(secilen_ilanlar)}")


# ---------------------------------------------------------------
# 2. ADIM - DETAYLARI CEK, VKN CIKAR
# ---------------------------------------------------------------
ilan_kayitlari = []
hatali_ilanlar = []

for ilan_id, ilan in secilen_ilanlar.items():
    try:
        detay = requests.get(DETAY_URL, params={"id": ilan_id}, headers=headers,
                             verify=False, timeout=20)
        detay.raise_for_status()
        ham_icerik = detay.json()["result"]["content"]
    except Exception as e:
        print(f"UYARI: Ilan {ilan_id} detayi alinamadi -> {e}")
        hatali_ilanlar.append(str(ilan_id))
        continue

    temiz = clean_html(ham_icerik)

    ciftler = firma_vkn_ciftleri(temiz)
    serbest = serbest_vkn_bul(temiz, set(ciftler.keys()))

    vergi_nolari = list(ciftler.keys()) + serbest
    firmalar = [{"vergiNo": v, "firma": u} for v, u in ciftler.items()]

    ilan_kayitlari.append({
        "ilanId": str(ilan_id),
        "vergiNolari": vergi_nolari,
        "firmalar": firmalar,
        "durum": durum_bul(ilan.get("title")),
        "tarih": (ilan.get("publishStartDate") or "")[:10],
        "sehir": ilan.get("addressCityName"),
        "mahkeme": mahkeme_bul(temiz),
        "esasNo": esas_no_bul(ilan.get("adTypeFilters")),
        "link": "https://www.ilan.gov.tr" + (ilan.get("urlStr") or ""),
        "vknBulunamadi": len(vergi_nolari) == 0
    })


# ---------------------------------------------------------------
# 3. ADIM - DUZ VKN LISTESI (Power Automate bunu kullaniyor)
# ---------------------------------------------------------------
tum_vkn = []
for kayit in ilan_kayitlari:
    for v in kayit["vergiNolari"]:
        if v not in tum_vkn:
            tum_vkn.append(v)

vkn_bulunamayan = [k["ilanId"] for k in ilan_kayitlari if k["vknBulunamadi"]]

cikti = {
    "olusturmaTarihi": datetime.now(timezone.utc).isoformat(),
    "tarihAraligi": sorted(tarih_penceresi),
    "ilanSayisi": len(ilan_kayitlari),
    "vergiNolari": tum_vkn,
    "vknBulunamayanIlanlar": vkn_bulunamayan,
    "hataliIlanlar": hatali_ilanlar,
    "ilanlar": ilan_kayitlari
}

with open("ilanlar.json", "w", encoding="utf-8") as f:
    json.dump(cikti, f, ensure_ascii=False, indent=2)

print(f"{len(ilan_kayitlari)} ilan, {len(tum_vkn)} benzersiz VKN yazildi.")
if vkn_bulunamayan:
    print(f"VKN cikarilamayan ilanlar: {vkn_bulunamayan}")
if hatali_ilanlar:
    print(f"Detayi alinamayan ilanlar: {hatali_ilanlar}")
