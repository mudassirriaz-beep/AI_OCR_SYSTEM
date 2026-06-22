import os
import json
import re
import requests
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== CONFIG ==========
EDGE_DRIVER_PATH = "msedgedriver.exe"   # same folder mein hai
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

# ========== 1. OPEN FORM AND GET HTML ==========
def get_form_html_and_text(form_url):
    options = Options()
    options.add_argument('--no-sandbox')
    service = Service(EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(form_url)
    
    # Agar login chahiye to manual login ka chance
    input("🔐 If form requires login, please login in the browser, then press Enter...")
    
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    html = driver.page_source
    visible_text = driver.find_element(By.TAG_NAME, "body").text
    driver.quit()
    return html, visible_text

# ========== 2. LLM SE FIELDS EXTRACT KARO ==========
def extract_fields_with_llm(visible_text, html_snippet):
    prompt = f"""You are a form field extractor. Given the following form HTML and visible text, extract all input fields. Return a JSON object where keys are the field labels (e.g., "Full Name") and values are the input 'name' attributes (for Google Forms, these look like 'entry.xxxxx'). Only output valid JSON, no extra text.

Visible text (first 3000 chars):
{visible_text[:3000]}

HTML snippet (first 4000 chars):
{html_snippet[:4000]}

JSON:"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.0
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception as e:
        print(f"LLM error: {e}")
    return {}

# ========== 3. SUBMIT FORM (POST REQUEST) ==========
def submit_google_form(form_id, payload):
    submit_url = f"https://docs.google.com/forms/d/e/{form_id}/formResponse"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.post(submit_url, data=payload, headers=headers)
        return resp.status_code
    except Exception as e:
        print(f"Submission error: {e}")
        return 500

# ========== 4. MAIN AGENT ==========
def main():
    print("=" * 50)
    print("🤖 FORM AUTO-FILL AGENT")
    print("=" * 50)
    
    # --- Step A: Form link lo ---
    form_url = input("\nEnter Google Form public URL: ").strip()
    if "/edit" in form_url:
        form_url = form_url.replace("/edit", "/viewform")
    print(f"Using URL: {form_url}")
    
    # --- Step B: Extract fields via Selenium + LLM ---
    print("\n🔍 Opening form in Edge...")
    html, visible = get_form_html_and_text(form_url)
    print("🤖 Asking LLM to extract fields...")
    mapping = extract_fields_with_llm(visible, html)
    if not mapping:
        print("❌ Failed to extract fields. Check form accessibility or LLM response.")
        return
    
    # Save mapping
    with open("form_mapping.json", "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"✅ Mapping saved to 'form_mapping.json' ({len(mapping)} fields)")
    
    # --- Step C: Document image se data extract ---
    from brain_format import extract_cnic_info   # aap ka existing function
    image_path = input("\nEnter document image path: ").strip()
    extracted = extract_cnic_info(image_path)
    print("📄 Extracted data:", extracted)
    
    # --- Step D: Mapping ke hisaab se payload banayein ---
    payload = {}
    for doc_key, doc_val in extracted.items():
        for form_label, entry_id in mapping.items():
            if doc_key.lower() in form_label.lower() or form_label.lower() in doc_key.lower():
                payload[entry_id] = doc_val
                print(f"Mapped: '{doc_key}' -> {entry_id}")
                break
    
    if not payload:
        print("❌ No fields matched. Check mapping or extracted keys.")
        return
    
    # --- Step E: Form ID nikaalein URL se ---
    match = re.search(r'/d/e/([a-zA-Z0-9_-]+)/', form_url)
    if not match:
        print("❌ Could not extract form ID from URL.")
        return
    form_id = match.group(1)
    
    # --- Step F: Submit ---
    status = submit_google_form(form_id, payload)
    if status == 200:
        print("✅ Form submitted successfully!")
    else:
        print(f"❌ Submission failed. Status code: {status}")
    
    print("\n🎉 Agent finished. Mapping saved for future use.")

if __name__ == "__main__":
    main()