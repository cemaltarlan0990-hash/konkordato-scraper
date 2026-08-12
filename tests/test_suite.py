# -*- coding: utf-8 -*-
"""Konkordato boru hatti regresyon testleri."""

import sys
sys.path.insert(0, "src")

import scraper as s
import scraper as s_mod
import matcher as m

BASARILI = 0
BASARISIZ = []


def kontrol(ad, gercek, beklenen):
    global BASARILI
    if gercek == beklenen:
        BASARILI += 1
    else:
        BASARISIZ.append((ad, beklenen, gercek))


def bolum(baslik):
    print("\n" + "=" * 68)
    print(baslik)
    print("=" * 68)


# ---------------------------------------------------------------------------
bolum("1. UNVAN CIKARIMI - yazim bicimleri")

UNVAN_TESTLERI = [
    ("buyuk harf",
     "Borçlu BAREM AMBALAJ SANAYİ VE TİCARET ANONİM ŞİRKETİ hakkında karar",
     "BAREM AMBALAJ SANAYİ VE TİCARET ANONİM ŞİRKETİ"),
    ("baslik format",
     "Denizli Ticaret Sicil Müdürlüğü'nün 53129 sicil numarasında kayıtlı "
     "Fatih Gölcük Halı Ve Mobilya Sanayi Ticaret Anonim Şirketi hakkında",
     "Fatih Gölcük Halı Ve Mobilya Sanayi Ticaret Anonim Şirketi"),
    ("ltd sti kisa",
     "Borçlu ABC YAPI TEKSTİL LTD. ŞTİ. hakkında",
     "ABC YAPI TEKSTİL LTD. ŞTİ"),
    ("a.s. kisa",
     "Borçlu XYZ METAL SANAYİ A.Ş. hakkında",
     "XYZ METAL SANAYİ A.Ş"),
    ("kooperatif",
     "Borçlu YENİ DOĞAN TARIM SATIŞ KOOPERATİFİ hakkında",
     "YENİ DOĞAN TARIM SATIŞ KOOPERATİFİ"),
    ("tescilli sinir",
     "İzmir Ticaret Odasına tescilli Mno Gıda Sanayi Tic. Ltd. Şti. hakkında",
     "Mno Gıda Sanayi Tic. Ltd. Şti"),
    ("bastaki artik harf",
     "Borçlu I ATABAY KİDS TEKSTİL SANAYİ ANONİM ŞİRKETİ hakkında",
     "ATABAY KİDS TEKSTİL SANAYİ ANONİM ŞİRKETİ"),
    ("firma adinda kucuk ve",
     "Borçlu Antalya Sanayi ve Ticaret Anonim Şirketi hakkında",
     "Antalya Sanayi ve Ticaret Anonim Şirketi"),
]

for ad, metin, beklenen in UNVAN_TESTLERI:
    bulunan = s.unvanlari_bul(metin)
    gercek = bulunan[0] if bulunan else None
    kontrol("unvan/" + ad, gercek, beklenen)
    isaret = "OK " if gercek == beklenen else "HATA"
    print("  [%s] %-22s %s" % (isaret, ad, gercek))


# ---------------------------------------------------------------------------
bolum("2. UNVAN REDDI - cop girdiler yakalanmali")

RED_TESTLERI = [
    ("tamamen jenerik", "Ticaret A.Ş"),
    ("jenerik uzun", "Sanayi ve Ticaret Anonim Şirketi"),
    ("mahkeme adi", "İZMİR 1. ASLİYE TİCARET MAHKEMESİ"),
    ("cok kisa", "AB A.Ş."),
]
for ad, metin in RED_TESTLERI:
    gecerli = s.unvan_gecerli_mi(metin)
    kontrol("red/" + ad, gecerli, False)
    print("  [%s] %-22s reddedildi=%s" % ("OK " if not gecerli else "HATA", ad, not gecerli))


