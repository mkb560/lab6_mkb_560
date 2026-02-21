import re
import time
import random
import csv
import requests
from bs4 import BeautifulSoup
import mysql.connector

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

BASE = "https://www.drillingedge.com"
SEARCH_URL = BASE + "/search"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"

FAIL_CSV = "scrape_failures.csv"

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def parse_details_with_requests(detail_url: str) -> dict:
    headers = {"User-Agent": UA}
    r = requests.get(detail_url, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    def grab(pattern, default="N/A"):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        return clean(m.group(1)) if m else default

    well_status = grab(r"Well Status\s+([A-Za-z /\-]+)")
    well_type = grab(r"Well Type\s+([A-Za-z &/\-]+)")
    closest_city = grab(r"Closest City\s+([A-Za-z \-'.]+)")

    oil_prod = grab(r"(\d[\d,]*)\s+Barrels of Oil Produced.*", default="N/A")
    gas_prod = grab(r"(\d[\d,]*)\s+MCF of Gas Produced.*", default="N/A")

    scraped_oil = "N/A" if oil_prod == "N/A" else f"{oil_prod} BBL"
    scraped_gas = "N/A" if gas_prod == "N/A" else f"{gas_prod} MCF"

    return {
        "scraped_well_status": well_status,
        "scraped_well_type": well_type,
        "scraped_closest_city": closest_city,
        "scraped_oil_production": scraped_oil,
        "scraped_gas_production": scraped_gas,
    }

def get_detail_url_with_selenium(driver, api_no: str) -> str:
    driver.get(SEARCH_URL)
    wait = WebDriverWait(driver, 25)

    api_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="api_no"]')))
    api_input.clear()
    api_input.send_keys(api_no)

    submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"][value="Search Database"]')))
    submit_btn.click()

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Search Results')]")))
    result_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/wells/"]')))
    result_link.click()

    wait.until(EC.url_contains("/wells/"))
    time.sleep(0.6)
    return driver.current_url

def is_filled(row: dict) -> bool:
    keys = [
        "scraped_well_status",
        "scraped_well_type",
        "scraped_closest_city",
        "scraped_oil_production",
        "scraped_gas_production",
    ]

    def ok(v):
        if v is None:
            return False
        s = str(v).strip()
        if s == "":
            return False
        if s.upper() == "N/A":
            return False
        return True

    return all(ok(row.get(k)) for k in keys)

def main():
    conn = mysql.connector.connect(
        host="localhost", port=3306, user="root", password="", database="oil_wells_db"
    )
    cur = conn.cursor(dictionary=True)

    
    cur.execute(
        """
        SELECT well_file_no, api_number, well_name,
               scraped_well_status, scraped_well_type, scraped_closest_city,
               scraped_oil_production, scraped_gas_production
        FROM well_info
        WHERE api_number IS NOT NULL
            AND api_number <> ''
            AND UPPER(api_number) <> 'N/A'
        ORDER BY well_file_no
        """
    )
    wells = cur.fetchall()
    total = len(wells)
    print(f"Loaded wells with API: {total}")

    # selenium driver
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={UA}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    failures = []
    updated_count = 0
    skipped = 0

    try:
        for idx, w in enumerate(wells, 1):
            well_file_no = w["well_file_no"]
            api_no = w["api_number"]

            if is_filled(w):
                skipped += 1
                continue

            # polite delay
            time.sleep(random.uniform(0.7, 1.6))

            print(f"[{idx}/{total}] well_file_no={well_file_no} api={api_no}")

            ok = False
            last_err = ""
            detail_url = ""

            for attempt in range(1, 3 + 1):  # retry up to 3 attempts
                try:
                    detail_url = get_detail_url_with_selenium(driver, api_no)
                    data = parse_details_with_requests(detail_url)

                    cur2 = conn.cursor()
                    cur2.execute(
                        """
                        UPDATE well_info SET
                            scraped_well_status=%s,
                            scraped_well_type=%s,
                            scraped_closest_city=%s,
                            scraped_oil_production=%s,
                            scraped_gas_production=%s
                        WHERE well_file_no=%s
                        """,
                        (
                            data["scraped_well_status"],
                            data["scraped_well_type"],
                            data["scraped_closest_city"],
                            data["scraped_oil_production"],
                            data["scraped_gas_production"],
                            well_file_no,
                        ),
                    )
                    cur2.close()
                    updated_count += 1  
                    ok = True
                    break
                except Exception as e:
                    last_err = str(e)
                    # backoff
                    time.sleep(1.5 * attempt)

            if not ok:
                failures.append({
                    "well_file_no": well_file_no,
                    "api_number": api_no,
                    "detail_url": detail_url,
                    "error": last_err[:300],
                })

        conn.commit()

    finally:
        driver.quit()
        cur.close()
        conn.close()

    # write failures
    if failures:
        with open(FAIL_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["well_file_no", "api_number", "detail_url", "error"])
            writer.writeheader()
            writer.writerows(failures)

    print("\n=== SUMMARY ===")
    print("Total with API:", total)
    print("Skipped (already filled):", skipped)
    print("Processed successfully:", updated_count)
    print("Failures:", len(failures))
    if failures:
        print(f"Failure details saved to: {FAIL_CSV}")

if __name__ == "__main__":
    main()