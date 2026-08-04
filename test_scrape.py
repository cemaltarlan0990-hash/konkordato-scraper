import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr"
}

# 1. Adım: Liste çek (düzeltilmiş URL: /api/api/)
list_url = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
payload = {
    "keys": {"txv": [49]},
    "skipCount": 0,
    "maxResultCount": 5
}

list_response = requests.post(list_url, json=payload, headers=headers, verify=False, timeout=15)
ads = list_response.json()["result"]["ads"]

print(f"Toplam {len(ads)} ilan bulundu.\n")

# 2. Adım: Her ilan için detay çek ve vergi no ara
detail_url = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"

for ad in ads:
    ad_id = ad["id"]
    advertiser = ad["advertiserName"]

    detail_response = requests.get(detail_url, params={"id": ad_id}, headers=headers, verify=False, timeout=15)
    detail_response.raise_for_status()
    content = detail_response.json()["result"]["content"]

    vergi_no_list = re.findall(r'\b\d{10}\b', content)

    print(f"İlan ID: {ad_id}")
    print(f"Firma: {advertiser}")
    print(f"Bulunan 10 haneli sayılar: {vergi_no_list}")
    print("-" * 50)
