# -*- coding: utf-8 -*-
import copy
import rapor

L = "https://www.ilan.gov.tr/ilan/1234567/konkordato"
L2 = "https://www.ilan.gov.tr/ilan/7654321/konkordato"

BARAN_ADAY = {"crmIsim": "BARAN KABLO A.Ş.", "crmVkn": "1410632006",
              "crmCariKodu": ""}


def ilan(unvan="", adaylar=None, link=L, vkn="1410632006"):
    return {
        "unvan": unvan,
        "vkn": vkn,
        "sehir": "KOCAELI",
        "mahkeme": "T .C. GEBZE ASLİYE TİCARET MAHKEMESİ",
        "esas": "",
        "ilanDurumu": "Kesin Mühlet",
        "link": link,
        "adaylar": adaylar if adaylar is not None else [dict(BARAN_ADAY)],
    }


def kutu(vkn=None, isim=None, review=None, ozet=None):
    return {
        "uretimZamani": "2026-08-21T08:15:00",
        "geriyeDonukGun": 1,
        "vknEslesmeleri": vkn or [],
        "isimEslesmeleri": isim or [],
        "incelenecekler": review or [],
        "ozet": ozet or {},
    }


sonuclar = []


def kontrol(ad, kosul, ayrinti=""):
    sonuclar.append((ad, bool(kosul), ayrinti))


def say(c):
    return (len(c["vknEslesmeleri"]), len(c["isimEslesmeleri"]),
            len(c["incelenecekler"]))


# 1) Gercek vaka: BARAN KABLO hem VKN hem isimden bulundu
girdi = kutu(
    vkn=[ilan(unvan="")],
    isim=[ilan(unvan="BARAN KABLO ANONİM ŞİRKETİ")],
    ozet={"match": 2, "review": 0},
)
c = rapor.tekillestir(girdi)
kontrol("1a BARAN tek satira indi", say(c) == (1, 0, 0), str(say(c)))
kontrol("1b unvan VKN satirina tasindi",
        c["vknEslesmeleri"][0]["unvan"] == "BARAN KABLO ANONİM ŞİRKETİ",
        repr(c["vknEslesmeleri"][0]["unvan"]))
kontrol("1c ozet guncellendi", c["ozet"] == {"match": 1, "review": 0},
        str(c["ozet"]))
kontrol("1d girdi degismedi", say(girdi) == (1, 1, 0), str(say(girdi)))

# 2) Ayni ilan, FARKLI CRM kayitlari -> tekrar degil, ikisi de kalmali
diger = {"crmIsim": "BARAN METAL A.Ş.", "crmVkn": "9999999999",
         "crmCariKodu": "120.01"}
c = rapor.tekillestir(kutu(vkn=[ilan(adaylar=[dict(BARAN_ADAY)])],
                           isim=[ilan(adaylar=[diger])]))
kontrol("2 farkli CRM kaydi korundu", say(c) == (1, 1, 0), str(say(c)))

# 3) Ayni CRM kaydi, FARKLI ilan -> ikisi de kalmali
c = rapor.tekillestir(kutu(vkn=[ilan(link=L)], isim=[ilan(link=L2)]))
kontrol("3 farkli ilan korundu", say(c) == (1, 1, 0), str(say(c)))

# 4) VKN kesin + inceleme ayni cifti gosteriyor -> inceleme dusmeli
c = rapor.tekillestir(kutu(vkn=[ilan()], review=[ilan(unvan="BARAN KABLO")]))
kontrol("4 review VKN lehine dustu", say(c) == (1, 0, 0), str(say(c)))

# 5) Inceleme FAZLA aday tasiyorsa dusmemeli (bilgi kaybi olmasin)
c = rapor.tekillestir(kutu(
    vkn=[ilan()],
    review=[ilan(unvan="BARAN KABLO", adaylar=[dict(BARAN_ADAY), diger])],
))
kontrol("5 fazla adayli review korundu", say(c) == (1, 0, 1), str(say(c)))

# 6) Ayni liste icinde tekrar eden satir da tekillesmeli
c = rapor.tekillestir(kutu(isim=[ilan(unvan="BARAN KABLO ANONİM ŞİRKETİ"),
                                 ilan(unvan="BARAN KABLO ANONİM ŞİRKETİ")]))
kontrol("6 liste ici tekrar temizlendi", say(c) == (0, 1, 0), str(say(c)))

