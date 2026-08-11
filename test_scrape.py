import requests
import urllib3
import re
import json
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------
GERIYE_DONUK_GUN =1      # 0 = sadece bugun, 1 = bugun + dun
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
# METIN TEMIZLEME
# ---------------------------------------------------------------
def clean_html(content):
    text = re.sub(r'&nbsp;', ' ', content or '')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------------------------------------------------------
# VKN DOGRULAMA
# ---------------------------------------------------------------
def gecerli_vkn(vkn):
    """Turkiye vergi kimlik numarasi kontrol hanesi dogrulamasi."""
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


# ---------------------------------------------------------------
# UNVAN CIKARIMI  (VKN'den bagimsiz)
# ---------------------------------------------------------------
HARF = 'A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû'

SIRKET_EKLERI = (
    r'ANONİM\s+ŞİRKETİ|'
    r'LİMİTED\s+ŞİRKETİ|'
    r'KOLLEKTİF\s+ŞİRKETİ|'
    r'KOMANDİT\s+ŞİRKETİ|'
    r'(?<![' + HARF + r'])LTD\.?\s?ŞTİ\.?|'
    r'(?<![' + HARF + r'])A\.?\s?Ş\.?(?![' + HARF + r'])'
)

UNVAN_DESENI = re.compile(
    r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\,&/\-\s]{2,90}?'
    r'(?:' + SIRKET_EKLERI + r'))'
)

# Unvanin baslamasi gereken yeri belirler: bu kaliplardan SONRASI unvandir.
SINIR = re.compile(
    r'.*(?:MAHKEMESİ|MAHKEMESI|HAKİMLİĞİ|BAŞKANLIĞI|MÜDÜRLÜĞÜ|'
    r'DAVACI|DAVALI|BORÇLU|BORCLU|DAVACISI|KOMİSER|KOMISER|'
    r'VERGİ\s*NO(?:LU|SU)?|VERGI\s*NO(?:LU|SU)?|'
    r'İ\s*L\s*A\s*N|ESAS|SAYILI|DOSYA(?:SI)?|'
    r'ALEYHİNE|TARAFINDAN|HAKKINDA|ÜNVANLI|UNVANLI|:)\s*',
    re.IGNORECASE
)

# Sinirdan sonra kalabilecek kucuk harfli baglayici kelimeler
ARTIK = re.compile(r'^(?:[a-zçğıöşü]+\s+)+')

# Unvanin basina yapisabilen cumle baglaclari / kalip kelimeler
CUMLE_BAGLACI = [
    'AYRICA', 'AYNI', 'BUNUN', 'ANCAK', 'YUKARIDA', 'İŞBU', 'ISBU',
    'SÖZ', 'KONU', 'ADRESİ', 'ADRESİNDE', 'MERKEZİ', 'ADLI', 'İSİMLİ',
    'NEZDİNDE', 'TARAFI', 'ŞİRKET', 'FİRMA', 'MÜVEKKİL', 'ALACAKLI', 'ALACAKLISI'
]

# Unvan mutlaka bir sirket eki ile bitmeli
BITIS_KONTROL = re.compile(
    r'(?:ANONİM\s+ŞİRKETİ|LİMİTED\s+ŞİRKETİ|KOLLEKTİF\s+ŞİRKETİ|'
    r'KOMANDİT\s+ŞİRKETİ|LTD\.?\s?ŞTİ\.?|A\.?\s?Ş\.?)$',
    re.IGNORECASE
)

# Unvan sanilabilecek ama sirket olmayan ifadeler
YASAK_KELIMELER = [
    "MAHKEMES", "KOMİSER", "KOMISER", "İCRA", "ICRA",
    "TİCARET SİCİL", "TICARET SICIL", "BAROSU", "NOTER", "MÜDÜRLÜĞÜ",
    "BAKANLIĞI", "BAŞKANLIĞI", "AVUKAT", "HAKİMLİĞİ"
]


def unvan_temizle(unvan):
    """Unvanin basindaki mahkeme adi, taraf sifati gibi ekleri temizler."""
    u = re.sub(r'\s+', ' ', unvan).strip()
    if ',' in u:
        u = u.split(',')[-1].strip()

    # Kucuk harfli " ve " bir ayiractir; buyuk harfli "VE" unvanin parcasidir
    if ' ve ' in u:
        u = u.split(' ve ')[-1].strip()

    m = SINIR.match(u)
    if m:
        u = u[m.end():]

    m2 = ARTIK.match(u)
    if m2:
        u = u[m2.end():]

    # Bastaki sayilari ve cumle baglaclarini tekrarli olarak at
    for _ in range(6):
        onceki = u
        u = re.sub(r'^[\d\.\,\-/:;\s]+', '', u)
        u = re.sub(r'^(?:' + '|'.join(CUMLE_BAGLACI) + r')\s+', '', u,
                   flags=re.IGNORECASE)
        u = re.sub(r'^(?:[a-zçğıöşü]+\s+)+', '', u)
        if u == onceki:
            break

    return u.strip(' .,-:;')


