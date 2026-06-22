import os
import re
import json
import requests
import cv2
import numpy as np
import base64
from paddleocr import PaddleOCR
import easyocr
from preprocess import preprocess_image   # make sure preprocess.py exists

# ---------- Super-Resolution (Real-ESRGAN) ----------
try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

def get_sr_model():
    if not SR_AVAILABLE:
        return None
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=4,
        model_path=None,
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=False
    )
    return upsampler

sr_upsampler = get_sr_model()

# ---------- NAFNet ----------
try:
    from nafnetlib import DenoiseProcessor
    NAFNET_AVAILABLE = True
except ImportError:
    NAFNET_AVAILABLE = False

def enhance_with_nafnet(img_bgr):
    if not NAFNET_AVAILABLE:
        return img_bgr
    try:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        processor = DenoiseProcessor()
        cleaned_rgb = processor.process(img_rgb)
        return cv2.cvtColor(cleaned_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"[NAFNet] Enhancement failed: {e}")
        return img_bgr

# ---------- Photo Extraction (minimal bottom) ----------
def enhance_and_save_photo(cropped_img, output_path="extracted_photo.png", max_size=400):
    h, w = cropped_img.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        cropped_img = cv2.resize(cropped_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    elif max(h, w) < 200:
        new_w = w * 2
        new_h = h * 2
        cropped_img = cv2.resize(cropped_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    enhanced = cv2.convertScaleAbs(cropped_img, alpha=1.1, beta=0)
    cv2.imwrite(output_path, enhanced)
    with open(output_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return output_path, b64

def extract_photo(image_path, output_path="extracted_photo.png"):
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        margin_x = w // 2
        margin_y_top = h // 2
        margin_y_bottom = h // 2
        x = max(0, x - margin_x)
        y = max(0, y - margin_y_top)
        w = min(img.shape[1] - x, w + 2 * margin_x)
        h = min(img.shape[0] - y, h + margin_y_top + margin_y_bottom)
        cropped = img[y:y+h, x:x+w]
    else:
        h, w = img.shape[:2]
        x = int(w * 0.6)
        y = int(h * 0.05)
        w_crop = int(w * 0.35)
        h_crop = int(h * 0.35)
        cropped = img[y:y+h_crop, x:x+w_crop]   # FIXED: ] instead of )
    return enhance_and_save_photo(cropped, output_path)

# ---------- OCR Engines ----------
paddle_ocr = PaddleOCR(
    lang='en',
    use_textline_orientation=True,
    text_det_thresh=0.2,
    text_det_box_thresh=0.5,
    text_det_unclip_ratio=2.0
)
easy_reader = easyocr.Reader(['en'], gpu=True, verbose=False)

def get_ocr_text(image_path):
    try:
        processed = preprocess_image(
            image_path,
            use_super_res=(sr_upsampler is not None),
            sr_upsampler=sr_upsampler
        )
        if NAFNET_AVAILABLE:
            processed = enhance_with_nafnet(processed)
        result = paddle_ocr.ocr(processed, cls=True)
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            scores = [line[1][1] for line in result[0]]
            texts = [t for t, s in zip(texts, scores) if s > 0.4]
            if texts:
                return " ".join(texts), "PaddleOCR"
    except Exception as e:
        print(f"PaddleOCR error: {e}")
    try:
        result = easy_reader.readtext(image_path, detail=0)
        if result:
            return " ".join(result), "EasyOCR"
    except Exception as e:
        print(f"EasyOCR error: {e}")
    return "", None

# ---------- Post-processing ----------
def postprocess_extracted_data(data: dict, raw_text: str = "") -> dict:
    cleaned = {}
    gender_map = {"male": "M", "female": "F", "m": "M", "f": "F", "man": "M", "woman": "F"}
    if not data.get("Country") and raw_text:
        cm = re.search(r'(?:Country|Nationality|Place of Issue)[:\s]*([A-Za-z]+)', raw_text, re.IGNORECASE)
        if cm:
            data["Country"] = cm.group(1).strip()
    if not data.get("Gender") and raw_text:
        gm = re.search(r'(?:Gender|Sex|Category)[:\s]*([MF]|Male|Female)', raw_text, re.IGNORECASE)
        if gm:
            gen = gm.group(1).lower()
            data["Gender"] = "M" if gen in ['m', 'male'] else "F" if gen in ['f', 'female'] else ""
    for key, value in data.items():
        if not isinstance(value, str):
            cleaned[key] = value
            continue
        value = re.sub(r'\s+', ' ', value).strip()
        if "Identity_Number" in key or "ID" in key or "Number" in key:
            clean_id = re.sub(r'[^\d-]', '', value)
            match = re.search(r'\d{5}-\d{7}-\d', clean_id)
            if match:
                value = match.group(0)
            elif len(clean_id) >= 13:
                digits = re.sub(r'\D', '', clean_id)
                if len(digits) >= 13:
                    value = f"{digits[:5]}-{digits[5:12]}-{digits[12:13]}"
        if key == "Gender" or key == "gender":
            lower_val = value.lower()
            value = gender_map.get(lower_val, value[:1].upper() if value else "")
        if "DOB" in key or "Date" in key or "Issue" in key or "Expiry" in key:
            value = re.sub(r'[/\-]', '.', value)
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', value):
                d = re.search(r'\d{2}\.\d{2}\.\d{4}', value)
                if d:
                    value = d.group(0)
        if "Name" in key or "name" in key:
            words = value.split()
            if words:
                last_word = words[-1]
                if re.match(r'^(Fik|Juk|Jkr|Jnr|Jr|XXX|YYY|Unk|F|J)$', last_word, re.IGNORECASE):
                    words = words[:-1]
            if len(words) > 3:
                words = words[:3]
            value = ' '.join(word.capitalize() for word in words)
        cleaned[key] = value
    return cleaned

# ---------- Main ----------
def extract_cnic_info(image_path: str) -> dict:
    print(f"[INFO] Processing: {image_path}")
    full_text, ocr_engine = get_ocr_text(image_path)
    if not full_text:
        return {"error": "No text extracted by any OCR engine"}
    print(f"[OCR] {ocr_engine} extracted {len(full_text)} chars: {full_text[:200]}...")
    photo_path, photo_b64 = extract_photo(image_path)
    photo_info = {}
    if photo_path:
        photo_info["Photo_Path"] = photo_path
        photo_info["Photo_Base64"] = photo_b64
        print("[INFO] Photo extracted")
    url = "http://localhost:11434/api/generate"
    prompt = f"""Extract CNIC/Driving License information as JSON with keys: Full_Name, Father_Name, Gender, Identity_Number, DOB, Date_of_Issue, Date_of_Expiry, Country. Dates: DD.MM.YYYY. Gender: 'M' or 'F'. Only JSON. Text: {full_text}"""
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
        "temperature": 0.0,
        "format": {
            "type": "object",
            "properties": {
                "Full_Name": {"type": "string"},
                "Father_Name": {"type": "string"},
                "Gender": {"type": "string"},
                "Identity_Number": {"type": "string"},
                "DOB": {"type": "string"},
                "Date_of_Issue": {"type": "string"},
                "Date_of_Expiry": {"type": "string"},
                "Country": {"type": "string"}
            }
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            output = resp.json().get("response", "")
            data = json.loads(output) if isinstance(output, str) else output
            data = postprocess_extracted_data(data, raw_text=full_text)
            data.update(photo_info)
            print("[SUCCESS] Extraction done")
            return data
        else:
            return {"error": f"Ollama HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"Ollama error: {e}"}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(extract_cnic_info(sys.argv[1]), indent=4))
    else:
        print("Usage: python brain_format.py <image_path>")