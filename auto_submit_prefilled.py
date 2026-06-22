import json
import urllib.parse
import time
import os
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from brain_format import extract_cnic_info

def clean_path(path):
    """Remove surrounding quotes, spaces, and any trailing parenthesis."""
    path = path.strip()
    # Remove enclosing quotes
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    # Remove trailing ) if present (common copy-paste mistake)
    if path.endswith(')'):
        path = path[:-1]
    return path

def load_mapping(mapping_file="form_fields_final.json"):
    with open(mapping_file, "r") as f:
        return json.load(f)

def main():
    while True:
        raw_path = input("Enter document image path: ").strip()
        image_path = clean_path(raw_path)
        print(f"Using image path: {image_path}")
        if os.path.exists(image_path):
            break
        else:
            print(f"❌ File not found: {image_path}")
            print("Please enter a valid path (without quotes or trailing parentheses).")
    
    extracted = extract_cnic_info(image_path)
    if "error" in extracted:
        print("❌ Extraction failed:", extracted["error"])
        return

    print("\n✅ Extracted data:")
    for k, v in extracted.items():
        print(f"   {k}: {v}")

    mapping = load_mapping()
    doc_to_label = {
        "Full_Name": "Name",
        "Father_Name": "F.name",
        "Gender": "Gender",
        "Identity_Number": "Identity no",
        "DOB": "Date of birth",
        "Date_of_Issue": "Date of issue",
        "Date_of_Expiry": "Date  expiry"
    }

    params = {}
    for doc_key, value in extracted.items():
        if doc_key in doc_to_label:
            label = doc_to_label[doc_key]
            if label in mapping:
                params[mapping[label]] = value

    if "Country" in mapping and mapping["Country"] not in params:
        params[mapping["Country"]] = "Pakistan"

    form_base = "https://docs.google.com/forms/d/e/1FAIpQLSeunqDGmQdawFZqpMBmCOIqYhBDr9OhV0ftDJMrjBy1nBEyhQ/viewform"
    query = urllib.parse.urlencode(params)
    prefilled_url = f"{form_base}?{query}"
    print("\n🔗 Pre-filled URL generated.")

    # ---- Automate submission using Selenium ----
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    profile_dir = os.path.join(os.getcwd(), "selenium_edge_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    service = Service("msedgedriver.exe")
    driver = webdriver.Edge(service=service, options=options)

    try:
        driver.get(prefilled_url)
        print("⏳ Waiting for form to load...")
        submit_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button']//span[text()='Submit']"))
        )
        submit_btn.click()
        print("✅ Submit button clicked.")
        time.sleep(3)
        if "Your response has been recorded" in driver.page_source:
            print("🎉 Form submitted successfully!")
        else:
            print("⚠️ Form submitted, but confirmation not found. Check browser.")
        input("Press Enter to close browser...")
    except Exception as e:
        print(f"❌ Submission failed: {e}")
        print("You can still manually submit using the pre-filled link:")
        print(prefilled_url)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()