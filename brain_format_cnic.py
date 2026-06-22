"""
CNIC extraction brain — SLM-first pipeline:
  1. VLM (Qwen2-VL-2B)        — direct image → JSON (if available)
  2. SLM primary extraction    — combined dual-OCR text → LLM → JSON
  3. Regex fallback             — rule-based extraction
  4. Regex supplements SLM     — cross-validate; higher confidence wins
  5. Photo extraction
  6. Confidence gate            → _needs_review flag
"""
import base64
import re

import cv2

import ocr_engine
import profile_builder


# ── Photo extraction ──────────────────────────────────────────────────────────

def _enhance_and_save_photo(cropped, output_path="extracted_photo.png"):
    h, w = cropped.shape[:2]
    if max(h, w) > 400:
        scale   = 400 / max(h, w)
        cropped = cv2.resize(cropped, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_LANCZOS4)
    elif max(h, w) < 200:
        cropped = cv2.resize(cropped, (w * 2, h * 2),
                             interpolation=cv2.INTER_CUBIC)
    enhanced = cv2.convertScaleAbs(cropped, alpha=1.1, beta=0)
    cv2.imwrite(output_path, enhanced)
    with open(output_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return output_path, b64


def extract_photo(image_path: str, output_path: str = "extracted_photo.png"):
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1,
                                     minNeighbors=5, minSize=(50, 50))
    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        mx, my  = w // 2, h // 2
        x       = max(0, x - mx);   y = max(0, y - my)
        w       = min(img.shape[1] - x, w + 2 * mx)
        h       = min(img.shape[0] - y, h + 2 * my)
        cropped = img[y:y + h, x:x + w]
    else:
        ih, iw  = img.shape[:2]
        cropped = img[int(ih * 0.05):int(ih * 0.40),
                      int(iw * 0.60):int(iw * 0.95)]
    return _enhance_and_save_photo(cropped, output_path)


# ── Dual OCR helper ───────────────────────────────────────────────────────────

def _dual_ocr(image_path: str) -> tuple:
    """
    Two OCR passes — standard adaptive (primary for CNIC) + a second pass.
    Returns (primary_text, secondary_text).
    """
    blocks, engine = ocr_engine.extract_blocks(image_path)
    primary_text   = ocr_engine._blocks_to_layout(blocks) if blocks else ""
    if primary_text:
        print(f"[OCR]  {engine} spatial → {len(primary_text)} chars, {len(blocks)} blocks")
    else:
        primary_text, engine = ocr_engine.extract_text(image_path)
        print(f"[OCR]  {engine} → {len(primary_text)} chars")

    # Second pass: try EasyOCR if RapidOCR was primary (different char recognition)
    secondary_text = ""
    try:
        easy = ocr_engine._get_easy()
        if easy is not None and "Easy" not in (engine or ""):
            result = easy.readtext(image_path, detail=1)
            if result:
                easy_blocks = []
                for bbox, text, conf in result:
                    if text.strip():
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        easy_blocks.append((min(ys), min(xs), text))
                secondary_text = ocr_engine._blocks_to_layout(easy_blocks)
                print(f"[OCR2] EasyOCR → {len(secondary_text)} chars")
    except Exception:
        pass

    return primary_text, secondary_text


# ── Merge SLM + regex profiles ────────────────────────────────────────────────

def _merge_profiles(slm_profile: dict, slm_conf: dict,
                    reg_profile: dict, reg_conf: dict) -> tuple:
    profile = dict(slm_profile)
    conf    = dict(slm_conf)
    for key in reg_profile:
        r_val  = reg_profile.get(key, "")
        r_conf = reg_conf.get(key, 0.0)
        if r_val and r_conf >= conf.get(key, 0.0):
            profile[key] = r_val
            conf[key]    = r_conf
    return profile, conf


# ── Normalize & validate ──────────────────────────────────────────────────────

