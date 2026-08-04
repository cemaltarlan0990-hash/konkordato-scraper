import requests
import urllib3
import re
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr"
}

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
print(f"Bugünün tarihi (UTC): {today_str}\n")

list_url = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
page_size = 20
skip = 0
today_ads = []
max_pages = 20  # güvenlik freni: sonsuz döngüyü önlemek için

for page in range(max_pages):
    payload = {
        "keys": {"txv": [49]},
        "skipCount": skip,
        "maxResultCount": page_size
    }

    response = requests.post(list_url, json=payload, headers=headers, verify=False, timeout=15)
    response.raise_for_status()
    ads = response.json()["result"]["ads"]

    if not ads:
        print("Liste tükendi, daha fazla ilan yok.")
        break

    reached_older_date = False
    for ad in ads:
        if ad["publishStartDate"].startswith(today_str):
            today_ads.append(ad)
        else:
            reached_older_date = True
            break  # bu sayfada bugünden eski bir ilana rastladık, döngüyü kes

    print(f"Sayfa {page + 1} tarandı (skip={skip}), bu sayfada bugüne ait {sum(1 for a in ads if a['publishStartDate'].startswith(today_str))} ilan bulundu.")

    if reached_older_date:
        break

    skip += page_size

print(f"\nToplam bugüne ait ilan sayısı: {len(today_ads)}\n")

if not today_ads:
    print("Bugün için yeni ilan bulunamadı.")
else:
    detail_url = "https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail"

    for ad in today_ads:
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
