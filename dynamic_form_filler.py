import re
import urllib.parse
import webbrowser
import time
import os
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from brain_format import extract_cnic_info

EDGE_DRIVER = "msedgedriver.exe"   # make sure this is in the same folder

def get_form_mapping(form_url):
    """Extract {label: entry_id} by scraping the live form."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    profile_dir = os.path.join(os.getcwd(), "selenium_edge_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(EDGE_DRIVER)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(form_url)

    print("\n🔐 If login required, please log in now in the browser window.")
    input("Then press Enter here to continue...")

    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(3)  # let dynamic content settle

    mapping = {}
    # Find all input/textarea/select with name starting with "entry."
    elements = driver.find_elements(By.CSS_SELECTOR, "[name^='entry.']")
    for elem in elements:
        entry_id = elem.get_attribute("name")
        # Find the associated question text
        # Google Forms typically wrap each question in a div with role="listitem"
        parent = elem.find_element(By.XPATH, "./ancestor::div[@role='listitem']")
        label_elem = parent.find_element(By.CSS_SELECTOR, "[class*='freebirdFormviewerComponentsQuestionText'], [jsname='rnjvif'], .quantumWizTextinputPaperinputLabel")
        label = label_elem.text.strip() if label_elem else entry_id
        mapping[label] = entry_id
    driver.quit()
    return mapping

def convert_date_to_iso(date_str):
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }
    for abbr, num in month_map.items():
        date_str = date_str.replace(abbr, num)
    parts = re.findall(r'\d+', date_str)
    if len(parts) >= 3:
        d, m, y = parts[0], parts[1], parts[2]
        if len(d) == 1: d = '0' + d
        if len(m) == 1: m = '0' + m
        if len(y) == 2: y = '20' + y
        return f"{y}-{m}-{d}"
    return date_str

def clean_path(p):
    p = p.strip()
    if p.startswith('"') and p.endswith('"'): p = p[1:-1]
    if p.startswith("'") and p.endswith("'"): p = p[1:-1]
    if p.endswith(')'): p = p[:-1]
    return p

def main():
    form_url = input("Enter Google Form URL: ").strip()
    # Ensure full viewform URL (shortened forms.gle may drop query parameters)
    if "forms.gle" in form_url:
        print("⚠️ Shortened URL detected. Pre‑filled links may not work. Please use the full /viewform URL from the address bar.")
    img_path = input("Enter document image path: ").strip()
    img_path = clean_path(img_path)
    if not os.path.exists(img_path):
        print("❌ Image not found.")
        return

    print("\n🔍 Extracting form fields (this may take a few seconds)...")
    try:
        mapping = get_form_mapping(form_url)
        print(f"✅ Found {len(mapping)} fields.")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return

    print("\n📄 Extracting data from document...")
    extracted = extract_cnic_info(img_path)
    if "error" in extracted:
        print("❌ Extraction failed:", extracted["error"])
        return
    print("✅ Extracted data:")
    for k, v in extracted.items():
        print(f"   {k}: {v}")

    # Flexible field matching
    doc_to_labels = {
        "Full_Name": ["Name", "Full Name", "Applicant Name"],
        "Father_Name": ["Father Name", "Father's Name", "F.name"],
        "Gender": ["Gender"],
        "Identity_Number": ["Identity Number", "ID Number", "CNIC", "Identity no"],
        "DOB": ["Date of Birth", "DOB", "Birth Date"],
        "Date_of_Issue": ["Date of Issue", "Issue Date"],
        "Date_of_Expiry": ["Date of Expiry", "Expiry Date", "Date expiry"]
    }

    params = {}
    for doc_key, doc_val in extracted.items():
        if doc_key in doc_to_labels:
            possible_labels = doc_to_labels[doc_key]
            for p_label in possible_labels:
                for form_label, entry_id in mapping.items():
                    if p_label.lower() in form_label.lower() or form_label.lower() in p_label.lower():
                        val = doc_val
                        if "Date" in p_label:
                            val = convert_date_to_iso(val)
                        params[entry_id] = val
                        print(f"   Mapped {doc_key} -> '{form_label}' ({entry_id}) = {val}")
                        break
                else:
                    continue
                break

    # Add default country if the form has a Country field
    for form_label, entry_id in mapping.items():
        if "country" in form_label.lower() and entry_id not in params:
            params[entry_id] = "Pakistan"
            print(f"   Added default Country: Pakistan -> {entry_id}")

    if not params:
        print("❌ No fields could be mapped. Check the form's question texts.")
        return

    base_url = form_url.split('?')[0]
    query = urllib.parse.urlencode(params)
    prefilled_url = f"{base_url}?{query}"
    print("\n" + "="*70)
    print("🔗 Pre-filled link (copy and open in browser):")
    print(prefilled_url)
    print("="*70)

    open_browser = input("\nOpen link in browser? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open(prefilled_url)
        print("✅ Browser opened. Review the form and click Submit manually.")

if __name__ == "__main__":
    main()