"""
Azure App Service giris noktasi.

PA bu endpoint'lere HTTP istegi atar; sonuc dogrudan cevap govdesinde doner,
dosyaya yazilmaz. Boylece eski Do Until / polling zinciri gerekmez.
"""

import os
import sys
import time
import traceback
from datetime import datetime, timezone

from flask import Flask, jsonify, request

# src/ klasorunu import yoluna ekle - main.py "import matcher" diyor,
# yani src icinden calisiyormus gibi davranmali.
KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KOK, "src"))

# DIKKAT: duz "import main" baska bir main modulunu bulabiliyor.
# Dosyayi yolundan dogrudan yukluyoruz - hangi dosyanin calistigi kesin.
import importlib.util  # noqa: E402

MAIN_YOLU = os.path.join(KOK, "src", "main.py")
_spec = importlib.util.spec_from_file_location("konkordato_main", MAIN_YOLU)
tarayici = importlib.util.module_from_spec(_spec)
sys.modules["konkordato_main"] = tarayici
_spec.loader.exec_module(tarayici)

app = Flask(__name__)

CRM_YOLU = os.environ.get("CRM_YOLU", os.path.join(KOK, "data", "crm_referans.csv"))


@app.route("/")
def saglik():
    """Uygulama ayakta mi, CRM dosyasi yerinde mi."""
    var = os.path.exists(CRM_YOLU)
    return jsonify({
        "durum": "calisiyor",
        "zaman": datetime.now(timezone.utc).isoformat(),
        "crmDosyasi": CRM_YOLU,
        "crmDosyasiVar": var,
        "crmBoyutBayt": os.path.getsize(CRM_YOLU) if var else 0,
    })


@app.route("/teshis")
def teshis():
    """Hangi dosyalarin yuklendigini gosterir - dagitim dogrulamasi icin."""
    return jsonify({
        "kok": KOK,
        "mainYolu": MAIN_YOLU,
        "mainVar": os.path.exists(MAIN_YOLU),
        "taramaYapVar": hasattr(tarayici, "tarama_yap"),
        "mainFonksiyonlari": sorted(
            a for a in dir(tarayici) if not a.startswith("_")
        ),
        "kokDosyalari": sorted(os.listdir(KOK)),
        "srcDosyalari": sorted(os.listdir(os.path.join(KOK, "src")))
        if os.path.isdir(os.path.join(KOK, "src")) else [],
    })


@app.route("/tara")
def tara():
    """
    Tarama + eslestirme. PA'nin kullandigi 3 alani doner.

    ?gun=N  ile geriye donuk pencere degistirilebilir (varsayilan: 1).
    ?tam=1  ile teshis dahil tam cikti doner (elle inceleme icin).
    """
    baslangic = time.time()
    try:
        gun = int(request.args.get("gun", "1"))
    except ValueError:
        return jsonify({"hata": "gun sayisal olmali"}), 400

    try:
        cikti = tarayici.tarama_yap(crm_yolu=CRM_YOLU, geriye_donuk_gun=gun)
    except Exception as hata:
        # Sessiz basarisizlik yok: PA 500 gorursa uyari maili atabilir.
        traceback.print_exc()
        return jsonify({
            "hata": str(hata),
            "mailGonderilsinMi": False,
            "mailKonusu": "",
            "mailHtml": "",
        }), 500

    sure = round(time.time() - baslangic, 1)
    print("[tara] %s sn surdu, %d ilan" % (sure, cikti.get("ilanSayisi", 0)),
          flush=True)

    if request.args.get("tam") == "1":
        cikti["sureSaniye"] = sure
        return jsonify(cikti)

    return jsonify({
        "mailGonderilsinMi": cikti["mailGonderilsinMi"],
        "mailKonusu": cikti["mailKonusu"],
        "mailHtml": cikti["mailHtml"],
        "sureSaniye": sure,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
