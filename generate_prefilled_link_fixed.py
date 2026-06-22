import json
import urllib.parse
import webbrowser
import re
import os
from brain_format import extract_cnic_info

def clean_path(path):
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    if path.endswith(')'):
        path = path[:-1]
    return path

def convert_date_to_iso(date_str):
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }
    for abbr, num in month_map.items():
        date_str = date_str.replace(abbr, num)
    parts = re.findall(r'\d+', date_str)
    if len(parts) >= 3:
        day, month, year = parts[0], parts[1], parts[2]
        if len(day) == 1: day = '0' + day
        if len(month) == 1: month = '0' + month
        if len(year) == 2: year = '20' + year
        return f"{year}-{month}-{day}"
    return date_str

def load_mapping(mapping_file="form_fields_final.json"):
    with open(mapping_file, "r") as f:
        return json.load(f)

def main():
    # Always ask for form URL
    form_url = input("Enter Google Form URL: ").strip()
    if not form_url.startswith("http"):
        print("❌ Invalid URL. Please start with http:// or https://")
        return

    raw_path = input("Enter document image path: ").strip()
    image_path = clean_path(raw_path)
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return

    print("🔍 Extracting data...")
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
                if "Date" in label:
                    value = convert_date_to_iso(value)
                    print(f"   Converted {doc_key} date to ISO: {value}")
                params[mapping[label]] = value

    if "Country" in mapping and mapping["Country"] not in params:
        params[mapping["Country"]] = "Pakistan"
        print("   Added default Country: Pakistan")

    # Clean form URL: remove any existing query parameters
    base_url = form_url.split('?')[0]
    query = urllib.parse.urlencode(params)
    prefilled_url = f"{base_url}?{query}"

    print("\n" + "=" * 70)
    print("🔗 Pre-filled link (copy and open in browser):")
    print(prefilled_url)
    print("=" * 70)

    open_browser = input("\nOpen link in browser? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open(prefilled_url)
        print("✅ Browser opened. Review and submit manually.")

if __name__ == "__main__":
    main()