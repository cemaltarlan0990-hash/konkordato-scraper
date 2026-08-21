# -*- coding: utf-8 -*-
"""
eslesmeler.json -> e-posta HTML govdesi.

Tasarim kararlari:
  - Sonuc yoksa HTML uretilmez, mail gonderilmez.
  - Teshis/istatistik bilgisi maile girmez; sadece bulunan firmalar.
  - Tablo tabanli, satir ici stilli HTML. Outlook flexbox/grid
    desteklemez; e-posta istemcileri icin tablo tek guvenli yapidir.
  - CRM tarafinda OrijinalIsim gosterilir - personel CRM'de bu isimle
    arama yapar, duzeltilmis isimle kaydi bulamaz.
  - Ayni ilan + ayni CRM kaydi birden fazla asamada bulunabilir
    (once VKN, sonra isim). Rapor asamasinda tekillestirilir; ust
    kademe satiri korunur, alt kademedeki dolu alanlar ust satira
    tasinir. Bkz. tekillestir().
"""

import copy
import unicodedata
from html import escape


RENK = {
    "vkn": "#0F6E56",
    "isim": "#185FA5",
    "review": "#854F0B",
    "cizgi": "#D3D1C7",
    "baslik_zemin": "#F1EFE8",
    "metin": "#2C2C2A",
    "soluk": "#5F5E5A",
}

SUTUNLAR = [
    ("unvan", "İlandaki ünvan"),
    ("crmIsim", "CRM kaydı"),
    ("cariKodu", "Cari kodu"),
    ("vkn", "VKN"),
    ("sehir", "Şehir"),
    ("mahkeme", "Mahkeme"),
    ("esas", "Esas no"),
    ("ilanDurumu", "Durum"),
    ("link", "İlan"),
]

# Kademe sirasi: ustteki kazanir. VKN en guclu kanit.
KADEMELER = ["vknEslesmeleri", "isimEslesmeleri", "incelenecekler"]

# Tekillestirmede alt satirdan ust satira tasinabilecek ilan alanlari.
TASINIR_ALANLAR = [
    "unvan", "vkn", "sehir", "mahkeme", "esas", "ilanDurumu", "link",
]

# Aday (CRM kaydi) icinde tasinabilecek alanlar.
TASINIR_ADAY_ALANLARI = ["crmIsim", "crmVkn", "crmCariKodu"]


# ----------------------------------------------------------------------
# Tekillestirme
# ----------------------------------------------------------------------

def _bos_mu(deger):
    return deger is None or str(deger).strip() == ""


def _norm(deger):
    """
    Kimlik karsilastirmasi icin normalizasyon:
    NFC + cift nokta temizligi (U+0130 U+0307 -> U+0130) + Turkce
    buyuk harf + bosluk sadelestirme. Iki taraf ayni CRM alanindan
    gelse de kodlama farki olusabiliyor.
    """
    metin = unicodedata.normalize("NFC", str(deger or ""))
    metin = metin.replace("\u0130\u0307", "\u0130")
    metin = metin.replace("i", "\u0130").replace("\u0131", "I")
    return " ".join(metin.upper().split())


def _vkn_kimlik(deger):
    """Sadece rakamlar, 10 haneye tamamlanir. Bastaki sifir kaybi telafisi."""
    rakam = "".join(ch for ch in str(deger or "") if ch.isdigit())
    return rakam.zfill(10) if rakam else ""


def _ayni_crm_kaydi(a, b):
    """
    Iki adayin ayni CRM kaydi olup olmadigi.

    OrijinalIsim esitligi sarttir - VKN tek basina benzersiz degil
    (553 kayit VKN paylasiyor). VKN ve Cari_Kod ise ancak IKI TARAFTA
    DA doluysa karsilastirilir; bir tarafta bos olmasi celiski degil,
    eksik bilgidir.
    """
    isim_a, isim_b = _norm(a.get("crmIsim")), _norm(b.get("crmIsim"))
    if not isim_a or isim_a != isim_b:
        return False
    for alan, normalize in (("crmVkn", _vkn_kimlik), ("crmCariKodu", _norm)):
        x, y = normalize(a.get(alan)), normalize(b.get(alan))
        if x and y and x != y:
            return False
    return True


