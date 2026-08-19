"""
Azure App Service giris noktasi.
PA bu endpoint'lere HTTP istegi atar; sonuc dogrudan cevap govdesinde doner,
dosyaya yazilmaz. Boylece eski Do Until / polling zinciri gerekmez.
"""
import os
import sys
import csv
import time
import tempfile
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

CRM_YOLU = os.environ.get(
    "CRM_YOLU", os.path.join(KOK, "data", "crm_referans.csv"))

CRM_SUTUNLARI = ["OrijinalIsim", "DuzenlenmisFirmaAdi", "VKN", "Cari_Kod"]
MIN_CRM_KAYIT = 10000


# --- Anahtar kontrolu ---------------------------------------------------
# Sadece asagidaki yollar kilitli. "/" ve "/teshis" acik kalir ki
# tarayicidan saglik ve dagitim kontrolu yapilabilsin.
KORUMALI_YOLLAR = {"/tara", "/crm-guncelle"}
ANAHTAR_BASLIGI = "X-CRM-Anahtar"


@app.before_request
def anahtar_kontrolu():
    """Korumali yollarda gelen istegin anahtarini dogrular."""
    if request.path not in KORUMALI_YOLLAR:
        return None

    beklenen = os.environ.get("CRM_ANAHTAR", "").strip()
    if not beklenen:
        # Ortam degiskeni tanimli degil -> eski davranis surer.
        return None

    gelen = (request.headers.get(ANAHTAR_BASLIGI) or "").strip()
    if gelen != beklenen:
        print("[guvenlik] Yetkisiz istek: %s" % request.path, flush=True)
        return jsonify({
            "hata": "Yetkisiz istek",
            "mailGonderilsinMi": False,
            "mailKonusu": "",
            "mailHtml": "",
        }), 401

    return None
# ------------------------------------------------------------------------


# --- CRM dosyasi yardimcilari -------------------------------------------

def vkn_duzelt(deger):
    """Bastaki sifirlari geri koyar.

    Dataverse alani sayisal tipteyse JSON'a sifirsiz duser.
    """
    s = str(deger or "").strip()
    if not s:
        return ""
    return s.zfill(10) if len(s) < 10 else s


def kayit_kimligi(satir):
    """Mukerrer olcutu.

    DIKKAT: VKN tek basina YETERLI DEGIL. CRM'de ayni VKN'yi paylasan
    farkli cari kodlu kayitlar var (271 grup / 553 kayit). Sadece VKN'ye
    bakilirsa gercek bir kayit sessizce kaybolur - yanlis negatif.
    Bu yuzden olcut satirin tamami: ad + VKN + cari kod.
    """
    return (
        (satir.get("OrijinalIsim") or "").strip().upper(),
        (satir.get("VKN") or "").strip(),
        (satir.get("Cari_Kod") or "").strip(),
    )


def gelen_kayitlari_cevir(gelenler):
    """PA'nin gonderdigi ham Dataverse kayitlarini CSV satirlarina cevirir.

    DuzenlenmisFirmaAdi BILEREK bos birakilir. O sutun "elle duzeltilmis
    hali" demek; otomatik gelen kayitta karsiligi yok. Isim temizligi
    zaten tarama aninda saf_kelimeler() ile yapiliyor.
    """
    satirlar = []
    for k in gelenler:
        ad = str(k.get("name") or "").strip()
        if not ad:
            continue
        satirlar.append({
            "OrijinalIsim": ad,
            "DuzenlenmisFirmaAdi": "",
            "VKN": vkn_duzelt(k.get("twbs_vergino")),
            "Cari_Kod": str(k.get("twbs_carikodu") or "").strip(),
        })
    return satirlar