# 7) VKN yazim farki (bastaki sifir) ayni kayit sayilmali
a1 = {"crmIsim": "X A.Ş.", "crmVkn": "0123456789", "crmCariKodu": ""}
a2 = {"crmIsim": "X A.Ş.", "crmVkn": "123456789", "crmCariKodu": ""}
c = rapor.tekillestir(kutu(vkn=[ilan(adaylar=[a1])],
                           isim=[ilan(unvan="X ANONİM", adaylar=[a2])]))
kontrol("7 VKN sifir dolgusu esitlendi", say(c) == (1, 0, 0), str(say(c)))

# 8) Link/id yoksa tekillestirme yapilmaz (yanlis birlestirme riski)
y1 = ilan(link="")
y2 = ilan(unvan="BARAN KABLO ANONİM ŞİRKETİ", link="")
c = rapor.tekillestir(kutu(vkn=[y1], isim=[y2]))
kontrol("8 kimliksiz kayit birlestirilmedi", say(c) == (1, 1, 0), str(say(c)))

# 9) Idempotent: iki kez calistirmak ayni sonucu vermeli
bir = rapor.tekillestir(kutu(vkn=[ilan()], isim=[ilan(unvan="BARAN KABLO")]))
iki = rapor.tekillestir(bir)
kontrol("9 idempotent", bir == iki)

# 10) Dolu alan alt satirdan EZILMEMELI
ust = ilan(unvan="DOGRU ÜNVAN")
alt = ilan(unvan="YANLIS ÜNVAN")
c = rapor.tekillestir(kutu(vkn=[ust], isim=[alt]))
kontrol("10 dolu alan korundu",
        c["vknEslesmeleri"][0]["unvan"] == "DOGRU ÜNVAN",
        c["vknEslesmeleri"][0]["unvan"])

# 11) Aday alt alanlari tamamlanmali (cari kod alt satirda dolu)
a_bos = {"crmIsim": "BARAN KABLO A.Ş.", "crmVkn": "1410632006", "crmCariKodu": ""}
a_dolu = {"crmIsim": "BARAN KABLO A.Ş.", "crmVkn": "1410632006",
          "crmCariKodu": "320.05.001"}
c = rapor.tekillestir(kutu(vkn=[ilan(adaylar=[a_bos])],
                           isim=[ilan(unvan="B", adaylar=[a_dolu])]))
kontrol("11 cari kod tasindi",
        c["vknEslesmeleri"][0]["adaylar"][0]["crmCariKodu"] == "320.05.001",
        c["vknEslesmeleri"][0]["adaylar"][0]["crmCariKodu"])

# 12) Bos cikti -> mail yok
kontrol("12 bos ciktida mail yok", rapor.mail_html_uret(kutu()) is None)

# 13) HTML uretimi ve mail konusu tutarli
g = kutu(vkn=[ilan()], isim=[ilan(unvan="BARAN KABLO ANONİM ŞİRKETİ")],
         ozet={"match": 2, "review": 0})
html = rapor.mail_html_uret(g)
kontrol("13a HTML'de isim tablosu yok", "İsimden eşleşenler" not in html)
kontrol("13b HTML'de VKN tablosu var (1)",
        "Vergi numarasından eşleşenler <span" in html and ">(1)<" in html)
kontrol("13c HTML'de unvan gorunuyor", "BARAN KABLO ANONİM ŞİRKETİ" in html)
kontrol("13d konu 1 firma", rapor.mail_konusu(g) ==
        "Konkordato taraması: 1 firma bulundu", rapor.mail_konusu(g))

# 14) Adaysiz kayit cokmemeli
c = rapor.tekillestir(kutu(review=[ilan(adaylar=[])]))
kontrol("14 adaysiz kayit korundu", say(c) == (0, 0, 1), str(say(c)))

# 15) Eksik anahtarlar (None listeler) cokmemeli
c = rapor.tekillestir({"vknEslesmeleri": None, "isimEslesmeleri": None,
                       "incelenecekler": None})
kontrol("15 None listeler tolere edildi", say(c) == (0, 0, 0), str(say(c)))


print("=" * 62)
hata = 0
for ad, ok, ayrinti in sonuclar:
    print(("  OK   " if ok else "  HATA ") + ad + (("   -> " + ayrinti) if (ayrinti and not ok) else ""))
    if not ok:
        hata += 1
print("=" * 62)
print("%d test, %d hata" % (len(sonuclar), hata))