def _kapsiyor_mu(ust_kayit, alt_kayit):
    """Alt kaydin TUM adaylari ust kayitta zaten var mi?"""
    ust_adaylar = ust_kayit.get("adaylar") or []
    alt_adaylar = alt_kayit.get("adaylar") or []
    if not alt_adaylar or not ust_adaylar:
        return False
    return all(
        any(_ayni_crm_kaydi(alt, ust) for ust in ust_adaylar)
        for alt in alt_adaylar
    )


def _ilan_kimlik(kayit):
    """
    Ilan kimligi. Guvenilir bir kimlik yoksa None doner ve kayit
    tekillestirmeye sokulmaz - yanlis birlestirme, tekrar eden
    satirdan daha zararlidir.
    """
    for alan in ("ilanId", "ilanid", "id", "link"):
        deger = kayit.get(alan)
        if not _bos_mu(deger):
            return str(deger).strip()
    return None


def _bosluklari_doldur(hedef, kaynak):
    """Hedefte bos olan alanlari kaynaktan tamamlar. Dolu alan ezilmez."""
    for alan in TASINIR_ALANLAR:
        if _bos_mu(hedef.get(alan)) and not _bos_mu(kaynak.get(alan)):
            hedef[alan] = kaynak[alan]

    kaynak_adaylar = kaynak.get("adaylar") or []
    for hedef_aday in hedef.get("adaylar") or []:
        for kaynak_aday in kaynak_adaylar:
            if not _ayni_crm_kaydi(hedef_aday, kaynak_aday):
                continue
            for alan in TASINIR_ADAY_ALANLARI:
                if _bos_mu(hedef_aday.get(alan)) and not _bos_mu(kaynak_aday.get(alan)):
                    hedef_aday[alan] = kaynak_aday[alan]
            break


def tekillestir(cikti):
    """
    Ayni ilan + ayni CRM kaydi ciftini tek satira indirir.

    Kural:
      - Kademe onceligi VKN > isim > inceleme. Ust kademe satiri kalir.
      - Alt kademe satiri, ancak tum adaylari ust kademe satirinda
        zaten varsa dusurulur. Fazladan aday tasiyorsa yerinde kalir -
        bilgi kaybi olmaz.
      - Dusurulen satirin dolu alanlari kalan satirdaki bos alanlara
        tasinir (ornek: VKN satirinda bos olan 'İlandaki ünvan').
      - Ayni ilanin farkli CRM kayitlariyla eslesmesi tekrar degildir,
        her ikisi de korunur.

    Girdi degistirilmez; yeni bir cikti sozlugu doner. Idempotenttir.
    """
    sonuc = dict(cikti)
    gorulenler = {}   # ilan kimligi -> [(aday kimlik kumesi, kayit)]

    for kademe in KADEMELER:
        korunan = []
        for kayit in cikti.get(kademe) or []:
            ilan_id = _ilan_kimlik(kayit)

            if ilan_id is None or not (kayit.get("adaylar") or []):
                korunan.append(copy.deepcopy(kayit))
                continue

            onceki = None
            for mevcut in gorulenler.get(ilan_id, []):
                if _kapsiyor_mu(mevcut, kayit):
                    onceki = mevcut
                    break

            if onceki is not None:
                _bosluklari_doldur(onceki, kayit)
                continue

            yeni = copy.deepcopy(kayit)
            korunan.append(yeni)
            gorulenler.setdefault(ilan_id, []).append(yeni)

        sonuc[kademe] = korunan

    ozet = dict(cikti.get("ozet") or {})
    ozet["match"] = len(sonuc["vknEslesmeleri"]) + len(sonuc["isimEslesmeleri"])
    ozet["review"] = len(sonuc["incelenecekler"])
    sonuc["ozet"] = ozet

    return sonuc


# ----------------------------------------------------------------------
# HTML uretimi
# ----------------------------------------------------------------------

def _g(deger):
    """Bos/None degerleri tire ile gosterir, HTML kacisi uygular."""
    if deger is None or str(deger).strip() == "":
        return "&ndash;"
    return escape(str(deger).strip())


