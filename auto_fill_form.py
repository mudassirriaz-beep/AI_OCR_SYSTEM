import json
import re
import requests
import time
import os
from brain_format import extract_cnic_info
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== Helper Functions ==========
def extract_form_id_from_url(url_or_id):
    if re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
        return url_or_id
    match = re.search(r'/e/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    match = re.search(r'/d/e/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    return url_or_id

def clean_path(path):
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    return path

def load_form_mapping(mapping_file="form_fields_final.json"):
    with open(mapping_file, "r") as f:
        return json.load(f)

def clean_date(date_str):
    # Replace common OCR errors
    month_fixes = {
        "Oec": "Dec", "Jpn": "Jan", "Fab": "Feb", "Mch": "Mar", "Aprl": "Apr",
        "Mey": "May", "Jun": "Jun", "Jul": "Jul", "Aug": "Aug", "Sep": "Sep",
        "Oct": "Oct", "Nov": "Nov", "Dec": "Dec"
    }
    for wrong, correct in month_fixes.items():
        date_str = date_str.replace(wrong, correct)
    # Convert from DD.Mon.YYYY to YYYY-MM-DD for broader compatibility
    match = re.match(r'(\d{1,2})\.([A-Za-z]{3})\.(\d{4})', date_str)
    if match:
        day, month_abbr, year = match.groups()
        month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                     "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
        month = month_map.get(month_abbr, "01")
        return f"{year}-{month}-{day}"  # Returning YYYY-MM-DD for safety
    return date_str

def build_payload(extracted_data, form_mapping):
    doc_to_label = {
        "Full_Name": "Name",
        "Father_Name": "F.name",
        "Gender": "Gender",
        "Identity_Number": "Identity no",
        "DOB": "Date of birth",
        "Date_of_Issue": "Date of issue",
        "Date_of_Expiry": "Date  expiry"
    }
    payload = {}
    for doc_key, doc_value in extracted_data.items():
        if doc_key in doc_to_label:
            label = doc_to_label[doc_key]
            if label in form_mapping:
                value = doc_value.strip()
                if "Date" in label:
                    value = clean_date(value)
                payload[form_mapping[label]] = value
                print(f"✅ Mapped: {doc_key} -> {label} = {value}")
            else:
                print(f"⚠️ Label '{label}' not in form mapping.")
        else:
            print(f"⚠️ Unknown doc key: {doc_key}")
    
    # Add missing required fields with defaults
    gender_label = "Gender"
    if gender_label in form_mapping and form_mapping[gender_label] not in payload:
        payload[form_mapping[gender_label]] = "Male"  # Using full word to match common Google Forms
        print(f"➕ Added default Gender: Male")
    
    country_label = "Country"
    if country_label in form_mapping and form_mapping[country_label] not in payload:
        payload[form_mapping[country_label]] = "Pakistan"
        print(f"➕ Added default Country: Pakistan")
    
    return payload

def submit_google_form(form_id, payload):
    submit_url = f"https://docs.google.com/forms/d/e/{form_id}/formResponse"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.post(submit_url, data=payload, headers=headers)
    return resp.status_code, resp.text

def submit_with_selenium(form_url, payload):
    # --- Edge browser setup ---
    driver_path = "msedgedriver.exe"
    options = Options()
    # Use a fresh profile to avoid conflicts
    profile_dir = os.path.join(os.getcwd(), "selenium_edge_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(driver_path)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(form_url)
    
    # Wait for the page to load
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(2)
    
    # Fill the form using the entry IDs
    for entry_id, value in payload.items():
        try:
            # Find the input element by its name attribute
            input_elem = driver.find_element(By.NAME, entry_id)
            input_elem.clear()
            input_elem.send_keys(value)
            print(f"📝 Filled {entry_id} with '{value}'")
        except Exception as e:
            print(f"⚠️ Could not fill {entry_id}: {e}")
    
    # Submit the form
    submit_button = driver.find_element(By.XPATH, "//div[@role='button']//span[text()='Submit']")
    submit_button.click()
    
    # Wait for submission to process
    time.sleep(3)
    driver.quit()
    print("✅ Form submitted via Selenium.")

def main():
    print("🤖 Google Form Auto-Filler (with POST & Selenium Fallback)")
    print("=" * 60)
    form_input = input("Enter Google Form URL or Form ID: ").strip()
    form_id = extract_form_id_from_url(form_input)
    print(f"Form ID: {form_id}")
    form_url = f"https://docs.google.com/forms/d/e/{form_id}/viewform"

    raw_path = input("Enter path to document image: ").strip()
    image_path = clean_path(raw_path)
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return

    print("\n📄 Extracting data from document...")
    extracted = extract_cnic_info(image_path)
    if "error" in extracted:
        print("❌ Extraction failed:", extracted["error"])
        return
    print("✅ Extracted data:")
    for k, v in extracted.items():
        print(f"   {k}: {v}")

    form_mapping = load_form_mapping()
    print("\n📋 Form mapping loaded.")
    payload = build_payload(extracted, form_mapping)

    if not payload:
        print("❌ No fields to submit. Check mapping.")
        return

    print("\n📤 Submitting form via POST request...")
    status, response_text = submit_google_form(form_id, payload)
    if status == 200:
        if "Your response has been recorded" in response_text or "Thank you" in response_text:
            print("✅ Form submitted successfully via POST!")
            return
        else:
            print("⚠️ Form returned 200 but confirmation not found. Trying Selenium fallback...")
    else:
        print(f"❌ Submission failed with status {status}. Trying Selenium fallback...")
        if "CAPTCHA" in response_text or "captcha" in response_text:
            print("  -> The form likely has CAPTCHA protection. Ask the owner to disable 'Send a copy of response'.")
    
    print("\n🤖 Attempting to submit via Selenium...")
    try:
        submit_with_selenium(form_url, payload)
    except Exception as e:
        print(f"❌ Selenium submission failed: {e}")

if __name__ == "__main__":
    main()