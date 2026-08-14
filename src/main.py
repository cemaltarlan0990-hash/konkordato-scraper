"""
Konkordato tarama - ana calistirici.

Akis:
  1. CRM referansini oku ve dogrula
  2. ilan.gov.tr'den ilanlari cek
  3. Eslestir
  4. eslesmeler.json yaz

GitHub Actions bu dosyayi calistirir.
"""

import os
import sys
import json
from datetime import datetime, timezone

import matcher
import rapor
from scraper import ilanlari_cek


# ---------------------------------------------------------------------------
# AYARLAR (ortam degiskeniyle ezilebilir)
# ---------------------------------------------------------------------------

CRM_YOLU = os.environ.get("CRM_YOLU", "data/crm_referans.csv")
CIKTI_YOLU = os.environ.get("CIKTI_YOLU", "cikti/eslesmeler.json")
GERIYE_DONUK_GUN = int(os.environ.get("GERIYE_DONUK_GUN", "1"))

# REVIEW esigi: bunun altindaki kismi eslesmeler NO MATCH sayilir.
# 0.75 -> 3/4 ve ustu girer, 2/3 (0.667) girmez.
REVIEW_ESIGI = float(os.environ.get("REVIEW_ESIGI", "0.75"))


def log(mesaj):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), mesaj), flush=True)


def esik_uygula(sonuclar, esik):
    """
    Tam olmayan eslesmeleri esige gore eler.
    Tam eslesmeler (N/N) esikten etkilenmez.
    """
    for s in sonuclar:
        if s["durum"] != "REVIEW":
            continue
        tam = (s["toplamKelime"] > 0
               and s["eslesenKelime"] == s["toplamKelime"])
        if not tam and s["skor"] < esik:
            s["durum"] = "NO MATCH"
            s["adaylar"] = []
    return sonuclar


def main():
    log("CRM referansi okunuyor: %s" % CRM_YOLU)
    if not os.path.exists(CRM_YOLU):
        log("HATA: CRM referans dosyasi bulunamadi.")
        return 1

    try:
        referans = matcher.CRMReferans(matcher.crm_oku(CRM_YOLU))
        referans.dogrula()
    except ValueError as hata:
        # Bozuk/eksik referansla sessizce devam etmek en tehlikeli senaryo:
        # sistem "bugun eslesme yok" der, sen hicbir sey fark etmezsin.
        log("HATA: %s" % hata)
        return 1

    log("%d CRM kaydi yuklendi (katlama=%s)"
        % (len(referans), matcher.KATLAMA))

    # Cari kod ikincil bir alandir: okunamazsa eslestirme yine dogru calisir,
    # sadece mailde tire gorunur. Bu yuzden calismayi DURDURMAZ - durdurmak
    # konkordato uyarisinin hic gitmemesine yol acardi ki bu daha kotu.
    # Ama sessiz de kalmaz: sutun adi degisirse Actions log'unda gorunur.
    cari_dolu = referans.cari_kod_sayisi()
    if cari_dolu == 0:
        log("UYARI: Hicbir cari kod okunamadi. CRM dosyasindaki sutun adi "
            "degismis olabilir. Beklenen adlar: %s"
            % ", ".join(matcher.CARI_KOD_ANAHTARLARI))
    else:
        log("%d kayitta cari kod dolu (%d kayitta bos)"
            % (cari_dolu, len(referans) - cari_dolu))

    log("Ilanlar cekiliyor (son %d gun)" % GERIYE_DONUK_GUN)
    try:
        ilanlar = ilanlari_cek(GERIYE_DONUK_GUN)
    except Exception as hata:
        log("HATA: ilan cekme basarisiz: %s" % hata)
        return 1

    log("%d ilan alindi" % len(ilanlar))

    if not ilanlar:
        log("Ilan yok, bos cikti yaziliyor.")

    sonuclar = matcher.ilanlari_isle(referans, ilanlar)
    sonuclar = esik_uygula(sonuclar, REVIEW_ESIGI)
    log("%d unvan islendi" % len(sonuclar))

    cikti = matcher.cikti_uret(sonuclar, crm_kayit_sayisi=len(referans))
    cikti["teshis"] = matcher.teshis_uret(ilanlar, referans)

    # DIKKAT: bu alanlar mail uretiminden ONCE atanmali - rapor.py
    # tarih satirinda geriyeDonukGun'u kullaniyor.
    cikti["reviewEsigi"] = REVIEW_ESIGI
    cikti["geriyeDonukGun"] = GERIYE_DONUK_GUN
    cikti["ilanSayisi"] = len(ilanlar)

    # Mail govdesi burada uretilir; PA sadece hazir HTML'i basar.
    # Sonuc yoksa mailHtml bos kalir ve mailGonderilsinMi=false olur.
    mail_html = rapor.mail_html_uret(cikti)
    cikti["mailGonderilsinMi"] = mail_html is not None
    cikti["mailKonusu"] = rapor.mail_konusu(cikti) if mail_html else ""
    cikti["mailHtml"] = mail_html or ""

    os.makedirs(os.path.dirname(CIKTI_YOLU) or ".", exist_ok=True)
    with open(CIKTI_YOLU, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)

    ozet = cikti["ozet"]
    log("MATCH: %d | REVIEW: %d | NO MATCH: %d"
        % (ozet["match"], ozet["review"], ozet["noMatch"]))
    t = cikti["teshis"]
    log("Teshis: VKN cifti=%d | serbest VKN=%d | CRM'de bulunan=%d | "
        "unvansiz ilan=%d | CRM VKN dolu=%d bos=%d"
        % (t["ilandanCikarilanVknCifti"], t["ilandanCikarilanSerbestVkn"],
           t["crmdeBulunanVkn"], t["unvaniCikarilamayanIlan"],
           t["crmVknDoluKayit"], t["crmVknBosKayit"]))
    log("Cari kod: CRM'de dolu=%d bos=%d | mailde gosterilen=%d"
        % (t["crmCariKoduDoluKayit"], t["crmCariKoduBosKayit"],
           _mailde_cari_kod_sayisi(cikti)))
    log("Mail gonderilsin mi: %s" % cikti["mailGonderilsinMi"])
    log("Yazildi: %s" % CIKTI_YOLU)
    return 0


def _mailde_cari_kod_sayisi(cikti):
    """Maile giren satirlardan kacinda cari kod dolu - log icin."""
    sayac = 0
    for anahtar in ("vknEslesmeleri", "isimEslesmeleri", "incelenecekler"):
        for s in cikti.get(anahtar) or []:
            aday = (s.get("adaylar") or [{}])[0]
            if (aday.get("crmCariKodu") or "").strip():
                sayac += 1
    return sayac


if __name__ == "__main__":
    sys.exit(main())
