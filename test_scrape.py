import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.ilan.gov.tr/ilan/kategori/49/konkordato-ve-muhlet-iik-288inci-md-",
    "Origin": "https://www.ilan.gov.tr"
}

list_url = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
payload = {
    "keys": {"txv": [49]},
    "skipCount": 0,
    "maxResultCount": 5
}

response = requests.post(list_url, json=payload, headers=headers, verify=False, timeout=15)

print("Status code:", response.status_code)
print("Response headers:", dict(response.headers))
print("İlk 1000 karakter (ham cevap):")
print(response.text[:1000])