def _satir_hucreleri(kayit):
    aday = (kayit.get("adaylar") or [{}])[0]

    crm_isim = aday.get("crmIsim") or ""
    vkn = kayit.get("vkn") or aday.get("crmVkn") or ""

    # Birden fazla aday varsa personelin bilmesi gerekir
    aday_sayisi = len(kayit.get("adaylar") or [])
    if aday_sayisi > 1:
        crm_isim = "%s <span style=\"color:%s\">(+%d benzer kayıt)</span>" % (
            escape(crm_isim), RENK["soluk"], aday_sayisi - 1)
    else:
        crm_isim = _g(crm_isim)

    link = kayit.get("link") or ""
    link_hucre = (
        '<a href="%s" style="color:%s">Görüntüle</a>' % (escape(link), RENK["isim"])
        if link else "&ndash;"
    )

    return [
        _g(kayit.get("unvan")),
        crm_isim,
        _g(aday.get("crmCariKodu")),
        _g(vkn),
        _g(kayit.get("sehir")),
        _g(kayit.get("mahkeme")),
        _g(kayit.get("esas")),
        _g(kayit.get("ilanDurumu")),
        link_hucre,
    ]


def _tablo(baslik, kayitlar, renk, aciklama=None):
    if not kayitlar:
        return ""

    parcalar = [
        '<h3 style="font-family:Arial,sans-serif;font-size:15px;'
        'font-weight:600;color:%s;margin:26px 0 4px 0">%s '
        '<span style="font-weight:400;color:%s">(%d)</span></h3>'
        % (renk, escape(baslik), RENK["soluk"], len(kayitlar))
    ]

    if aciklama:
        parcalar.append(
            '<p style="font-family:Arial,sans-serif;font-size:12px;'
            'color:%s;margin:0 0 8px 0">%s</p>' % (RENK["soluk"], escape(aciklama))
        )

    parcalar.append(
        '<table cellpadding="7" cellspacing="0" border="0" '
        'style="border-collapse:collapse;width:100%%;'
        'font-family:Arial,sans-serif;font-size:12px;color:%s;'
        'border-top:2px solid %s">' % (RENK["metin"], renk)
    )

    parcalar.append('<tr style="background:%s">' % RENK["baslik_zemin"])
    for _, etiket in SUTUNLAR:
        parcalar.append(
            '<th align="left" style="border-bottom:1px solid %s;'
            'font-weight:600;white-space:nowrap">%s</th>'
            % (RENK["cizgi"], escape(etiket))
        )
    parcalar.append("</tr>")

    for i, kayit in enumerate(kayitlar):
        zemin = "#FFFFFF" if i % 2 == 0 else "#FAFAF8"
        parcalar.append('<tr style="background:%s">' % zemin)
        for hucre in _satir_hucreleri(kayit):
            parcalar.append(
                '<td style="border-bottom:1px solid %s;vertical-align:top">%s</td>'
                % (RENK["cizgi"], hucre)
            )
        parcalar.append("</tr>")

    parcalar.append("</table>")
    return "".join(parcalar)


def mail_html_uret(cikti):
    """
    Doner: HTML metni, veya sonuc yoksa None.
    None donerse mail gonderilmemelidir.
    """
    cikti = tekillestir(cikti)

    vkn_list = cikti.get("vknEslesmeleri") or []
    isim_list = cikti.get("isimEslesmeleri") or []
    review_list = cikti.get("incelenecekler") or []

    if not (vkn_list or isim_list or review_list):
        return None

    govde = [
        '<div style="font-family:Arial,sans-serif;color:%s;max-width:1000px">'
        % RENK["metin"],
        '<h2 style="font-size:17px;font-weight:600;margin:0 0 2px 0">'
        'Konkordato ilan taraması</h2>',
        '<p style="font-size:12px;color:%s;margin:0">%s</p>'
        % (RENK["soluk"], escape(_tarih_metni(cikti))),
    ]

    govde.append(_tablo(
        "Vergi numarasından eşleşenler", vkn_list, RENK["vkn"]))
    govde.append(_tablo(
        "İsimden eşleşenler", isim_list, RENK["isim"]))
    govde.append(_tablo(
        "İncelenecekler", review_list, RENK["review"],
        "Tam eşleşme sağlanamadı veya birden fazla aday bulundu."))

    govde.append("</div>")
    return "".join(p for p in govde if p)


def _tarih_metni(cikti):
    zaman = (cikti.get("uretimZamani") or "")[:16].replace("T", " ")
    gun = cikti.get("geriyeDonukGun")
    if gun is None:
        return zaman
    kapsam = "bugün" if gun == 0 else "son %d gün" % (gun + 1)
    return "%s · %s taranan ilanlar" % (zaman, kapsam)


def mail_konusu(cikti):
    ozet = tekillestir(cikti).get("ozet") or {}
    toplam = (ozet.get("match", 0) + ozet.get("review", 0))
    return "Konkordato taraması: %d firma bulundu" % toplam
