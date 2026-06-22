"""
Driving License extraction brain — SLM-first pipeline:
  1. VLM (Qwen2-VL-2B)        — direct image → JSON (if available)
  2. SLM primary extraction    — combined dual-OCR text → LLM → JSON
  3. Regex fallback             — rule-based extraction (no province hardcoding)
  4. Regex supplements SLM     — cross-validate; regex wins on high-confidence fields
  5. Photo extraction
  6. Confidence gate            → _needs_review flag
"""
import base64
import os
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
    h, w    = img.shape[:2]
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1,
                                     minNeighbors=5, minSize=(50, 50))
    if len(faces) > 0:
        x, y, wf, hf = max(faces, key=lambda r: r[2] * r[3])
        mx = wf // 2
        x  = max(0, x - mx);       y  = max(0, y - hf // 2)
        wf = min(img.shape[1] - x, wf + 2 * mx)
        hf = min(img.shape[0] - y, hf * 2)
        cropped = img[y:y + hf, x:x + wf]
    else:
        for x_r, y_r, w_r, h_r in [(0.65, 0.05, 0.30, 0.40),
                                    (0.05, 0.05, 0.30, 0.40)]:
            xs, ys = int(w * x_r), int(h * y_r)
            wc, hc = int(w * w_r), int(h * h_r)
            temp   = img[ys:ys + hc, xs:xs + wc]
            if temp.size > 0:
                cropped = temp
                break
        else:
            cropped = img
    return _enhance_and_save_photo(cropped, output_path)


# ── Dual OCR helper ───────────────────────────────────────────────────────────

def _dual_ocr(image_path: str) -> tuple:
    """
    Run two OCR preprocessing passes and return (bw_text, std_text).
    - B&W Otsu pass:   best for dates, numbers, wavy/patterned backgrounds
    - Standard pass:   best for names (preserves thin strokes like uppercase I)
    Both results are used so the SLM has the richest possible input.
    """
    # Pass 1 — B&W Otsu (DL-specific)
    bw_blocks, bw_engine = ocr_engine.extract_blocks_dl(image_path)
    bw_text = ocr_engine._blocks_to_layout(bw_blocks) if bw_blocks else ""
    if bw_text:
        print(f"[OCR-BW]  {bw_engine} → {len(bw_text)} chars, {len(bw_blocks)} blocks")

    # Pass 2 — Standard adaptive threshold
    std_blocks, std_engine = ocr_engine.extract_blocks(image_path)
    std_text = ocr_engine._blocks_to_layout(std_blocks) if std_blocks else ""
    if std_text:
        print(f"[OCR-STD] {std_engine} → {len(std_text)} chars, {len(std_blocks)} blocks")

    # Debug dump
    try:
        debug_path = os.path.join(os.path.dirname(image_path), '_debug_ocr.txt')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(f"[B&W Otsu]\n{bw_text}\n\n[Standard]\n{std_text}")
    except Exception:
        pass

    return bw_text, std_text


# ── Validate SLM output against OCR text ─────────────────────────────────────

def _ocr_validate_slm(slm_profile: dict, slm_conf: dict,
                      ocr_texts: list) -> tuple:
    """
    Penalize SLM date/number values that don't appear in any OCR pass.
    Prevents hallucinations from overriding correct regex values.
    """
    combined = " ".join(ocr_texts)
    # Date_of_Issue is intentionally excluded: when OCR can't see it (e.g. hand
    # covering the card), the SLM calculates it from DOE — the year won't appear
    # in OCR text and that is correct, not a hallucination.
    for key in ("DOB", "Date_of_Expiry", "License_Number"):
        val = slm_profile.get(key, "")
        if not val:
            continue
        parts = re.split(r'[.\-/]', val)
        years = [p for p in parts if len(p) == 4 and p.isdigit()]
        if years and not any(y in combined for y in years):
            slm_conf[key] = 0.30
    return slm_profile, slm_conf


# ── Merge SLM + regex profiles ────────────────────────────────────────────────

def _merge_profiles(slm_profile: dict, slm_conf: dict,
                    reg_profile: dict, reg_conf: dict) -> tuple:
    """
    Regex is the reliable base — it's validated against actual OCR text.
    SLM supplements ONLY fields where regex confidence < 0.75 (weak/missing).
    SLM confidence is capped at 0.75 to stay below high-confidence regex values.
    """
    # Start from regex (validated, reliable)
    profile = dict(reg_profile)
    conf    = dict(reg_conf)

    for key, s_val in slm_profile.items():
        s_conf = slm_conf.get(key, 0.0)
        r_conf = conf.get(key, 0.0)
        # Only let SLM fill in what regex is weak on
        if s_val and r_conf < 0.75:
            profile[key] = s_val
            conf[key]    = min(s_conf, 0.75)   # cap to avoid overconfidence

    return profile, conf


# ── Normalize & validate profile ──────────────────────────────────────────────

def _normalize(profile: dict, conf: dict, bw_text: str, std_text: str,
               reg_profile: dict, reg_conf: dict) -> tuple:
    """
    Format-normalize, cross-validate, and apply logical fallbacks.
    """
    combined = bw_text + "\n" + std_text

    # Normalize dates to DD.MM.YYYY
    for key in ("DOB", "Date_of_Issue", "Date_of_Expiry"):
        val = profile.get(key, "")
        if val:
            profile[key] = profile_builder._norm_date(val)

    # Guard: Full_Name must not equal Father_Name (SLM hallucinating Father = Name)
    fn     = profile.get("Full_Name", "").lower().strip()
    father = profile.get("Father_Name", "").lower().strip()
    if fn and father and fn == father:
        # Revert Full_Name to regex value
        if reg_profile.get("Full_Name"):
            profile["Full_Name"] = reg_profile["Full_Name"]
            conf["Full_Name"]    = reg_conf.get("Full_Name", 0.75)
        else:
            profile["Full_Name"] = ""
            conf["Full_Name"]    = 0.0
        # Also revert Father_Name — SLM couldn't differentiate; trust regex or clear
        reg_father = reg_profile.get("Father_Name", "")
        if reg_father:
            profile["Father_Name"] = reg_father
            conf["Father_Name"]    = reg_conf.get("Father_Name", 0.75)
        else:
            profile["Father_Name"] = ""
            conf["Father_Name"]    = 0.0

    # Guard: if DOI and DOE share the same year the SLM conflated them — clear DOI
    # so the pipeline's targeted SLM call can recalculate it correctly.
    doe = profile.get("Date_of_Expiry", "")
    doi = profile.get("Date_of_Issue", "")
    if doe and doi and (doi == doe or
                        profile_builder._get_year(doi) == profile_builder._get_year(doe)):
        profile["Date_of_Issue"] = ""
        conf["Date_of_Issue"]    = 0.0

    # Boost confidence when value confirmed in OCR text
    for key in ("License_Number", "DOB", "Date_of_Expiry", "Province", "Category"):
        val = profile.get(key, "")
        if val and val in combined:
            conf[key] = min(1.0, conf.get(key, 0.0) + 0.05)

    # Names: strip stray punctuation, title-case
    for key in ("Full_Name", "Father_Name"):
        val = profile.get(key, "")
        if val:
            val = re.sub(r'[^A-Za-z\s]', ' ', val).strip()
            val = ' '.join(w.capitalize() for w in val.split())
            profile[key] = val

    return profile, conf


# ── Main fallback pipeline ────────────────────────────────────────────────────

def _ocr_slm_pipeline(image_path: str) -> tuple:
    """
    Dual-OCR → SLM primary → regex supplement → normalize.
    Returns (profile, confidence).
    """
    import slm_client

    bw_text, std_text = _dual_ocr(image_path)
    primary_text      = bw_text or std_text

    if not primary_text:
        return {}, {}

    # ── Regex extraction (primary — validated against OCR text) ──────────────
    reg_profile, reg_conf = profile_builder.build_dl_profile(primary_text)

    # Supplement regex names from standard preprocessing (reads thin strokes better)
    if std_text:
        std_reg, std_rc = profile_builder.build_dl_profile(std_text)
        for key in ("Full_Name", "Father_Name"):
            std_val = std_reg.get(key, "")
            std_c   = std_rc.get(key, 0.0)
            cur_val = reg_profile.get(key, "")
            cur_c   = reg_conf.get(key, 0.0)
            if (std_val
                    and std_c >= cur_c
                    and len(std_val.replace(" ", "")) >= len(cur_val.replace(" ", ""))):
                reg_profile[key] = std_val
                reg_conf[key]    = std_c

    print(f"[REGEX] {{{', '.join(f'{k}:{v:.2f}' for k,v in reg_conf.items())}}}")

    # ── SLM: supplements only fields regex couldn't find confidently ──────────
    ocr_texts = [t for t in [bw_text, std_text] if t.strip()]
    slm_profile, slm_conf = slm_client.primary_extract(ocr_texts, "Driving License")

    if slm_profile:
        # Validate SLM dates against OCR (reject hallucinated values)
        slm_profile, slm_conf = _ocr_validate_slm(slm_profile, slm_conf, ocr_texts)
        profile, confidence   = _merge_profiles(slm_profile, slm_conf,
                                                reg_profile, reg_conf)
    else:
        # SLM offline — regex-only + gap-fill
        print("[PIPELINE] SLM offline — regex-only mode")
        profile, confidence = reg_profile, reg_conf

        low_conf = profile_builder.low_confidence_fields(confidence)
        if low_conf:
            print(f"[SLM-GAP] Fields: {low_conf}")
            gap = slm_client.ask_slm(primary_text, low_conf, doc_type="Driving License")
            for k, v in gap.items():
                if v and k in low_conf:
                    profile[k]    = str(v).strip()
                    confidence[k] = 0.65

        overall = profile_builder.overall_confidence(confidence)
        if overall < profile_builder.CONF_THRESHOLD:
            deep = slm_client.full_extract(primary_text, "Driving License")
            for k, v in deep.items():
                if v and confidence.get(k, 0) < profile_builder.CONF_THRESHOLD:
                    profile[k]    = str(v).strip()
                    confidence[k] = 0.70

    # ── Normalize, validate, and apply logical fallbacks ──────────────────────
    profile, confidence = _normalize(profile, confidence, bw_text, std_text,
                                     reg_profile, reg_conf)

    # ── Targeted DOI fill: SLM calculates from DOE when OCR couldn't read it ──
    doi = profile.get("Date_of_Issue", "")
    doe = profile.get("Date_of_Expiry", "")
    if not doi and doe:
        calculated = slm_client.calculate_doi(doe)
        if calculated:
            calc_norm = profile_builder._norm_date(calculated)
            doe_year  = profile_builder._get_year(doe)
            doi_year  = profile_builder._get_year(calc_norm)
            # Only accept if SLM gave a date in a different year from expiry
            if calc_norm != doe and doi_year != doe_year:
                profile["Date_of_Issue"] = calc_norm
                confidence["Date_of_Issue"] = 0.80

    # ── Arithmetic fallback: if DOI still missing, compute from DOE ───────────
    # SLMs often fail date arithmetic; this is a universal calculation, not a
    # province-specific rule: DOI = (DOE_day + 1).(DOE_month).(DOE_year - 5)
    doi = profile.get("Date_of_Issue", "")
    doe = profile.get("Date_of_Expiry", "")
    if not doi and doe:
        try:
            dp = doe.split('.')
            if len(dp) == 3 and len(dp[2]) == 4:
                day, month, year = int(dp[0]), int(dp[1]), int(dp[2])
                _days = [0,31,28,31,30,31,30,31,31,30,31,30,31]
                if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
                    _days[2] = 29
                day += 1
                if day > _days[month]:
                    day, month = 1, month + 1
                    if month > 12:
                        month, year = 1, year + 1
                year -= 5
                profile["Date_of_Issue"] = f"{day:02d}.{month:02d}.{year}"
                confidence["Date_of_Issue"] = 0.78
        except Exception:
            pass

    return profile, confidence


# ── Main entry point ──────────────────────────────────────────────────────────

def extract_dl_info(image_path: str) -> dict:
    print(f"[DL] Processing: {image_path}")

    # Primary path — VLM
    profile, confidence = {}, {}
    try:
        import vlm_extractor
        if vlm_extractor.is_available():
            profile, confidence = vlm_extractor.extract_dl(image_path)
            filled = sum(1 for v in profile.values() if v)
            print(f"[VLM]  Extracted {filled}/{len(profile)} fields")
        else:
            print("[VLM]  Model files missing — using OCR+SLM pipeline")
    except Exception as e:
        print(f"[VLM]  Error ({e}) — using OCR+SLM pipeline")

    if not profile or profile_builder.overall_confidence(confidence) < 0.30:
        profile, confidence = _ocr_slm_pipeline(image_path)

    overall = profile_builder.overall_confidence(confidence)

    # Photo
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
        print(json.dumps(extract_dl_info(sys.argv[1]), indent=2))
    else:
        print("Usage: python brain_format_dl.py <image_path>")
