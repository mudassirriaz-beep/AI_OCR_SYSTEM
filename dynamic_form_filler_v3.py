import json
import urllib.parse
import webbrowser
import os
from brain_format import extract_cnic_info

# Path to your manual mapping file
MAPPING_FILE = "my_form_fields.json"

def clean_path(p):
    p = p.strip()
    if p.startswith('"') and p.endswith('"'): p = p[1:-1]
    if p.startswith("'") and p.endswith("'"): p = p[1:-1]
    if p.endswith(')'): p = p[:-1]
    return p

def main():
    # 1. Load manual mapping
    if not os.path.exists(MAPPING_FILE):
        print(f"❌ Mapping file '{MAPPING_FILE}' not found.")
        print("Please create it following the instructions.")
        return
    with open(MAPPING_FILE, "r") as f:
        mapping = json.load(f)   # { label: entry_id }

    # 2. Get form URL and image path
    form_url = input("Enter Google Form URL: ").strip()
    if "forms.gle" in form_url:
        print("⚠️ Shortened URL detected. Pre‑filled links may not work. Please use the full /viewform URL.")
    img_path = input("Enter document image path: ").strip()
    img_path = clean_path(img_path)
    if not os.path.exists(img_path):
        print("❌ Image file not found.")
        return

    # 3. Extract data from document
    print("\n🔍 Extracting data from document...")
    extracted = extract_cnic_info(img_path)
    if "error" in extracted:
        print("❌ Extraction failed:", extracted["error"])
        return
    print("✅ Extracted data:")
    for k, v in extracted.items():
        print(f"   {k}: {v}")

    # 4. Map document fields to form labels (adjust this dictionary if needed)
    doc_to_label = {
        "Full_Name": "Name",
        "Father_Name": "F.name",
        "Gender": "Gender",
        "Identity_Number": "Identity no",
        "DOB": "Date of birth",
        "Date_of_Issue": "Date of issue",
        "Date_of_Expiry": "Date expiry"
    }

    params = {}
    for doc_key, doc_val in extracted.items():
        if doc_key in doc_to_label:
            label = doc_to_label[doc_key]
            if label in mapping:
                params[mapping[label]] = doc_val
                print(f"   Mapped '{doc_key}' -> '{label}' = {doc_val}")
            else:
                print(f"⚠️ Warning: No entry ID for label '{label}'. Check your mapping file.")
        else:
            print(f"⚠️ Ignoring document key '{doc_key}' (not in doc_to_label)")

    # Optional: add default country if your form has a Country field
    if "Country" in mapping and mapping["Country"] not in params:
        params[mapping["Country"]] = "Pakistan"
        print("   Added default Country: Pakistan")

    if not params:
        print("❌ No fields mapped. Check your mapping file and doc_to_label.")
        return

    # 5. Build pre‑filled link
    base_url = form_url.split('?')[0]
    query = urllib.parse.urlencode(params)
    prefilled_url = f"{base_url}?{query}"
    print("\n" + "=" * 70)
    print("🔗 Pre‑filled link (copy and open in browser):")
    print(prefilled_url)
    print("=" * 70)

    # 6. Open in browser
    webbrowser.open(prefilled_url)
    print("✅ Browser opened. Review the form and click Submit manually.")

if __name__ == "__main__":
    main()