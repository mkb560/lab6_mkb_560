import re
import requests
from bs4 import BeautifulSoup

DETAIL_URL = "https://www.drillingedge.com/north-dakota/mckenzie-county/wells/basic-game-and-fish-34-3/33-053-02102"

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    }
    r = requests.get(DETAIL_URL, headers=headers, timeout=30)
    print("Status:", r.status_code)
    print("Final URL:", r.url)
    print("Len:", len(r.text))

    if r.status_code != 200:
        print("Failed to fetch page.")
        return

    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n", strip=True)

    
    def grab(pattern, default="N/A"):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        return clean(m.group(1)) if m else default

    well_status = grab(r"Well Status\s+([A-Za-z /\-]+)")
    well_type   = grab(r"Well Type\s+([A-Za-z &/\-]+)")
    closest_city = grab(r"Closest City\s+([A-Za-z \-'.]+)")

    
    oil_prod = grab(r"(\d[\d,]*)\s+Barrels of Oil Produced.*", default="N/A")
    gas_prod = grab(r"(\d[\d,]*)\s+MCF of Gas Produced.*", default="N/A")

    
    scraped_oil_production = "N/A" if oil_prod == "N/A" else f"{oil_prod} BBL"
    scraped_gas_production = "N/A" if gas_prod == "N/A" else f"{gas_prod} MCF"

    result = {
        "scraped_well_status": well_status,
        "scraped_well_type": well_type,
        "scraped_closest_city": closest_city,
        "scraped_oil_production": scraped_oil_production,
        "scraped_gas_production": scraped_gas_production,
    }

    print("\n--- SCRAPED ---")
    for k, v in result.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()