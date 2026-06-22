"""
Form field matching using rapidfuzz (fuzzy) + regex.
Replaces the previous simple substring pattern matching.
"""
import re
from bs4 import BeautifulSoup

try:
    from rapidfuzz import fuzz, process as rfprocess
    RAPIDFUZZ_OK = True
except ImportError:
    RAPIDFUZZ_OK = False
    print("[FormMapper] rapidfuzz not installed — falling back to substring matching")

MATCH_THRESHOLD = 62  # minimum score (0-100) for rapidfuzz

FIELD_PATTERNS = {
    "Full_Name":       ["name", "full name", "fullname", "full_name", "applicant name"],
    "Father_Name":     ["father", "father name", "father_name", "fathers name", "guardian name", "parent name"],
    "Gender":          ["gender", "sex"],
    "Identity_Number": ["cnic", "identity number", "id number", "cnic number", "identity", "nic"],
    "License_Number":  ["license", "licence", "driver license", "dl number", "license no", "licence no"],
    "DOB":             ["date of birth", "dob", "birth date", "birthdate", "date of birth"],
    "Date_of_Issue":   ["date of issue", "issue date", "issue_date", "doi", "issued on"],
    "Date_of_Expiry":  ["date of expiry", "expiry date", "expiry_date", "doe", "expiry", "valid until"],
    "Country":         ["country", "nationality", "nation"],
    "Category":        ["category", "class", "vehicle category", "cat", "license class"],
    "Province":        ["province", "state", "region", "issuing province", "issued by"],
}

GENDER_MAP = {"M": "Male", "F": "Female", "Male": "Male", "Female": "Female"}
FIELD_ORDER = list(FIELD_PATTERNS.keys())

_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _to_iso_date(date_str: str) -> str:
    """Convert any common date format to YYYY-MM-DD for type='date' inputs."""
    s = date_str.strip()
    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # DD-MM-YYYY  or  DD/MM/YYYY  or  DD.MM.YYYY
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # YYYY/MM/DD  or  YYYY.MM.DD
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # DD MMM YYYY  (e.g. 15 Mar 1990)
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", s)
    if m:
        d, mo_str, y = m.group(1), m.group(2).lower()[:3], m.group(3)
        mo = _MONTHS.get(mo_str, "01")
        return f"{y}-{mo}-{d.zfill(2)}"
    return s  # return unchanged if no pattern matched


def _format_for_type(inp_type: str, value: str) -> str:
    """Coerce an extracted value to what the HTML input type expects."""
    t = inp_type.lower()
    if t == "date":
        return _to_iso_date(value)
    if t == "number":
        digits = re.sub(r"[^\d]", "", value)
        return digits if digits else value
    if t == "email":
        return value.lower().strip()
    # text, tel, search, url, month, week, time — use as-is
    return value


def _get_label(inp, soup: BeautifulSoup) -> str:
    """Collect all text hints for a form field and return lowercase string."""
    parts = []
    if inp.get("id"):
        lbl = soup.find("label", {"for": inp["id"]})
        if lbl:
            parts.append(lbl.get_text(strip=True))
    for attr in ("name", "id", "placeholder"):
        val = inp.get(attr, "")
        if val:
            parts.append(val.replace("_", " ").replace("-", " "))
    return " ".join(parts).lower().strip()


def _fuzzy_score(label: str, candidates: list) -> float:
    if not RAPIDFUZZ_OK:
        # Simple substring fallback
        return max((100 if c in label else 0) for c in candidates)
    result = rfprocess.extractOne(label, candidates, scorer=fuzz.partial_ratio)
    return result[1] if result else 0


def _find_best_input(doc_key: str, soup: BeautifulSoup):
    """Return (best_input_tag, score) for a given field key."""
    candidates = FIELD_PATTERNS.get(doc_key, [])
    best_inp   = None
    best_score = MATCH_THRESHOLD

    for inp in soup.find_all(["input", "textarea", "select"]):
        if inp.get("type") in ["submit", "reset", "button", "file", "hidden"]:
            continue
        if not (inp.get("name") or inp.get("id")):
            continue
        label = _get_label(inp, soup)
        if not label:
            continue
        score = _fuzzy_score(label, candidates)
        if score > best_score:
            best_score = score
            best_inp   = inp

    return best_inp, best_score


def fill_soup_form(soup: BeautifulSoup, profile: dict) -> tuple:
    """
    Fill all HTML form fields using rapidfuzz matching.
    Returns (soup, fill_log: list[str]).
    """
    log = []

    for doc_key in FIELD_ORDER:
        value = profile.get(doc_key, "")
        if not value:
            continue
        if doc_key == "Gender":
            value = GENDER_MAP.get(value, value)

        best_inp, score = _find_best_input(doc_key, soup)

        if best_inp is None:
            log.append(f"  NO MATCH  {doc_key}")
            continue

        tag = best_inp.name
        if tag == "input":
            inp_type = best_inp.get("type", "text") or "text"
            if inp_type.lower() == "radio":
                for r in soup.find_all("input", {"type": "radio", "name": best_inp.get("name")}):
                    if r.get("value") == value:
                        r["checked"] = "checked"
            elif inp_type.lower() == "checkbox":
                truthy = str(value).lower() in ("yes", "true", "1", "on", "checked")
                if truthy:
                    best_inp["checked"] = "checked"
            else:
                best_inp["value"] = _format_for_type(inp_type, value)
        elif tag == "textarea":
            best_inp.string = value
        elif tag == "select":
            for opt in best_inp.find_all("option"):
                if opt.get("value") == value or opt.text.strip() == value:
                    opt["selected"] = "selected"
                    break

        field_id = best_inp.get("name") or best_inp.get("id", "")
        log.append(f"  FILLED    {doc_key} → {field_id}  (score={score:.0f})")

    return soup, log


def inject_photo(soup: BeautifulSoup, photo_b64: str) -> BeautifulSoup:
    """Insert extracted photo into the form."""
    if not photo_b64:
        return soup

    selectors = [
        ".extracted-image", ".cnic-preview-card", "#photo-container",
        ".photo-container", '[class*="photo"]', '[class*="image"]',
    ]
    img_tag_html = (
        f'<img src="data:image/jpeg;base64,{photo_b64}" '
        f'style="max-width:150px;max-height:150px;border-radius:10px;'
        f'border:2px solid #0b2b40;display:block;margin:10px auto;" '
        f'alt="Extracted Photo">'
    )

    for sel in selectors:
        container = soup.select_one(sel)
        if container:
            container.clear()
            container.append(BeautifulSoup(img_tag_html, "html.parser"))
            return soup

    # Create new container at top of form
    form_tag = soup.find("form")
    if form_tag:
        div_html = (
            '<div style="text-align:center;margin-bottom:20px;padding:10px;'
            'background:#f0f4f8;border-radius:12px;">'
            '<p style="font-weight:bold;margin-bottom:8px;color:#0b2b40;">Extracted Photo</p>'
            + img_tag_html + "</div>"
        )
        form_tag.insert(0, BeautifulSoup(div_html, "html.parser"))

    return soup
