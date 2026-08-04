import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=15, verify=False)
    print("Status code:", response.status_code)
    print("Content length:", len(response.text))
    print("İlk 500 karakter:")
    print(response.text[:500])
except Exception as e:
    print("HATA:", e)
