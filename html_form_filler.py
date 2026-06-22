import os
import sys
import webbrowser
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from brain_format import extract_cnic_info, extract_photo

def clean_path(p):
    p = p.strip()
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1]
    if p.startswith("'") and p.endswith("'"):
        p = p[1:-1]
    if p.startswith('file://'):
        p = p[7:]
        if os.name == 'nt' and p.startswith('/'):
            p = p[1:]
        if '|' in p and len(p) > 2 and p[1] == '|':
            p = p[0] + ':' + p[2:]
    p = p.replace('\\', '/')
    return p

def fill_html_form(image_path, html_path, output_path="filled_form.html"):
    print("📄 Extracting data from document...")
    extracted = extract_cnic_info(image_path)
    if "error" in extracted:
        print("❌ Extraction failed:", extracted["error"])
        return False

    # Extract photo (shoulder-level)
    photo_path, photo_b64 = extract_photo(image_path)
    print("✅ Extracted data:")
    for k, v in extracted.items():
        print(f"   {k}: {v}")
    if photo_b64:
        print("   Photo extracted (base64 available)")

    # Gender mapping
    gender_map = {"M": "Male", "F": "Female", "Male": "Male", "Female": "Female"}

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # Insert photo into the form (look for specific container)
    # Try multiple selectors: div with class 'extracted-image', 'cnic-preview-card', or any div with 'mock-icon' parent
    photo_container = soup.find('div', class_='extracted-image')
    if not photo_container:
        photo_container = soup.find('div', class_='cnic-preview-card')
    if not photo_container:
        photo_container = soup.find('div', class_='mock-icon')
        if photo_container:
            photo_container = photo_container.parent
    if photo_container and photo_b64:
        # Remove old content inside the container (keep the container)
        photo_container.clear()
        img_tag = soup.new_tag('img')
        img_tag['src'] = f"data:image/jpeg;base64,{photo_b64}"
        img_tag['alt'] = 'Extracted CNIC Photo'
        img_tag['style'] = 'max-width:150px; border-radius:12px; border:2px solid #0b2b40; margin:10px auto; display:block;'
        photo_container.append(img_tag)
        print("✓ Inserted extracted photo into form")
    elif photo_container:
        # Placeholder message
        photo_container.clear()
        photo_container.append("No photo extracted")
        print("⚠️ No photo available, inserted placeholder")

    # Field mapping (same as before)
    doc_order = ["Full_Name", "Father_Name", "Gender", "Identity_Number", "DOB", "Date_of_Issue", "Date_of_Expiry", "Country"]
    doc_to_patterns = {
        "Full_Name": ["name", "full name", "full_name", "fullname"],
        "Father_Name": ["father", "father name", "father_name", "father's name", "guardian name"],
        "Gender": ["gender"],
        "Identity_Number": ["cnic", "identity number", "id number", "cnic number"],
        "DOB": ["date of birth", "dob", "birth date"],
        "Date_of_Issue": ["date of issue", "issue date", "issue_date", "doi"],
        "Date_of_Expiry": ["date of expiry", "expiry date", "expiry_date", "doe"],
        "Country": ["country"]
    }

    filled_count = 0
    for doc_key in doc_order:
        if doc_key not in extracted or not extracted[doc_key]:
            continue
        value = extracted[doc_key]
        if doc_key == "Gender":
            value = gender_map.get(value, value)
        # No date conversion – keep original DD.MM.YYYY

        patterns = doc_to_patterns.get(doc_key, [])
        best_match = None
        for inp in soup.find_all(['input', 'textarea', 'select']):
            if inp.get('type') in ['submit', 'reset', 'button', 'file', 'hidden']:
                continue
            field_id = inp.get('name') or inp.get('id')
            if not field_id:
                continue
            label_text = ""
            if inp.get('id'):
                label_tag = soup.find('label', {'for': inp['id']})
                if label_tag:
                    label_text = label_tag.get_text(strip=True).lower()
            if not label_text and field_id:
                label_text = field_id.lower()
            if not label_text:
                label_text = inp.get('placeholder', '').lower()
            if any(pat in label_text or pat in field_id.lower() for pat in patterns):
                best_match = inp
                break
        if best_match:
            inp = best_match
            if inp.name == 'input':
                if inp.get('type') == 'radio':
                    for radio in soup.find_all('input', {'type': 'radio', 'name': inp.get('name')}):
                        if radio.get('value') == value:
                            radio['checked'] = 'checked'
                    filled_count += 1
                    print(f"✓ Selected radio '{inp.get('name')}' with '{value}'")
                else:
                    inp['value'] = value
                    filled_count += 1
                    print(f"✓ Filled '{inp.get('name') or inp.get('id')}' with '{value}'")
            elif inp.name == 'textarea':
                inp.string = value
                filled_count += 1
                print(f"✓ Filled textarea '{inp.get('name') or inp.get('id')}' with '{value}'")
            elif inp.name == 'select':
                for option in inp.find_all('option'):
                    if option.get('value') == value or option.text.strip() == value:
                        option['selected'] = 'selected'
                        filled_count += 1
                        print(f"✓ Selected option '{value}' in select '{inp.get('name') or inp.get('id')}'")
                        break
        else:
            print(f"⚠️ No matching field for '{doc_key}'")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    print(f"\n✅ Filled HTML saved to: {output_path}")
    return output_path

def main():
    print("=" * 50)
    print("📝 HTML Form Filler from Document")
    print("=" * 50)

    img_path = input("Enter document image path: ").strip()
    img_path = clean_path(img_path)
    if not os.path.exists(img_path):
        print("❌ Image file not found.")
        return

    html_path = input("Enter HTML form file path (e.g., C:/Users/ZAH/Desktop/CNIC_form.html): ").strip()
    html_path = clean_path(html_path)
    if not os.path.exists(html_path):
        print(f"❌ HTML file not found at: {html_path}")
        return

    output = input("Enter output HTML file name (default: filled_CNIC_form.html): ").strip()
    if not output:
        output = "filled_CNIC_form.html"
    if os.path.sep in output or '/' in output:
        output = os.path.basename(output)

    out_path = fill_html_form(img_path, html_path, output)
    if out_path:
        open_browser = input("\nOpen filled form in browser? (y/n): ").lower()
        if open_browser == 'y':
            webbrowser.open(os.path.abspath(out_path))
            print("✅ Browser opened.")

if __name__ == "__main__":
    main()