# ---------------------------------------------------------------------------
bolum("3. VKN CIFT CIKARIMI - yazim varyantlari")

VKN_TESTLERI = [
    ("VKN: bitisik", "ABC YAPI TEKSTİL LİMİTED ŞİRKETİ (VKN:3852096544) hakkında"),
    ("V.K.N. noktali", "ABC YAPI TEKSTİL LİMİTED ŞİRKETİ V.K.N. 3852096544 hakkında"),
    ("Vergi No bosluk", "ABC YAPI TEKSTİL LİMİTED ŞİRKETİ Vergi No : 3852096544 hakkında"),
    ("Vergi Numarasi", "ABC YAPI TEKSTİL LİMİTED ŞİRKETİ Vergi Numarası: 3852096544"),
    ("koseli parantez", "ABC YAPI TEKSTİL LİMİTED ŞİRKETİ [Vergi No 3852096544]"),
    ("baslik format", "kayıtlı Abc Yapı Tekstil Limited Şirketi (VKN:3852096544) ve"),
]
for ad, metin in VKN_TESTLERI:
    c = s.firma_vkn_ciftleri(metin)
    vkn = c[0]["vergiNo"] if c else None
    kontrol("vkn/" + ad, vkn, "3852096544")
    print("  [%s] %-18s vkn=%s  firma=%s"
          % ("OK " if vkn == "3852096544" else "HATA", ad, vkn,
             c[0]["firma"][:34] if c else "-"))

# gecersiz VKN reddedilmeli
sahte = s.firma_vkn_ciftleri("ABC YAPI TEKSTİL LİMİTED ŞİRKETİ (VKN:1111111111)")
kontrol("vkn/gecersiz kontrol hanesi", sahte, [])
print("  [%s] %-18s gecersiz VKN reddedildi=%s"
      % ("OK " if sahte == [] else "HATA", "kontrol hanesi", sahte == []))


# ---------------------------------------------------------------------------
bolum("4. NORMALIZASYON SIMETRISI - iki taraf ayni cekirdege inmeli")

SIMETRI = [
    ("kisaltma farki", "BAREM AMBALAJ SANAYİ VE TİCARET ANONİM ŞİRKETİ",
     "BAREM AMBALAJ SAN.TİC.A.Ş."),
    ("baslik vs buyuk", "Fatih Gölcük Halı Ve Mobilya Sanayi Ticaret Anonim Şirketi",
     "FATİH GÖLCÜK HALI VE MOBİLYA SAN. TİC. A.Ş."),
    ("turkce vs latin", "AUDUBON BIOSCIENCE MEDIKAL SAGLIK LTD STI",
     "AUDUBON BİOSCIENCE MEDİKAL SAĞLIK LTD ŞTİ"),
    ("A.S. birlestirme", "FLORA FOOD MANAGEMENT ANONİM ŞİRKETİ",
     "FLORA FOOD MANAGEMENT A.Ş."),
    ("bosluksuz kisaltma", "NOVMA KİMYA SANAYİ TİCARET LİMİTED ŞİRKETİ",
     "NOVMA KİMYA SAN.VE TİC.LTD.ŞTİ."),
    ("sube kaydi onek", "BOLAMAN PARK GIDA ÜRÜNLERİ VE TİCARET ANONİM ŞİRKETİ",
     "BOLAMAN PARK GIDA ÜRÜNLERİ VE TİCARET ANONİM ŞİRKETİ"),
]
for ad, ilan, crm in SIMETRI:
    a, b = m.saf_kelimeler(ilan), m.saf_kelimeler(crm)
    kontrol("simetri/" + ad, a, b)
    print("  [%s] %-20s %s" % ("OK " if a == b else "HATA", ad, a))

