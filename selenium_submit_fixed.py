import json
import re
import time
import os
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from brain_format import extract_cnic_info

# ========== CONFIG ==========
EDGE_DRIVER = "msedgedriver.exe"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeunqDGmQdawFZqpMBmCOIqYhBDr9OhV0ftDJMrjBy1nBEyhQ/viewform"
IMAGE_PATH = r"C:\Users\ZAH\Downloads\WhatsApp Image 2026-05-12 at 19.34.50.jpeg"  # change if needed

def load_mapping(mapping_file="form_fields_final.json"):
    with open(mapping_file, "r") as f:
        return json.load(f)   # {label: entry_id}

def fill_form_with_selenium(driver, payload):
    # Wait for the first input element to be present
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, list(payload.keys())[0])))
    time.sleep(2)  # extra for any JS

    for entry_id, value in payload.items():
        try:
            # Wait for the element to be interactable
            elem = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.NAME, entry_id))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", elem)
            time.sleep(0.5)
            elem.clear()
            elem.send_keys(str(value))
            print(f"✅ Filled {entry_id} with '{value}'")
        except Exception as e:
            print(f"⚠️ Could not fill {entry_id}: {e}")
            # Optionally take screenshot
            driver.save_screenshot(f"error_{entry_id}.png")

    # Click submit button
    try:
        submit = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button']//span[text()='Submit']"))
        )
        submit.click()
        print("✅ Submit button clicked.")
    except:
        # Fallback: find by class or text
        try:
            submit = driver.find_element(By.XPATH, "//div[@role='button'][contains(.,'Submit')]")
            submit.click()
        except:
            print("❌ Could not find submit button.")

def main():
    # Extract data from image
    extracted = extract_cnic_info(IMAGE_PATH)
    if "error" in extracted:
        print("Extraction failed:", extracted["error"])
        return
    print("Extracted:", extracted)

    # Load form mapping (label -> entry_id)
    mapping = load_mapping()  # e.g., {"Name": "entry.615891020", ...}
    # Convert extracted data to payload using doc_to_label mapping
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
    for doc_key, doc_val in extracted.items():
        if doc_key in doc_to_label:
            label = doc_to_label[doc_key]
            if label in mapping:
                payload[mapping[label]] = doc_val
    # Add default Country
    if "Country" in mapping and mapping["Country"] not in payload:
        payload[mapping["Country"]] = "Pakistan"
    print("Payload to submit:", payload)

    # Setup Edge driver
    options = Options()
    # Use a fresh profile to avoid conflicts
    profile_dir = os.path.join(os.getcwd(), "selenium_edge_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(EDGE_DRIVER)
    driver = webdriver.Edge(service=service, options=options)

    try:
        driver.get(FORM_URL)
        # Wait for the page to be fully loaded (any input field visible)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name], textarea[name]")))
        time.sleep(2)

        fill_form_with_selenium(driver, payload)
        # Wait for submission confirmation
        time.sleep(5)
        # Optional: check for success message
        if "Your response has been recorded" in driver.page_source:
            print("✅ Form submission confirmed!")
        else:
            print("⚠️ Submission may have failed; check browser.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()