def crm_satirlari_oku(yol):
    """Mevcut CRM dosyasini ham sozluk listesi olarak okur."""
    if not os.path.exists(yol):
        return []
    with open(yol, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def crm_atomik_yaz(yol, satirlar):
    """Once gecici dosyaya yazar, sonra yer degistirir.

    POST yarida kesilirse yarim dosya kalmaz; dosya ya tamamen eskisi
    ya tamamen yenisidir. os.replace ayni dosya sisteminde atomiktir,
    bu yuzden gecici dosya hedefle ayni klasorde acilir.
    """
    klasor = os.path.dirname(yol) or "."
    os.makedirs(klasor, exist_ok=True)
    gecici = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="",
        dir=klasor, delete=False, suffix=".tmp")
    try:
        yazici = csv.DictWriter(gecici, fieldnames=CRM_SUTUNLARI)
        yazici.writeheader()
        for s in satirlar:
            yazici.writerow({a: (s.get(a) or "") for a in CRM_SUTUNLARI})
        gecici.flush()
        os.fsync(gecici.fileno())
        gecici.close()
        os.replace(gecici.name, yol)
    except Exception:
        try:
            gecici.close()
        except Exception:
            pass
        if os.path.exists(gecici.name):
            os.remove(gecici.name)
        raise
# ------------------------------------------------------------------------


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
        "anahtarTanimli": bool(os.environ.get("CRM_ANAHTAR", "").strip()),
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


@app.route("/crm-guncelle", methods=["POST"])
def crm_guncelle():
    """PA'nin Dataverse'den cektigi kayitlari CRM dosyasina yazar.

    ?mod=ekle  (varsayilan) - mevcut dosyanin sonuna ekler, mukerreri atlar
    ?mod=tam                - dosyayi bastan yazar (felaket kurtarma)

    Govde: Dataverse kayit dizisi. Ya duz dizi, ya {"value": [...]}.
    Beklenen alanlar: name, twbs_vergino, twbs_carikodu
    """
    baslangic = time.time()

    mod = (request.args.get("mod") or "ekle").strip().lower()
    if mod not in ("ekle", "tam"):
        return jsonify({"hata": "mod 'ekle' veya 'tam' olmali"}), 400

    govde = request.get_json(silent=True)
    if isinstance(govde, dict):
        govde = govde.get("value", govde.get("kayitlar"))
    if not isinstance(govde, list):
        return jsonify({"hata": "Govde bir kayit dizisi olmali"}), 400

    try:
        ham_sayi = len(govde)
        yeni = gelen_kayitlari_cevir(govde)
        gecersiz = ham_sayi - len(yeni)

        if mod == "tam":
            # Bozuk veriyle sessizce devam etmek en tehlikeli senaryo.
            if len(yeni) < MIN_CRM_KAYIT:
                return jsonify({
                    "hata": "Tam modda %d gecerli kayit geldi, esik %d. "
                            "Dosya korundu." % (len(yeni), MIN_CRM_KAYIT),
                    "gelen": ham_sayi,
                    "gecersiz": gecersiz,
                }), 400
            crm_atomik_yaz(CRM_YOLU, yeni)
            sonuc = {
                "mod": "tam",
                "gelen": ham_sayi,
                "gecersiz": gecersiz,
                "eklenen": len(yeni),
                "atlanan": 0,
                "toplam": len(yeni),
            }
        else:
            mevcut = crm_satirlari_oku(CRM_YOLU)
            varolan = {kayit_kimligi(s) for s in mevcut}

            eklenecek = []
            atlanan = 0
            for s in yeni:
                k = kayit_kimligi(s)
                if k in varolan:
                    atlanan += 1
                    continue
                eklenecek.append(s)
                varolan.add(k)

            # Eklenecek yoksa dosyaya hic dokunma.
            if eklenecek:
                crm_atomik_yaz(CRM_YOLU, mevcut + eklenecek)

            sonuc = {
                "mod": "ekle",
                "gelen": ham_sayi,
                "gecersiz": gecersiz,
                "eklenen": len(eklenecek),
                "atlanan": atlanan,
                "toplam": len(mevcut) + len(eklenecek),
            }

    except Exception as hata:
        traceback.print_exc()
        return jsonify({"hata": str(hata)}), 500

    sonuc["dosya"] = CRM_YOLU
    sonuc["boyutBayt"] = (os.path.getsize(CRM_YOLU)
                          if os.path.exists(CRM_YOLU) else 0)
    sonuc["sureSaniye"] = round(time.time() - baslangic, 2)
    print("[crm-guncelle] %s" % sonuc, flush=True)
    return jsonify(sonuc)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
