"""
ilan.gov.tr konkordato ilanlarini ceker.

Eski surumden farklar:
  - Dosyaya yazmiyor, liste donduruyor
  - unvanlar[] ile vergiNolari[] arasinda POZISYONEL ESLEME KURULMUYOR
    (eski kod iki listeyi ters sirada dolduruyordu -> yanlis firmaya
     yanlis VKN atanabiliyordu). Dogru ciftler artik sadece
     firmalar[] icinde tasiniyor.
  - Eski PA contains() mimarisine ait olu kod kaldirildi
    (arama_anahtari, unvanlarUzun/Kisa, ANAHTAR_DISI ...)
"""

import re
import json
import requests
import urllib3
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SAYFA_BOYUTU = 20

# Mutlak guvenlik siniri. Sabit 30 sayfa (600 ilan) tavani, genis
# pencerelerde taramayi SESSIZCE kesiyordu: 90 gunluk tarama ~1100 ilan
# demek, 600'de duruyor ve hicbir uyari vermiyordu.
# Artik dongu tarih toleransiyla kendi kendine duruyor; bu sayi sadece
# sonsuz donguye karsi emniyet supabi.
MAKS_SAYFA = 500

# Liste yeniden eskiye sirali geliyor. Pencereye giren ilan icermeyen
# ardisik sayfa sayisi bunu asarsa pencerenin gerisine gectik demektir.
# Tolerans birakiliyor cunku siralamanin garantisi yok - tek bos sayfada
# durmak, arada tarihi eksik/bozuk kayit varsa erken kesintiye yol acar.
BOS_SAYFA_TOLERANSI = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/"
               "konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr",
}

LISTE_URL = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
DETAY_URL = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"


# ---------------------------------------------------------------------------
# METIN
# ---------------------------------------------------------------------------

def clean_html(content):
    text = re.sub(r"&nbsp;", " ", content or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# VKN
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UNVAN CIKARIMI
# ---------------------------------------------------------------------------

HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû"

SIRKET_EKLERI = (
    r"ANONİM\s+ŞİRKETİ|"
    r"LİMİTED\s+ŞİRKETİ|"
    r"KOLLEKTİF\s+ŞİRKETİ|"
    r"KOMANDİT\s+ŞİRKETİ|"
    r"ADİ\s+ORTAKLIĞI|"
    r"KOOPERATİFİ|"
    r"(?<![" + HARF + r"])LTD\.?\s?ŞTİ\.?|"
    r"(?<![" + HARF + r"])A\.?\s?Ş\.?(?![" + HARF + r"])"
)

# (?i:...) kapsamli bayrak: SADECE sirket eki kismi buyuk/kucuk harf
# duyarsiz olur, bastaki buyuk harf sarti korunur.
# ZORUNLU: ilan metinleri her zaman BUYUK HARF degil. Gercek ornek:
# "Fatih Golcuk Hali Ve Mobilya Sanayi Ticaret Anonim Sirketi (VKN:...)"
# Sadece "ANONİM ŞİRKETİ" arayan desen bunu hic yakalamiyordu -
# baslik formatindaki tum ilanlar sessizce kayboluyordu.
UNVAN_DESENI = re.compile(
    r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\,&/\-\s]{2,90}?"
    r"(?i:" + SIRKET_EKLERI + r"))"
)

SINIR = re.compile(
    r".*(?:MAHKEMESİ|MAHKEMESI|HAKİMLİĞİ|BAŞKANLIĞI|MÜDÜRLÜĞÜ|"
    r"DAVACI|DAVALI|BORÇLU|BORCLU|DAVACISI|KOMİSER|KOMISER|"
    r"VERGİ\s*NO(?:LU|SU)?|VERGI\s*NO(?:LU|SU)?|"
    r"İ\s*L\s*A\s*N|ESAS|SAYILI|DOSYA(?:SI)?|"
    r"ALEYHİNE|TARAFINDAN|HAKKINDA|ÜNVANLI|UNVANLI|"
    # Baslik formatindaki ilanlarda unvan bu kaliplardan SONRA baslar:
    # "... sicil numarasinda kayitli Fatih Golcuk Hali Ve Mobilya A.S."
    # Bunlar olmadan "Denizli Sicilinde kayitli" gibi baglam kelimeleri
    # unvanin basinda kaliyor ve kademeli aramada ilk kelime tutmuyor.
    r"KAYITLI|KAYİTLI|SİCİLİNDE|SICILINDE|SİCİL\s*NUMARASINDA|"
    r"TESCİLLİ|TESCILLI|"
    r":)\s*",
    re.IGNORECASE,
)

ARTIK = re.compile(r"^(?:[a-zçğıöşü]+\s+)+")

