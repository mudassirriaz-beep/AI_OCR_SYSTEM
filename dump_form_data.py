import json
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EDGE_DRIVER = "msedgedriver.exe"

def get_fb_data(driver):
    script = """
    let attempts = 0;
    const maxAttempts = 20;
    const intervalMs = 500;
    return new Promise((resolve) => {
        const check = setInterval(() => {
            if (typeof FB_PUBLIC_LOAD_DATA_ !== 'undefined') {
                clearInterval(check);
                resolve(JSON.stringify(FB_PUBLIC_LOAD_DATA_));
            } else if (attempts >= maxAttempts) {
                clearInterval(check);
                resolve(null);
            }
            attempts++;
        }, intervalMs);
    });
    """
    raw = driver.execute_script(script)
    if raw:
        return json.loads(raw)
    return None

def main():
    url = input("Enter Google Form URL: ").strip()
    if "/edit" in url:
        url = url.replace("/edit", "/viewform")
    print(f"Opening: {url}")

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-data-dir=C:\\temp\\selenium_edge_profile")
    service = Service(EDGE_DRIVER)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(url)

    print("\n🔐 If login required, please login now in the browser window.")
    input("Then press Enter to continue...")

    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem'], form")))
    time.sleep(2)

    print("Extracting raw form data...")
    fb_data = get_fb_data(driver)
    driver.quit()

    if fb_data:
        with open("raw_form_data.json", "w") as f:
            json.dump(fb_data, f, indent=2)
        print("✅ Raw data saved to 'raw_form_data.json'")
        print("Open this file and look for 'entry.' IDs and question texts.")
    else:
        print("❌ Could not extract data. Make sure you have access to the form.")

if __name__ == "__main__":
    main()