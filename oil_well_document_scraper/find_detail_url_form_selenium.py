import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

API_NUMBER = "33-053-02102"

def main():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get("https://www.drillingedge.com/search")

        # C1: API input (exact)
        api_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="api_no"]')))
        api_input.clear()
        api_input.send_keys(API_NUMBER)

        # C2: Search Database submit button (exact)
        submit_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"][value="Search Database"]'))
        )
        submit_btn.click()

        # 等 Search Results 出現（你頁面會有 "Search Results" 文字）
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Search Results')]")))

        # C3: results link — first anchor with /wells/
        result_link = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/wells/"]'))
        )
        href = result_link.get_attribute("href")
        result_link.click()

        # 等跳轉到 well detail page
        wait.until(EC.url_contains("/wells/"))
        time.sleep(0.8)

        print("OK: Found result link:", href)
        print("Final details URL:", driver.current_url)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()