def _normalize(profile: dict, conf: dict, combined_text: str) -> tuple:
    # Normalize dates
    for key in ("DOB", "Date_of_Issue", "Date_of_Expiry"):
        val = profile.get(key, "")
        if val:
            profile[key] = profile_builder._norm_date(val)

    # Validate CNIC number format
    cnic = profile.get("Identity_Number", "")
    if cnic and not re.match(r'^\d{5}-\d{7}-\d$', cnic.strip()):
        m = profile_builder._CNIC_RE.search(combined_text)
        if m:
            profile["Identity_Number"] = profile_builder._norm_cnic(m.group())
            conf["Identity_Number"]    = 0.95
        else:
            conf["Identity_Number"] = max(0.0, conf.get("Identity_Number", 0.0) - 0.20)

    # Names: clean punctuation, title-case
    for key in ("Full_Name", "Father_Name"):
        val = profile.get(key, "")
        if val:
            val = re.sub(r'[^A-Za-z\s]', ' ', val).strip()
            val = ' '.join(w.capitalize() for w in val.split())
            profile[key] = val

    # Boost confidence for fields confirmed in OCR text
    for key in ("Identity_Number", "DOB"):
        val = profile.get(key, "")
        if val and val in combined_text:
            conf[key] = min(1.0, conf.get(key, 0.0) + 0.05)

    return profile, conf


# ── Main fallback pipeline ────────────────────────────────────────────────────

def _ocr_slm_pipeline(image_path: str) -> tuple:
    import slm_client

    primary_text, secondary_text = _dual_ocr(image_path)
    if not primary_text:
        return {}, {}

    combined = primary_text + "\n" + secondary_text

    # Primary: SLM from all OCR passes
    ocr_texts = [t for t in [primary_text, secondary_text] if t.strip()]
    slm_profile, slm_conf = slm_client.primary_extract(ocr_texts, "CNIC")

    # Regex (always runs)
    reg_profile, reg_conf = profile_builder.build_cnic_profile(primary_text)
    print(f"[REGEX] {{{', '.join(f'{k}:{v:.2f}' for k,v in reg_conf.items())}}}")

    if slm_profile:
        profile, confidence = _merge_profiles(slm_profile, slm_conf,
                                              reg_profile, reg_conf)
    else:
        print("[PIPELINE] SLM offline — regex-only mode")
        profile, confidence = reg_profile, reg_conf

        low_conf = profile_builder.low_confidence_fields(confidence)
        if low_conf:
            print(f"[SLM-GAP]  Fields: {low_conf}")
            gap = slm_client.ask_slm(primary_text, low_conf, doc_type="CNIC")
            for k, v in gap.items():
                if v and k in low_conf:
                    profile[k]    = str(v).strip()
                    confidence[k] = 0.65

        overall = profile_builder.overall_confidence(confidence)
        if overall < profile_builder.CONF_THRESHOLD:
            deep = slm_client.full_extract(primary_text, "CNIC")
            for k, v in deep.items():
                if v and confidence.get(k, 0) < profile_builder.CONF_THRESHOLD:
                    profile[k]    = str(v).strip()
                    confidence[k] = 0.70

    profile, confidence = _normalize(profile, confidence, combined)
    return profile, confidence


# ── Main entry point ──────────────────────────────────────────────────────────

def extract_cnic_info(image_path: str) -> dict:
    print(f"[CNIC] Processing: {image_path}")

    profile, confidence = {}, {}
    try:
        import vlm_extractor
        if vlm_extractor.is_available():
            profile, confidence = vlm_extractor.extract_cnic(image_path)
            filled = sum(1 for v in profile.values() if v)
            print(f"[VLM]  Extracted {filled}/{len(profile)} fields")
        else:
            print("[VLM]  Model files missing — using OCR+SLM pipeline")
    except Exception as e:
        print(f"[VLM]  Error ({e}) — using OCR+SLM pipeline")

    if not profile or profile_builder.overall_confidence(confidence) < 0.30:
        profile, confidence = _ocr_slm_pipeline(image_path)

    overall = profile_builder.overall_confidence(confidence)

    photo_path, photo_b64 = extract_photo(image_path)
    if photo_path:
        profile["Photo_Path"]   = photo_path
        profile["Photo_Base64"] = photo_b64

    profile["_confidence"]     = overall
    profile["_needs_review"]   = overall < profile_builder.CONF_THRESHOLD
    profile["_confidence_map"] = {k: round(v, 2) for k, v in confidence.items()}
    print(f"[CONF] overall={overall:.2f}  needs_review={profile['_needs_review']}")
    return profile


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        print(json.dumps(extract_cnic_info(sys.argv[1]), indent=2))
    else:
        print("Usage: python brain_format_cnic.py <image_path>")