# FARKLI olmasi gerekenler
FARKLI = [
    ("farkli marka", "KARTAL İNŞAAT SANAYİ LTD ŞTİ", "ASLAN İNŞAAT SANAYİ LTD ŞTİ"),
    ("SAN basta korunmali", "ŞAN TRANSPORT LOJİSTİK LTD ŞTİ", "SANAYİ TRANSPORT LOJİSTİK LTD ŞTİ"),
]
for ad, x, y in FARKLI:
    a, b = m.saf_kelimeler(x), m.saf_kelimeler(y)
    kontrol("farkli/" + ad, a != b, True)
    print("  [%s] %-20s %s  !=  %s" % ("OK " if a != b else "HATA", ad, a, b))


# ---------------------------------------------------------------------------
bolum("5. BOSA DUSME KORUMASI")

for isim in ["SANAYİ VE TİCARET ANONİM ŞİRKETİ", "TİCARET LTD ŞTİ", "A.Ş."]:
    k = m.saf_kelimeler(isim)
    kontrol("bosa/" + isim[:12], len(k) > 0, True)
    print("  [%s] %-34s -> %s" % ("OK " if k else "HATA", isim, k))


# ---------------------------------------------------------------------------
bolum("6. UCTAN UCA - gercek CRM ornegi + gercek ilan metinleri")

CRM = [
    {"OrijinalIsim": "KÜTAHYA HASTANE İŞLETMELERİ YATIRIM A.Ş.",
     "DuzenlenmisFirmaAdi": "KÜTAHYA HASTANE İŞLETMELERİ YATİRİM A.Ş.", "VKN": "6070376789"},
    {"OrijinalIsim": "EPOİF TEKNOLOJİ A.Ş", "DuzenlenmisFirmaAdi": "EPOİF TEKNOLOJİ A.Ş", "VKN": ""},
    {"OrijinalIsim": "ACACİA MADEN İŞLETMELERİ ANONİM ŞİRKETİ",
     "DuzenlenmisFirmaAdi": "ACACİA MADEN İŞLETMELERİ ANONİM ŞTİ.", "VKN": "0910506007"},
    {"OrijinalIsim": "NOVMA KİMYA SANAYİ TİCARET LİMİTED ŞİRKETİ",
     "DuzenlenmisFirmaAdi": "NOVMA KİMYA SANAYİ TİCARET LİMİTED ŞTİ.", "VKN": "6321564061"},
    {"OrijinalIsim": "YORGLASS ENDÜSTRİYEL CAM SANAYİ VE TİCARET ANONİM ŞİRKETİ",
     "DuzenlenmisFirmaAdi": "YORGLASS ENDÜSTRİYEL CAM SANAYİ VE TİCARET ANONİM ŞTİ.", "VKN": "9821092915"},
    {"OrijinalIsim": "FATİH GÖLCÜK HALI VE MOBİLYA SAN. TİC. A.Ş.",
     "DuzenlenmisFirmaAdi": "", "VKN": "3852096544"},
    {"OrijinalIsim": "BAREM AMBALAJ SAN.TİC.A.Ş.", "DuzenlenmisFirmaAdi": "", "VKN": ""},
    {"OrijinalIsim": "TİCARET BAKANLIĞI EGE GÜMRÜK MÜDÜRLÜĞÜ",
     "DuzenlenmisFirmaAdi": "", "VKN": "1460244554"},
]
ref = m.CRMReferans(CRM)
print("  CRM kaydi: %d" % len(ref))

ILAN_METINLERI = [
    ("VKN'li baslik format",
     "Denizli Ticaret Sicil Müdürlüğü'nün 53129 sicil numarasında kayıtlı "
     "Fatih Gölcük Halı Ve Mobilya Sanayi Ticaret Anonim Şirketi (VKN:3852096544) "
     "ve Davacı Fatih Gölcük hakkında geçici mühlet verilmesine"),
    ("VKN'siz buyuk harf",
     "İZMİR 1. ASLİYE TİCARET MAHKEMESİ Borçlu BAREM AMBALAJ SANAYİ VE "
     "TİCARET ANONİM ŞİRKETİ hakkında konkordato talep edilmiştir"),
    ("kisaltma farkli",
     "Borçlu NOVMA KİMYA SAN. VE TİC. LTD. ŞTİ. hakkında"),
    ("CRM'de olmayan",
     "Borçlu ZZZZ OLMAYAN FİRMA TEKSTİL LİMİTED ŞİRKETİ hakkında"),
    ("cop unvan uretmeli mi",
     "Antalya Sanayi ve Ticaret A.Ş hakkında karar verildi"),
]