CUMLE_BAGLACI = [
    "AYRICA", "AYNI", "BUNUN", "ANCAK", "YUKARIDA", "İŞBU", "ISBU",
    "SÖZ", "KONU", "ADRESİ", "ADRESİNDE", "MERKEZİ", "ADLI", "İSİMLİ",
    "NEZDİNDE", "TARAFI", "ŞİRKET", "FİRMA", "MÜVEKKİL",
    "ALACAKLI", "ALACAKLISI",
]

BITIS_KONTROL = re.compile(
    r"(?:ANONİM\s+ŞİRKETİ|LİMİTED\s+ŞİRKETİ|KOLLEKTİF\s+ŞİRKETİ|"
    r"KOMANDİT\s+ŞİRKETİ|ADİ\s+ORTAKLIĞI|KOOPERATİFİ|"
    r"LTD\.?\s?ŞTİ\.?|A\.?\s?Ş\.?)$",
    re.IGNORECASE,
)

YASAK_KELIMELER = [
    "MAHKEMES", "KOMİSER", "KOMISER", "İCRA", "ICRA",
    "TİCARET SİCİL", "TICARET SICIL", "BAROSU", "NOTER", "MÜDÜRLÜĞÜ",
    "BAKANLIĞI", "BAŞKANLIĞI", "AVUKAT", "HAKİMLİĞİ",
]

# Unvanin basinda kalabilen tek harflik scraping artigi.
# Gercek ornek: "I ATABAY KİDS TEKSTİL ..." -> bastaki I kaldirilmali,
# yoksa kademeli aramada ilk kelime eslesmesi bozulur.
# Kisaltma noktali gelir (A.Ş.), bu yuzden noktasiz tek harf artiktir.
BASTA_TEK_HARF = re.compile(r"^(?:[A-ZÇĞİÖŞÜ](?!\.)\s+){1,2}")


# Hukuki ek ve jenerik kuyruk kelimeleri - "anlamli kelime" sayarken haric
_ANLAMSIZ_HAM = [
    "ANONİM", "ŞİRKETİ", "LİMİTED", "ŞTİ", "LTD", "AŞ",
    "KOLLEKTİF", "KOMANDİT", "ADİ", "ORTAKLIĞI", "KOOPERATİFİ",
    "SANAYİ", "SAN", "TİCARET", "TİC", "VE", "İLE",
    "DIŞ", "İÇ", "İTHALAT", "İHRACAT", "PAZARLAMA",
]


def _sadelestir(metin):
    """
    Karsilastirma icin Turkce karakterleri Latin karsiliklarina indirger.
    ZORUNLU: Python'un upper()'i "Ticaret" -> "TICARET" (Latin I) uretir,
    listedeki "TİCARET" (Turkce İ) ile eslesmez. Gercek veride bu yuzden
    "Ticaret A.S" copu filtreden kacti.
    """
    tablo = {"İ": "I", "ı": "I", "i": "I", "Ş": "S", "ş": "S",
             "Ğ": "G", "ğ": "G", "Ç": "C", "ç": "C",
             "Ö": "O", "ö": "O", "Ü": "U", "ü": "U"}
    metin = "".join(tablo.get(k, k) for k in (metin or ""))
    return metin.upper()


_ANLAMSIZ = {_sadelestir(k) for k in _ANLAMSIZ_HAM}


def _anlamli_kelime_sayisi(metin):
    """Hukuki ek ve jenerik kelimeler disindaki kelime sayisi."""
    sayac = 0
    for k in _sadelestir(metin).replace(".", " ").split():
        k = k.strip(".,;:()")
        if k and k not in _ANLAMSIZ and len(k) > 1:
            sayac += 1
    return sayac


def unvan_temizle(unvan):
    """Unvanin basindaki mahkeme adi, taraf sifati gibi ekleri temizler."""
    u = re.sub(r"\s+", " ", unvan).strip()
    if "," in u:
        u = u.split(",")[-1].strip()

    # Kucuk harfli " ve " genelde ayiractir ("X davaci ve Y A.S.").
    # AMA firma adinin ortasinda da gecebilir ("Sanayi ve Ticaret A.S.").
    # Korumasiz bolme gercek veride "Ticaret A.S" gibi cop uretti.
    # Kural: bolmeden sonra kalan parca, hukuki ek disinda en az 2
    # anlamli kelime icermiyorsa bolme GERI ALINIR.
    if " ve " in u:
        aday = u.split(" ve ")[-1].strip()
        if _anlamli_kelime_sayisi(aday) >= 2:
            u = aday

    m = SINIR.match(u)
    if m:
        u = u[m.end():]

    m2 = ARTIK.match(u)
    if m2:
        u = u[m2.end():]

    for _ in range(6):
        onceki = u
        u = re.sub(r"^[\d\.\,\-/:;\s]+", "", u)
        u = re.sub(r"^(?:" + "|".join(CUMLE_BAGLACI) + r")\s+", "", u,
                   flags=re.IGNORECASE)
        u = re.sub(r"^(?:[a-zçğıöşü]+\s+)+", "", u)
        if u == onceki:
            break

    u = BASTA_TEK_HARF.sub("", u)
    return u.strip(" .,-:;")


