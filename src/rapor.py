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
"""

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
    ("vkn", "VKN"),
    ("sehir", "Şehir"),
    ("mahkeme", "Mahkeme"),
    ("esas", "Esas no"),
    ("ilanDurumu", "Durum"),
    ("link", "İlan"),
]


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
    ozet = cikti.get("ozet") or {}
    toplam = (ozet.get("match", 0) + ozet.get("review", 0))
    return "Konkordato taraması: %d firma bulundu" % toplam