ilanlar = []
for ad, metin in ILAN_METINLERI:
    firmalar = s.firma_vkn_ciftleri(metin)
    unvanlar = s.unvanlari_bul(metin)
    kullanilan = {f["vergiNo"] for f in firmalar}
    for f in firmalar:
        if f["firma"] and f["firma"] not in unvanlar:
            unvanlar.append(f["firma"])
    ilanlar.append({
        "ilanId": ad, "unvanlar": unvanlar, "firmalar": firmalar,
        "serbestVergiNolari": s.serbest_vkn_bul(metin, kullanilan),
        "tarih": "2026-08-12", "durum": "Geçici Mühlet",
    })
    print("  %-22s unvan=%d vkn_cift=%d" % (ad, len(unvanlar), len(firmalar)))

print()
sonuclar = m.ilanlari_isle(ref, ilanlar)
for r in sonuclar:
    print("  %-22s %-8s %-4s %.2f (%d/%d) -> %s"
          % (r["ilanId"][:22], r["durum"], r["yontem"], r["skor"],
             r["eslesenKelime"], r["toplamKelime"],
             r["adaylar"][0]["crmIsim"][:38] if r["adaylar"] else "-"))

# beklenen sonuclar
durumlar = {}
for r in sonuclar:
    durumlar.setdefault(r["ilanId"], []).append(r["durum"])

kontrol("e2e/VKN'li baslik MATCH", "MATCH" in durumlar.get("VKN'li baslik format", []), True)
kontrol("e2e/VKN'siz buyuk MATCH", "MATCH" in durumlar.get("VKN'siz buyuk harf", []), True)
kontrol("e2e/kisaltma MATCH", "MATCH" in durumlar.get("kisaltma farkli", []), True)
kontrol("e2e/olmayan NO MATCH", durumlar.get("CRM'de olmayan", []) == ["NO MATCH"], True)
kontrol("e2e/cop MATCH uretmemeli",
        "MATCH" not in durumlar.get("cop unvan uretmeli mi", []), True)


# ---------------------------------------------------------------------------
bolum("7. ZOR SENARYOLAR")

# 7a. Ayni ilanda birden fazla firma
metin_coklu = ("Borçlu ACACİA MADEN İŞLETMELERİ ANONİM ŞİRKETİ (VKN:0910506007) "
               "ve BAREM AMBALAJ SANAYİ VE TİCARET ANONİM ŞİRKETİ hakkında")
f = s_mod.firma_vkn_ciftleri(metin_coklu)
u = s_mod.unvanlari_bul(metin_coklu)
for x in f:
    if x["firma"] not in u:
        u.append(x["firma"])
ilan_coklu = [{"ilanId": "COKLU", "unvanlar": u, "firmalar": f,
               "serbestVergiNolari": []}]
sonuc_coklu = m.ilanlari_isle(ref, ilan_coklu)
eslesen = [r for r in sonuc_coklu if r["durum"] == "MATCH"]
kontrol("zor/coklu firma - ikisi de bulunmali", len(eslesen), 2)
print("  [%s] coklu firma: %d unvan, %d MATCH"
      % ("OK " if len(eslesen) == 2 else "HATA", len(u), len(eslesen)))
for r in sonuc_coklu:
    print("        %-9s %-4s %s" % (r["durum"], r["yontem"],
                                    r["adaylar"][0]["crmIsim"][:36] if r["adaylar"] else "-"))

