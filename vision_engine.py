import streamlit as st
import cv2
import numpy as np
from paddleocr import PaddleOCR
import requests
import json
import re
import os

# --- Windows Fix ---
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

st.set_page_config(page_title="AI CNIC Auto-Fill", layout="wide")

# --- 1. Advanced Image Processing Function ---
def get_processed_image(img_array):
    # Image ko read aur resize karein (Resolution barhane ke liye)
    img = cv2.imdecode(img_array, 1)
    height, width = img.shape[:2]
    img = cv2.resize(img, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
    
    # Grayscale aur Contrast (CLAHE)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    contrast = clahe.apply(gray)
    
    # Denoising (Bilaterial filter edges ko sharp rakhta hai)
    denoised = cv2.bilateralFilter(contrast, 9, 75, 75)
    
    # Final Thresholding (Otsu's Binarization)
    _, final_img = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Save processed image
    processed_path = "vision_ready.jpg"
    cv2.imwrite(processed_path, final_img)
    return processed_path

# --- 2. AI & Session State ---
if 'form_data' not in st.session_state:
    st.session_state.form_data = {"Full_Name": "", "Father_Name": "", "Identity_Number": "", "DOB": ""}

@st.cache_resource
def load_ocr_model():
    return PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

def get_ai_interpretation(text):
    # Regex for CNIC backup (handles spaces/hyphens)
    cnic_match = re.search(r'\d{5}[-\s]?\d{7}[-\s]?\d{1}', text)
    extracted_cnic = cnic_match.group() if cnic_match else ""
    
    url = "http://localhost:11434/api/generate"
    prompt = f"Extract details from: {text}. Output JSON with keys: Full_Name, Father_Name, Identity_Number, DOB."
    
    try:
        model_name = os.environ.get("AI_DOC_MODEL", "docextract:v11")
        response = requests.post(url, json={"model": model_name, "prompt": prompt, "stream": False, "format": "json"}, timeout=15)
        raw_json = json.loads(response.json().get("response", "{}"))
        
        return {
            "Full_Name": raw_json.get("Full_Name", ""),
            "Father_Name": raw_json.get("Father_Name", ""),
            "Identity_Number": extracted_cnic if extracted_cnic else raw_json.get("Identity_Number", ""),
            "DOB": raw_json.get("DOB", "")
        }
    except:
        return {"Full_Name": "", "Father_Name": "", "Identity_Number": extracted_cnic, "DOB": ""}

# --- 3. UI Layout ---
st.title("🚀 Smart CNIC Auto-Fill")

col1, col2 = st.columns([1, 1])

with col1:
    uploaded_file = st.file_uploader("Upload CNIC Front", type=['jpg','png','jpeg'])
    if uploaded_file:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        st.image(uploaded_file, caption="Original Image", width=350)
        
        if st.button("Magic Auto-Fill ✨"):
            with st.spinner("Processing..."):
                # Step A: Image Cleaning
                processed_path = get_processed_image(file_bytes)
                st.info("Image cleaned for better OCR!")
                
                # Step B: OCR on Cleaned Image
                ocr = load_ocr_model()
                result = ocr.ocr(processed_path, cls=True)
                all_text = " ".join([line[1][0] for line in result[0]]) if result[0] else ""
                
                # Step C: AI Extraction
                data = get_ai_interpretation(all_text)
                st.session_state.form_data.update(data)
                st.rerun()

with col2:
    with st.form("main_form"):
        st.subheader("Final Verification")
        f_name = st.text_input("Full Name", value=st.session_state.form_data["Full_Name"])
        f_father = st.text_input("Father Name", value=st.session_state.form_data["Father_Name"])
        f_cnic = st.text_input("Identity Number (CNIC)", value=st.session_state.form_data["Identity_Number"])
        f_dob = st.text_input("Date of Birth", value=st.session_state.form_data["DOB"])
        
        if st.form_submit_button("Save to Database"):
            st.success("Data Saved!")