def unvan_gecerli_mi(unvan):
    if len(unvan) < 10:
        return False
    # Tamamen jenerik unvan ("Ticaret A.S.") ayirt edici bilgi tasimaz;
    # eslestirmede yuzlerce alakasiz kayitla eslesir.
    if _anlamli_kelime_sayisi(unvan) < 1:
        return False
    if not BITIS_KONTROL.search(unvan):
        return False
    if any(y in unvan.upper() for y in YASAK_KELIMELER):
        return False
    return True


def unvanlari_bul(text):
    """Metindeki tum sirket unvanlarini yakalar (VKN'den bagimsiz)."""
    bulunanlar = []
    for eslesme in UNVAN_DESENI.findall(text):
        unvan = unvan_temizle(eslesme)
        if unvan_gecerli_mi(unvan) and unvan not in bulunanlar:
            bulunanlar.append(unvan)
    return bulunanlar


def firma_vkn_ciftleri(text):
    """
    Unvan ile hemen ardindan gelen VKN'yi BIRLIKTE yakalar.
    Bu, VKN-unvan eslemesinin TEK guvenilir kaynagi.
    """
    desen = (
        r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\,&/\- ]{2,80}?"
        r"(?i:" + SIRKET_EKLERI + r"))"
        r"\s*[\(\[]?\s*"
        r"(?i:V\.?\s?K\.?\s?N\.?|Vergi\s*Kimlik\s*(?:No|Numarasi|Numarası)|"
        r"Vergi\s*(?:No|Numarasi|Numarası))"
        r"\s*[:.\-]?\s*(\d{10})\s*[\)\]]?"
    )
    ciftler = []
    gorulen = set()
    for unvan, vkn in re.findall(desen, text):
        if not gecerli_vkn(vkn) or vkn in gorulen:
            continue
        gorulen.add(vkn)
        ciftler.append({"vergiNo": vkn, "firma": unvan_temizle(unvan)})
    return ciftler


def serbest_vkn_bul(text, kullanilanlar):
    """Metinde gecen ama bir unvana baglanamayan gecerli VKN'ler."""
    sonuc = []
    for vkn in re.findall(r"\b\d{10}\b", text):
        if vkn in kullanilanlar or vkn in sonuc:
            continue
        if gecerli_vkn(vkn):
            sonuc.append(vkn)
    return sonuc


# ---------------------------------------------------------------------------
# DIGER ALANLAR
# ---------------------------------------------------------------------------

def mahkeme_bul(text):
    temiz = re.sub(r"^\s*İ\s*L\s*A\s*N\s+", "", text)
    desen = (r"([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\.\s]{3,60}?"
             r"(?:MAHKEMESİ(?:\s+HAKİMLİĞİ)?))")
    m = re.search(desen, temiz)
    if not m:
        return None
    sonuc = re.sub(r"^(İ\s*L\s*A\s*N\s+)", "", m.group(1)).strip()
    return re.sub(r"\s+", " ", sonuc)


def durum_bul(baslik):
    t = (baslik or "").lower()
    for anahtar, deger in [
        ("geçici mühlet", "Geçici Mühlet"),
        ("kesin mühlet", "Kesin Mühlet"),
        ("tasdik", "Tasdik"),
        ("ret", "Ret"),
        ("duruşma", "Duruşma"),
        ("alacaklı", "Alacaklı Bildirimi"),
    ]:
        if anahtar in t:
            return deger
    return baslik


def esas_no_bul(filtreler):
    for f in (filtreler or []):
        if f.get("key") == "Dosya Numarası":
            return (f.get("value") or "").strip()
    return None


# ---------------------------------------------------------------------------
# ANA FONKSIYON
# ---------------------------------------------------------------------------