def unvan_uzun_bicim(unvan):
    """Kisaltmalari acik yazima cevirir: A.Ş. -> ANONİM ŞİRKETİ"""
    u = unvan.upper()
    u = re.sub(r'\bLTD\.?\s?ŞTİ\.?', 'LİMİTED ŞİRKETİ', u)
    u = re.sub(r'\bA\.?\s?Ş\.?(?=\s|$)', 'ANONİM ŞİRKETİ', u)
    return re.sub(r'\s+', ' ', u).strip()


def unvan_kisa_bicim(unvan):
    """Acik yazimi kisaltmaya cevirir: ANONİM ŞİRKETİ -> A.Ş."""
    u = unvan.upper()
    u = re.sub(r'\bLİMİTED\s+ŞİRKETİ\b', 'LTD. ŞTİ.', u)
    u = re.sub(r'\bANONİM\s+ŞİRKETİ\b', 'A.Ş.', u)
    u = re.sub(r'\bA\.?\s?Ş\.?(?=\s|$)', 'A.Ş.', u)
    u = re.sub(r'\bLTD\.?\s?ŞTİ\.?(?=\s|$)', 'LTD. ŞTİ.', u)
    return re.sub(r'\s+', ' ', u).strip()


def unvanlari_bul(text):
    """Metindeki tum sirket unvanlarini yakalar (VKN'den bagimsiz)."""
    bulunanlar = []
    for eslesme in UNVAN_DESENI.findall(text):
        unvan = unvan_temizle(eslesme)
        if len(unvan) < 10:
            continue
        if not BITIS_KONTROL.search(unvan):
            continue
        if any(y in unvan.upper() for y in YASAK_KELIMELER):
            continue
        if unvan not in bulunanlar:
            bulunanlar.append(unvan)
    return bulunanlar


# Arama anahtari uretimi: sirket eki ve sektor kelimeleri disarida birakilir
ANAHTAR_DISI = {
    'ANONİM', 'ŞİRKETİ', 'LİMİTED', 'ŞTİ', 'LTD', 'A.Ş', 'AŞ', 'A.O',
    'KOLLEKTİF', 'KOMANDİT', 'SANAYİ', 'SANAYI', 'SAN', 'TİCARET',
    'TICARET', 'TİC', 'VE', 'İLE', 'PAZARLAMA', 'İTHALAT', 'İHRACAT',
    'DIŞ', 'İÇ', 'ALIM', 'SATIM', 'TURİZM', 'İNŞAAT', 'TAAHHÜT',
    'NAKLİYAT', 'LOJİSTİK', 'OTOMOTİV', 'ÜRETİM', 'TASARIM',
    'HİZMETLERİ', 'HİZMET', 'DANIŞMANLIK', 'YATIRIM', 'HOLDİNG',
    'GRUP', 'ORGANİZASYON', 'İŞLETMECİLİĞİ', 'İŞLETMELERİ',
    'MADDELERİ', 'ÜRÜNLERİ', 'MAMULLERİ', 'MALZEMELERİ', 'GEREÇLERİ',
}

HUKUKI_FORM = {'ANONİM', 'ŞİRKETİ', 'LİMİTED', 'ŞTİ', 'LTD',
               'A.Ş', 'AŞ', 'A.O', 'KOLLEKTİF', 'KOMANDİT', 'VE'}


def arama_anahtari(unvan, hedef=2):
    """Unvandan CRM'de aranacak ayirt edici anahtari cikarir.

    CRM'de unvanlar farkli kisaltmalarla yazildigi icin
    (SAN. VE TIC. / SANAYI VE TICARET / TIC. VE SAN.) tam eslesme
    calismaz. Sadece marka kismini alip contains() ile ariyoruz.
    """
    kelimeler = [k.strip('.,;:()') for k in (unvan or '').upper().split()]
    kelimeler = [k for k in kelimeler if k and len(k) > 1]
    ayirt = [k for k in kelimeler if k not in ANAHTAR_DISI]

    if not ayirt:
        return None

    if len(ayirt) >= hedef:
        return ' '.join(ayirt[:hedef])

    # Tek ayirt edici kelime varsa sonrasindaki ilk sektor kelimesini ekle
    tek = ayirt[0]
    try:
        i = kelimeler.index(tek)
    except ValueError:
        return tek if len(tek) >= 4 else None
    for sonraki in kelimeler[i + 1:]:
        if sonraki not in HUKUKI_FORM:
            return tek + ' ' + sonraki
    return tek if len(tek) >= 4 else None


