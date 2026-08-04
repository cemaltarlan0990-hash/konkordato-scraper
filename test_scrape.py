import requests
import urllib3
import re
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

# 1. Adım: Liste çek
list_url = "https://www.ilan.gov.tr/api/services/app/Ad/AdsByFilter"
payload = {
    "keys": {"txv": [49]},
    "skipCount": 0,
    "maxResultCount": 5   # test için sadece 5 ilan çekiyoruz
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
    content = detail_response.json()["result"]["content"]

    # 10 haneli vergi no'ları regex ile ara (V.K.N. veya vergi no ibaresi geçen yerlerde)
    vergi_no_list = re.findall(r'\b\d{10}\b', content)

    print(f"İlan ID: {ad_id}")
    print(f"Firma: {advertiser}")
    print(f"Bulunan 10 haneli sayılar: {vergi_no_list}")
    print("-" * 50)