# 7b. CRM mukerrer kayit -> REVIEW olmali, MATCH degil
CRM_MUKERRER = [
    {"OrijinalIsim": "DELTA YAPI SANAYİ VE TİCARET A.Ş.", "DuzenlenmisFirmaAdi": "", "VKN": "1"},
    {"OrijinalIsim": "DELTA YAPI SAN. TİC. LTD. ŞTİ.", "DuzenlenmisFirmaAdi": "", "VKN": "2"},
]
ref_muk = m.CRMReferans(CRM_MUKERRER)
r_muk = m.ilanlari_isle(ref_muk, [{"ilanId": "MUK",
    "unvanlar": ["DELTA YAPI SANAYİ VE TİCARET ANONİM ŞİRKETİ"],
    "firmalar": [], "serbestVergiNolari": []}])[0]
kontrol("zor/mukerrer -> REVIEW", r_muk["durum"], "REVIEW")
print("  [%s] mukerrer kayit: durum=%s skor=%.2f aday=%d"
      % ("OK " if r_muk["durum"] == "REVIEW" else "HATA",
         r_muk["durum"], r_muk["skor"], len(r_muk["adaylar"])))

# 7c. Kismi eslesme - esik uygulamasi
CRM_KISMI = [{"OrijinalIsim": "ASLAN TAAHHÜT YAPI BETON SAN. TİC. A.Ş.",
              "DuzenlenmisFirmaAdi": "", "VKN": "9"}]
ref_k = m.CRMReferans(CRM_KISMI)
for unvan, bek_skor in [("ASLAN TAAHHÜT YAPI BETON ANONİM ŞİRKETİ", 1.0),
                        ("ASLAN TAAHHÜT YAPI DEMİR ANONİM ŞİRKETİ", 0.75),
                        ("ASLAN KIRMIZI MAVİ YEŞİL ANONİM ŞİRKETİ", 0.25)]:
    r = m.ilanlari_isle(ref_k, [{"ilanId": "K", "unvanlar": [unvan],
                                 "firmalar": [], "serbestVergiNolari": []}])[0]
    kontrol("zor/kismi %.2f" % bek_skor, r["skor"], bek_skor)
    print("  [%s] %-42s skor=%.2f (%d/%d) %s"
          % ("OK " if r["skor"] == bek_skor else "HATA", unvan[:40],
             r["skor"], r["eslesenKelime"], r["toplamKelime"], r["durum"]))

# 7d. Bos / bozuk girdiler cokmemeli
for bozuk in ["", "   ", ".", "A", "123456", None]:
    try:
        k = m.saf_kelimeler(bozuk or "")
        kontrol("zor/bozuk girdi %r" % (bozuk,), True, True)
    except Exception as hata:
        kontrol("zor/bozuk girdi %r" % (bozuk,), "COKTU: %s" % hata, True)
print("  [OK ] bos/bozuk girdiler cokmedi")

# 7e. Cift nokta bozuklugu (U+0130 + U+0307)
bozuk_isim = "N\u0130\u0307SAN TEKST\u0130\u0307L SANAY\u0130\u0307 A.\u015e."
temiz_isim = "NİSAN TEKSTİL SANAYİ A.Ş."
kontrol("zor/cift nokta", m.saf_kelimeler(bozuk_isim), m.saf_kelimeler(temiz_isim))
print("  [%s] cift nokta bozuklugu: %s"
      % ("OK " if m.saf_kelimeler(bozuk_isim) == m.saf_kelimeler(temiz_isim) else "HATA",
         m.saf_kelimeler(bozuk_isim)))


# ---------------------------------------------------------------------------
bolum("SONUC")
print("  Basarili : %d" % BASARILI)
print("  Basarisiz: %d" % len(BASARISIZ))
for ad, bek, ger in BASARISIZ:
    print("\n  HATA: %s" % ad)
    print("    beklenen: %r" % (bek,))
    print("    gercek  : %r" % (ger,))

sys.exit(1 if BASARISIZ else 0)
