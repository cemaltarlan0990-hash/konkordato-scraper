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
    cikti["reviewEsigi"] = REVIEW_ESIGI
    cikti["geriyeDonukGun"] = GERIYE_DONUK_GUN
    cikti["ilanSayisi"] = len(ilanlar)

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
    log("Yazildi: %s" % CIKTI_YOLU)
    return 0


if __name__ == "__main__":
    sys.exit(main())