def firma_vkn_ciftleri(text):
    """Unvan ile hemen ardindan gelen VKN'yi birlikte yakalar."""
    pattern = (
        r'([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9\.\,&/\- ]{2,80}?'
        r'(?:' + SIRKET_EKLERI + r'))'
        r'\s*\(?\s*(?:V\.?K\.?N\.?|Vergi\s*Kimlik\s*No|Vergi\s*No)\s*[:.]?\s*(\d{10})\s*\)?'
    )
    ciftler = {}
    for unvan, vkn in re.findall(pattern, text):
        if not gecerli_vkn(vkn):
            continue
        ciftler.setdefault(vkn, unvan_temizle(unvan))
    return ciftler


def serbest_vkn_bul(text, kullanilanlar):
    adaylar = re.findall(r'\b\d{10}\b', text)
    sonuc = []
    for vkn in adaylar:
        if vkn in kullanilanlar or vkn in sonuc:
            continue
        if gecerli_vkn(vkn):
            sonuc.append(vkn)
    return sonuc


# ---------------------------------------------------------------
# DIGER ALANLAR
# ---------------------------------------------------------------
def mahkeme_bul(text):
    temiz = re.sub(r'^\s*İ\s*L\s*A\s*N\s+', '', text)
    pattern = r'([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\.\s]{3,60}?(?:MAHKEMESİ(?:\s+HAKİMLİĞİ)?))'
    m = re.search(pattern, temiz)
    if not m:
        return None
    sonuc = re.sub(r'^(İ\s*L\s*A\s*N\s+)', '', m.group(1)).strip()
    return re.sub(r'\s+', ' ', sonuc)


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
# 1. ADIM - ILAN LISTESI
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

    if sayfada_uygun == 0:
        break

    skip += SAYFA_BOYUTU

print(f"Pencereye giren benzersiz ilan sayisi: {len(secilen_ilanlar)}")


# ---------------------------------------------------------------
# 2. ADIM - DETAYLAR
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

    # VKN'den bagimsiz unvan taramasi
    tum_unvanlar = unvanlari_bul(temiz)
    for u in ciftler.values():
        if u and u not in tum_unvanlar:
            tum_unvanlar.append(u)

    ilan_kayitlari.append({
        "ilanId": str(ilan_id),
        "vergiNolari": vergi_nolari,
        "unvanlar": tum_unvanlar,
        "firmalar": [{"vergiNo": v, "firma": u} for v, u in ciftler.items()],
        "durum": durum_bul(ilan.get("title")),
        "tarih": (ilan.get("publishStartDate") or "")[:10],
        "sehir": ilan.get("addressCityName"),
        "mahkeme": mahkeme_bul(temiz),
        "esasNo": esas_no_bul(ilan.get("adTypeFilters")),
        "link": "https://www.ilan.gov.tr" + (ilan.get("urlStr") or ""),
        "vknBulunamadi": len(vergi_nolari) == 0
    })


# ---------------------------------------------------------------
# 3. ADIM - DUZ LISTELER (Power Automate bunlari kullaniyor)
# ---------------------------------------------------------------
def tekille(liste):
    sonuc = []
    for x in liste:
        if x and x not in sonuc:
            sonuc.append(x)
    return sonuc


tum_vkn = tekille([v for k in ilan_kayitlari for v in k["vergiNolari"]])
ham_unvanlar = tekille([u for k in ilan_kayitlari for u in k["unvanlar"]])

unvanlar_uzun = tekille([unvan_uzun_bicim(u) for u in ham_unvanlar])
unvanlar_kisa = tekille([unvan_kisa_bicim(u) for u in ham_unvanlar])
arama_anahtarlari = tekille([arama_anahtari(u) for u in ham_unvanlar])

vkn_bulunamayan = [k["ilanId"] for k in ilan_kayitlari if k["vknBulunamadi"]]

cikti = {
    "olusturmaTarihi": datetime.now(timezone.utc).isoformat(),
    "tarihAraligi": sorted(tarih_penceresi),
    "ilanSayisi": len(ilan_kayitlari),
    "vergiNolari": tum_vkn,
    "unvanlarUzun": unvanlar_uzun,
    "unvanlarKisa": unvanlar_kisa,
    "aramaAnahtarlari": arama_anahtarlari,
    "vknBulunamayanIlanlar": vkn_bulunamayan,
    "hataliIlanlar": hatali_ilanlar,
    "ilanlar": ilan_kayitlari
}

with open("ilanlar.json", "w", encoding="utf-8") as f:
    json.dump(cikti, f, ensure_ascii=False, indent=2)

print(f"{len(ilan_kayitlari)} ilan yazildi.")
print(f"  Benzersiz VKN   : {len(tum_vkn)}")
print(f"  Benzersiz unvan : {len(ham_unvanlar)}")
print(f"  Arama anahtari  : {len(arama_anahtarlari)}")
if vkn_bulunamayan:
    print(f"  VKN cikarilamayan ilanlar: {vkn_bulunamayan}")
if hatali_ilanlar:
    print(f"  Detayi alinamayan ilanlar: {hatali_ilanlar}")
