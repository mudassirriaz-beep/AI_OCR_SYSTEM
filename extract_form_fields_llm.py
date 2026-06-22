import json
import re
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EDGE_DRIVER = "msedgedriver.exe"   # make sure this file is in the same folder

def get_form_fields_via_js(driver):
    """Inject JavaScript to extract FB_PUBLIC_LOAD_DATA_"""
    script = """
    // Poll for the variable (max 10 seconds)
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

def parse_fields(data):
    fields = {}
    try:
        pages = data[1][1]
        for page in pages:
            for question in page[1]:
                label = question[1]
                entry_id = question[4][0][0]
                # Remove trailing asterisk (required marker)
                label = re.sub(r'\s*\*$', '', label).strip()
                fields[label] = entry_id
    except Exception as e:
        print(f"Parsing error: {e}")
        return {}
    return fields

def main():
    url = input("Enter Google Form URL: ").strip()
    # Ensure it's a viewform URL
    if "/edit" in url:
        url = url.replace("/edit", "/viewform")
    elif "/d/" in url and "/viewform" not in url:
        # Convert edit link to viewform if necessary
        url = url.rstrip('/') + "/viewform"
    print(f"Opening: {url}")

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Use a fresh profile to avoid caching issues
    options.add_argument("--user-data-dir=C:\\temp\\selenium_edge_profile")
    service = Service(EDGE_DRIVER)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(url)

    print("\n🔐 If the form requires login, please login now in the browser window.")
    input("Then press Enter in this terminal to continue...")

    # Wait for the form to be interactive
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem'], form")))
    time.sleep(2)  # extra buffer for JS to load

    print("Extracting form fields...")
    form_data = get_form_fields_via_js(driver)
    driver.quit()

    if form_data:
        fields = parse_fields(form_data)
        if fields:
            with open("form_fields_final.json", "w") as f:
                json.dump(fields, f, indent=2)
            print(f"\n✅ Successfully extracted {len(fields)} fields.")
            print("Saved to 'form_fields_final.json'")
            print("\n📋 Mapping:")
            for label, entry_id in fields.items():
                print(f"  {label} → {entry_id}")
        else:
            print("❌ Could not parse the form structure.")
    else:
        print("❌ Could not extract FB_PUBLIC_LOAD_DATA_. Make sure you have access to the form (try opening it in your regular browser first).")

if __name__ == "__main__":
    main()