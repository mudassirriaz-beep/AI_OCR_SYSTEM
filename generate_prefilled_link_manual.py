import json
import urllib.parse
import webbrowser
import os
from brain_format import extract_cnic_info

def clean_path(path):
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    # remove any trailing parenthesis (common copy-paste error)
    if path.endswith(')'):
        path = path[:-1]
    return path

def load_mapping(mapping_file="form_fields_final.json"):
    with open(mapping_file, "r") as f:
        return json.load(f)

def main():
    raw_path = input("Enter document image path: ").strip()
    image_path = clean_path(raw_path)
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return

    print("🔍 Extracting data from document...")
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

    # Add default country if field exists
    if "Country" in mapping and mapping["Country"] not in params:
        params[mapping["Country"]] = "Pakistan"

    form_base = "https://docs.google.com/forms/d/e/1FAIpQLSeunqDGmQdawFZqpMBmCOIqYhBDr9OhV0ftDJMrjBy1nBEyhQ/viewform"
    query = urllib.parse.urlencode(params)
    prefilled_url = f"{form_base}?{query}"

    print("\n" + "=" * 70)
    print("🔗 Pre-filled form link (copy and open in browser):")
    print(prefilled_url)
    print("=" * 70)

    # Optionally open the link automatically
    open_browser = input("\nOpen link in your default browser? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open(prefilled_url)
        print("✅ Browser opened. Review the form and click Submit manually.")
    else:
        print("You can manually copy the link and paste it into your browser.")

if __name__ == "__main__":
    main()