def ilan_listesini_al(geriye_donuk_gun):
    """Tarih penceresine giren ilan basliklarini toplar.

    Doner: (secilen_ilanlar, pencere_tarihleri)
    Tavana dayanilirsa RuntimeError firlatir - eksik veriyle "eslesme yok"
    demek, hic calismamaktan daha tehlikeli.
    """
    bugun = datetime.now(timezone.utc).date()
    pencere = {
        (bugun - timedelta(days=i)).isoformat()
        for i in range(geriye_donuk_gun + 1)
    }

    secilen = {}
    skip = 0
    bos_sayfa = 0
    sayfa = 0
    tavana_dayandi = False

    while True:
        if sayfa >= MAKS_SAYFA:
            tavana_dayandi = True
            break
        sayfa += 1

        payload = {"keys": {"txv": [49]}, "skipCount": skip,
                   "maxResultCount": SAYFA_BOYUTU}
        try:
            yanit = requests.post(LISTE_URL, json=payload, headers=HEADERS,
                                  verify=False, timeout=20)
            yanit.raise_for_status()
            ilanlar = yanit.json()["result"]["ads"]
        except Exception as hata:
            # Ilk sayfa alinamiyorsa kaynak erisilemez demektir.
            # Sessizce bos donmek "bugun ilan yok" gibi gorunur ve
            # sistem yesil biter - en tehlikeli hata bicimi.
            if not secilen:
                raise RuntimeError(
                    "ilan.gov.tr liste servisine erisilemedi: %s" % hata)
            print("UYARI: liste sayfasi alinamadi (sayfa %d) -> %s"
                  % (sayfa, hata))
            break

        if not ilanlar:
            break

        uygun = 0
        for ilan in ilanlar:
            if (ilan.get("publishStartDate") or "")[:10] in pencere:
                secilen[ilan["id"]] = ilan
                uygun += 1

        if uygun == 0:
            bos_sayfa += 1
            if bos_sayfa >= BOS_SAYFA_TOLERANSI:
                break
        else:
            bos_sayfa = 0

        skip += SAYFA_BOYUTU

    print("Taranan liste sayfasi: %d (%d ilan gorundu)"
          % (sayfa, skip + SAYFA_BOYUTU if sayfa else 0))

    if tavana_dayandi:
        raise RuntimeError(
            "Sayfa tavanina dayanildi (%d sayfa / ~%d ilan). Pencere %d gun. "
            "Tarama EKSIK olurdu, bu yuzden durduruldu. MAKS_SAYFA artirilmali "
            "ya da pencere daraltilmali."
            % (MAKS_SAYFA, MAKS_SAYFA * SAYFA_BOYUTU, geriye_donuk_gun))

    return secilen, sorted(pencere)


def ilan_detayini_isle(ilan_id, ilan):
    """Tek bir ilanin detayini ceker ve yapiya donusturur."""
    detay = requests.get(DETAY_URL, params={"id": ilan_id}, headers=HEADERS,
                         verify=False, timeout=20)
    detay.raise_for_status()
    temiz = clean_html(detay.json()["result"]["content"])

    firmalar = firma_vkn_ciftleri(temiz)
    kullanilan_vkn = {f["vergiNo"] for f in firmalar}
    serbest = serbest_vkn_bul(temiz, kullanilan_vkn)

    unvanlar = unvanlari_bul(temiz)
    for f in firmalar:
        if f["firma"] and f["firma"] not in unvanlar:
            unvanlar.append(f["firma"])

    return {
        "ilanId": str(ilan_id),
        # DIKKAT: unvanlar ile bagimsiz VKN listesi arasinda
        # pozisyonel esleme YOKTUR. Dogru ciftler firmalar[] icindedir.
        "unvanlar": unvanlar,
        "firmalar": firmalar,
        "serbestVergiNolari": serbest,
        "durum": durum_bul(ilan.get("title")),
        "tarih": (ilan.get("publishStartDate") or "")[:10],
        "sehir": ilan.get("addressCityName"),
        "mahkeme": mahkeme_bul(temiz),
        "esas": esas_no_bul(ilan.get("adTypeFilters")),
        "link": "https://www.ilan.gov.tr" + (ilan.get("urlStr") or ""),
        "vknBulunamadi": len(firmalar) == 0 and len(serbest) == 0,
    }


def ilanlari_cek(geriye_donuk_gun=1):
    """
    Ana giris noktasi.
    Doner: ilan kayitlarindan olusan liste.
    """
    secilen, pencere = ilan_listesini_al(geriye_donuk_gun)
    print("Tarih penceresi: %s" % pencere)
    print("Pencereye giren ilan sayisi: %d" % len(secilen))

    kayitlar = []
    hatali = []
    for ilan_id, ilan in secilen.items():
        try:
            kayitlar.append(ilan_detayini_isle(ilan_id, ilan))
        except Exception as hata:
            print("UYARI: ilan %s detayi alinamadi -> %s" % (ilan_id, hata))
            hatali.append(str(ilan_id))

    if hatali:
        print("Detayi alinamayan ilanlar: %s" % hatali)

    # Ilan bulundu ama HICBIRININ detayi alinamadiysa, bu bir ag/servis
    # arizasidir - "eslesme yok" diye rapor edilmemeli.
    if secilen and not kayitlar:
        raise RuntimeError(
            "%d ilan listelendi ancak hicbirinin detayi alinamadi."
            % len(secilen))

    return kayitlar


if __name__ == "__main__":
    import sys
    gun = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sonuc = ilanlari_cek(gun)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
