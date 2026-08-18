from flask import Flask, jsonify, request
from datetime import datetime, timezone

app = Flask(__name__)

# Bellekte tutulan sahte "CRM verisi". Gercekte bu Blob Storage'dan okunacak.
crm_kayitlari = []


@app.route("/")
def saglik():
    """Uygulamanin ayakta oldugunu gormek icin. Tarayicidan acilir."""
    return jsonify({
        "durum": "calisiyor",
        "zaman": datetime.now(timezone.utc).isoformat(),
        "crmKayitSayisi": len(crm_kayitlari)
    })


@app.route("/crm-guncelle", methods=["POST"])
def crm_guncelle():
    """PA buraya ham CRM kayitlarini POST eder. Azure temizler ve saklar."""
    gelen = request.get_json(silent=True) or {}
    kayitlar = gelen.get("kayitlar", [])

    temiz = []
    for k in kayitlar:
        isim = (k.get("name") or "").strip()
        vkn = (k.get("twbs_vergino") or "").strip()
        if not isim:
            continue
        temiz.append({"isim": isim, "vkn": vkn.zfill(10) if vkn else ""})

    crm_kayitlari.clear()
    crm_kayitlari.extend(temiz)

    return jsonify({"alinan": len(kayitlar), "kaydedilen": len(temiz)})


@app.route("/tara")
def tara():
    """PA buraya GET atar. Cevabi dogrudan JSON olarak alir, dosya yok."""
    # Gercekte: scraper.py calisir, matcher.py eslestirir.
    # Simdilik sahte bir eslesme uretiyoruz.
    eslesmeler = [{"ilanFirma": "ORNEK GIDA SAN TIC AS", "crmFirma": "ORNEK GIDA"}]

    if not eslesmeler:
        return jsonify({
            "mailGonderilsinMi": False,
            "mailKonusu": "",
            "mailHtml": ""
        })

    satirlar = "".join(
        f"<tr><td>{e['ilanFirma']}</td><td>{e['crmFirma']}</td></tr>"
        for e in eslesmeler
    )
    html = f"<table border='1'><tr><th>Ilan</th><th>CRM</th></tr>{satirlar}</table>"

    return jsonify({
        "mailGonderilsinMi": True,
        "mailKonusu": f"Konkordato: {len(eslesmeler)} eslesme",
        "mailHtml": html
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
