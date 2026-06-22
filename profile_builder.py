"""
Build a structured profile JSON from raw OCR text using regex + rules.
Returns (profile: dict, confidence: dict) where confidence values are 0.0-1.0.

Fixes applied:
  - Country: skip "of Stay" label words, find actual country name
  - Dates: year-sorted positional assignment (handles 2-column CNIC grid layout)
  - Names: require multi-word, stop before Urdu/non-ASCII, guard Father vs Full
  - Confidence: validated against logical constraints
"""
import re
from typing import Tuple, Dict, List, Optional

CONF_THRESHOLD = 0.70

# ── Core patterns ─────────────────────────────────────────────────────────────

_CNIC_RE    = re.compile(r'\d{5}[\s\-]?\d{7}[\s\-]?\d{1}')
_LICENSE_RE = re.compile(
    r'(?:License|Licence|DL|Driver)[^\n]*?([A-Z0-9#]{2,6}[-]?\d{4,12}[-]?[#\d]{0,6})',
    re.IGNORECASE,
)
# Standalone DL number fallback — covers CNIC-prefix style (Sindh) and
# letter-prefix style (Punjab: PB-123456, KPK: NK-12345, Balochistan, etc.)
_DL_NUM_RE = re.compile(
    r'\b(\d{5}-\d{5,9}-[\d#A-Z]{1,10}'      # CNIC-prefix: 42101-8080603-5#652
    r'|[A-Z]{2,4}[-/]\d{4,12}(?:[-/][\d#A-Z]{1,8})?)\b'  # Letter-prefix: PB-123456-7
)
_DATE_RE    = re.compile(r'\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})\b')
# Text-month date: "11-Dec-2021", "21-Apr-2001", "10-Dec-2026"
_DATE_TXT_RE = re.compile(
    r'\b(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{4})\b',
    re.IGNORECASE,
)
_MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}
# Pattern matching either numeric OR text-month date (used in label patterns below)
_DATE_BOTH = (
    r'(?:\d{1,2}[./\-]'
    r'(?:\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)'
    r'[./\-]\d{4})'
)

# Label-anchored date patterns (secondary — used only when clear)
# `[:\s|]+` handles both classic ":" and spatial " | " separator sequence
_LABEL_DATE = {
    "DOB":            re.compile(rf'(?:D[ae]te?\s+of\s+Birth|DOB|Birth\s+D[ae]te?|D[ae]te?\s+[Oo]f\s+Birt\w*)[:\s|]+\s*({_DATE_BOTH})', re.IGNORECASE),
    "Date_of_Issue":  re.compile(rf'(?:Date\s+of\s+Issu\w*|Issue\s+Date|DOI|Date\s+of\s+[Ii]ss\w*)[:\s|]+\s*({_DATE_BOTH})', re.IGNORECASE),
    "Date_of_Expiry": re.compile(rf'(?:Date\s+of\s+Expir\w*|Expiry\s+Date|Expiry|DOE|Valid\s+(?:Till|Upto|Until))[:\s|]+\s*({_DATE_BOTH})', re.IGNORECASE),
}

# Name patterns — require at least 2 capitalized/alpha words
# Negative lookbehind so "Father Name" doesn't fire _NAME_RE
# `[:\s|]` accepts both classic ": " separators and spatial layout " | " pipes
_NAME_RE   = re.compile(
    r'(?<![A-Za-z])(?<!Father\s)(?<!Father)Nam[eo]?\s*[:\s|]\s*'
    r'([A-Za-z][a-zA-Z]{1,}(?:[^\S\n]+[A-Za-z][a-zA-Z\']{1,}){0,4})',
    re.IGNORECASE,
)
_FATHER_RE = re.compile(
    r"(?:Father|Fathr|[Kk]ath[ao]r\w*)(?:['\s/]*(?:s?\s*Nam[eo]?|Husband))\s*[:\s|]*\s*"
    r'([A-Za-z][a-zA-Z]{1,}(?:[^\S\n]+[A-Za-z][a-zA-Z\']{1,}){0,4})',
    re.IGNORECASE,
)

_GENDER_RE    = re.compile(r'\b(Male|Female)\b', re.IGNORECASE)
_GENDER_MF_RE = re.compile(r'(?:Gender|Sex)\s*[:\s|]\s*([MF])\b', re.IGNORECASE)
# Standalone M/F: appears as isolated token after pipe or newline (spatial layout)
_GENDER_STANDALONE = re.compile(
    r'(?:(?:^|\n|\|)\s*)([MF])(?:\s*(?:\||\n|$))', re.MULTILINE
)

# Country: skip "of Stay" / "of Origin" words, find the actual country
_COUNTRY_RE = re.compile(
    r'Country(?:\s+of\s+\w+)?\s+([A-Z][a-zA-Z]{3,})',
    re.IGNORECASE,
)
_PAKISTAN_RE = re.compile(r'\bPakistan\b', re.IGNORECASE)

_CATEGORY_RE = re.compile(
    r'(?:Category|Class|Vehicle\s+Category)[:\s|]+\s*([A-Za-z0-9,\s|]{1,40})',
    re.IGNORECASE,
)
# Fallback: vehicle-category pattern — licence class letter(s) + vehicle type word
# Covers both Pakistani DL formats and common international abbreviations
_DL_CAT_DIRECT = re.compile(
    r'\b([A-Z]{1,2})\s+(CAR|MC|LTV|HTV|PSV|TRACTOR|MOTORCYCLE|TRUCK|BUS|'
    r'RICKSHAW|MOTOR\s*CYCLE|LIGHT|HEAVY|TAXI|VAN|JEEP)\b',
    re.IGNORECASE,
)
_PROVINCE_RE = re.compile(
    r'(?:Province|State|Region|Issuing\s+Province)[:\s|]+\s*([A-Za-z ]{3,20})',
    re.IGNORECASE,
)
_LABEL_STOP_WORDS = frozenset({
    'name', 'father', 'date', 'issue', 'valid', 'license', 'licence',
    'gender', 'sex', 'province', 'country', 'authority', 'licensing',
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm_date(s: str) -> str:
    if not s:
        return s
    # Text-month: "11-Dec-2021" → "11.12.2021"
    m = re.match(r'^(\d{1,2})[-/\.]([A-Za-z]{3})[a-z]*[-/\.](\d{4})$', s.strip())
    if m:
        month = _MONTH_MAP.get(m.group(2).lower())
        if month:
            return f"{int(m.group(1)):02d}.{month}.{m.group(3)}"
    # Numeric: DD-MM-YYYY or YYYY-MM-DD
    parts = re.split(r'[./\-]', s.strip())
    if len(parts) == 3:
        if len(parts[2]) == 4:
            return f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{parts[2]}"
        if len(parts[0]) == 4:
            return f"{parts[2].zfill(2)}.{parts[1].zfill(2)}.{parts[0]}"
    return s


def _parse_date_tuple(d: str):
    """Return (year, month, day) from numeric or text-month date string, or None."""
    # Text-month: "11-Dec-2021"
    m = re.match(r'^(\d{1,2})[-/]([A-Za-z]{3})[a-z]*[-/](\d{4})$', d.strip())
    if m:
        month = _MONTH_MAP.get(m.group(2).lower())
        if month:
            y, mo, dy = int(m.group(3)), int(month), int(m.group(1))
            if 1950 <= y <= 2060 and 1 <= mo <= 12 and 1 <= dy <= 31:
                return (y, mo, dy)
    # Numeric
    parts = re.split(r'[./\-]', d.strip())
    if len(parts) == 3:
        try:
            if len(parts[2]) == 4:
                y, mo, dy = int(parts[2]), int(parts[1]), int(parts[0])
            elif len(parts[0]) == 4:
                y, mo, dy = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                return None
            if 1950 <= y <= 2060 and 1 <= mo <= 12 and 1 <= dy <= 31:
                return (y, mo, dy)
        except ValueError:
            pass
    return None


def _norm_cnic(s: str) -> str:
    digits = re.sub(r'\D', '', s)
    if len(digits) >= 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return s


def _get_year(date_str: str) -> int:
    """Extract 4-digit year from a date string."""
    parts = re.split(r'[./\-]', date_str.strip())
    for p in parts:
        if len(p) == 4:
            try:
                return int(p)
            except ValueError:
                pass
    return 0


_LABEL_STOP = frozenset({
    'gender', 'sex', 'country', 'nationality', 'identity', 'number',
    'date', 'dete', 'birth', 'issue', 'expiry', 'province', 'license', 'licence',
    'category', 'age', 'email', 'phone', 'address', 'father', 'husband',
    'fatherhusband', 'guardian', 'cnic', 'nic', 'passport', 'of', 'by',
})


def _clean_name(s: str, max_words: int = 4) -> str:
    # Stop at first non-ASCII character (Urdu/Arabic script)
    ascii_only = re.split(r'[^\x00-\x7F]', s)[0]
    words = ascii_only.strip().split()
    # Stop at any word that looks like a field label or is suspiciously short/numeric
    clean: list = []
    for w in words:
        # Strip punctuation before checking stop words so "FatherHusband:" matches "fatherhusband"
        if re.sub(r'\W', '', w).lower() in _LABEL_STOP:
            break
        if re.match(r'^[0-9]+$', w):
            break
        clean.append(w)
    # Drop trailing single-letter OCR noise (e.g. stray "M" from Gender field)
    while clean and re.match(r'^[A-Z]$', clean[-1], re.IGNORECASE):
        clean.pop()
    return " ".join(w.capitalize() for w in clean[:max_words])


# ── Smart date extraction (primary method) ────────────────────────────────────

def _smart_dates(text: str) -> Dict[str, Tuple[str, float]]:
    """
    Extract DOB, Date_of_Issue, Date_of_Expiry robustly.

    Strategy:
    1. Try label-anchored patterns.
    2. Collect all dates from text and sort by chronological value.
    3. Validate logical order: DOB <= Issue <= Expiry.
    4. If out-of-order, override with year-sorted positional values.

    This handles the CNIC 2-column grid where labels (Date of Issue | Date of Expiry)
    appear on one row and values (08.08.2025 | 17.09.2032) appear on the next row,
    causing label-anchored regex to grab the wrong date.
    """
    result: Dict[str, Tuple[str, float]] = {}

    # Pass 1: label-anchored
    for key, pat in _LABEL_DATE.items():
        m = pat.search(text)
        if m:
            result[key] = (_norm_date(m.group(1)), 0.96)

    # Collect ALL dates: numeric and text-month ("11-Dec-2021")
    all_raw = _DATE_RE.findall(text) + _DATE_TXT_RE.findall(text)
    parsed: List[Tuple[int, int, int, str]] = []
    for d in all_raw:
        tup = _parse_date_tuple(d)
        if tup:
            parsed.append((tup[0], tup[1], tup[2], d))

    # Remove duplicates (same year-month-day)
    seen = set()
    unique: List[Tuple[int, int, int, str]] = []
    for item in parsed:
        key_tuple = (item[0], item[1], item[2])
        if key_tuple not in seen:
            seen.add(key_tuple)
            unique.append(item)

    unique.sort(key=lambda x: (x[0], x[1], x[2]))  # sort oldest → newest

    # Fill missing from positional
    if len(unique) >= 3:
        # 3 dates found and in strict order → high confidence
        _d_conf    = 0.92
        pos_dob    = (_norm_date(unique[0][3]),  _d_conf)
        pos_issue  = (_norm_date(unique[-2][3]), _d_conf)
        pos_expiry = (_norm_date(unique[-1][3]), _d_conf)

        if "DOB"            not in result: result["DOB"]            = pos_dob
        if "Date_of_Issue"  not in result: result["Date_of_Issue"]  = pos_issue
        if "Date_of_Expiry" not in result: result["Date_of_Expiry"] = pos_expiry

        # Validate logical order AND uniqueness — fix swaps from label-regex misfire
        # (On CNIC, the 2-column grid causes label-regex to grab wrong date for Expiry)
        dob_y   = _get_year(result["DOB"][0])
        issue_y = _get_year(result["Date_of_Issue"][0])
        expiry_y= _get_year(result["Date_of_Expiry"][0])

        issue_val  = result["Date_of_Issue"][0]
        expiry_val = result["Date_of_Expiry"][0]

        order_ok = (
            dob_y > 0 and issue_y > 0 and expiry_y > 0
            and dob_y <= issue_y
            and issue_y < expiry_y           # strict: Issue must be BEFORE Expiry
            and issue_val != expiry_val      # can't be identical dates
        )
        if not order_ok:
            # If DOB was found by label and is clearly different from Issue/Expiry,
            # keep it (higher confidence); only fix the Issue/Expiry pair.
            if ("DOB" in result
                    and result["DOB"][0] not in (pos_issue[0], pos_expiry[0])):
                result["Date_of_Issue"]  = pos_issue
                result["Date_of_Expiry"] = pos_expiry
            else:
                result["DOB"]            = pos_dob
                result["Date_of_Issue"]  = pos_issue
                result["Date_of_Expiry"] = pos_expiry

    elif len(unique) == 2:
        # DOB + one more → DOB smallest, Expiry largest
        # If DOB was already found by label (conf=0.96), we're more certain about the second date
        doe_conf = 0.88 if "DOB" in result else 0.65
        if "DOB"            not in result: result["DOB"]            = (_norm_date(unique[0][3]), 0.65)
        if "Date_of_Expiry" not in result: result["Date_of_Expiry"] = (_norm_date(unique[1][3]), doe_conf)

    elif len(unique) == 1:
        if "DOB" not in result:
            result["DOB"] = (_norm_date(unique[0][3]), 0.55)

    return result


# ── Country extraction ────────────────────────────────────────────────────────

def _extract_country(text: str) -> Tuple[str, float]:
    # Pakistani CNICs always say "Pakistan" — direct search is most reliable
    if _PAKISTAN_RE.search(text):
        return "Pakistan", 0.95

    # General regex — skip the "of Stay" / "of Origin" label words
    m = _COUNTRY_RE.search(text)
    if m:
        val = m.group(1).strip()
        if val.lower() not in ('of', 'stay', 'the', 'a', 'an', 'origin'):
            return val.capitalize(), 0.80

    return "Pakistan", 0.95


# ── Spatial layout parser ─────────────────────────────────────────────────────

_SPATIAL_NAME_LABEL   = re.compile(r'^nam[eo]?$', re.IGNORECASE)
_SPATIAL_FATHER_LABEL = re.compile(r'(?:father|fathr|[Kk]ath\w*)', re.IGNORECASE)
_SPATIAL_NAME_VALUE   = re.compile(r'^[A-Za-z][A-Za-z\s\':!,\-\.]{4,50}$')


_FATHER_VALUE_PREFIX = re.compile(
    r'(?:Father|Fathr|[Kk]ath\w*)\s*(?:/?\s*(?:Husband|Nam[eo]?))?\s*[:\s]\s*',
    re.IGNORECASE,
)


def _spatial_names(text: str) -> Dict[str, Tuple[str, float]]:
    """
    Parse "Label | Value" lines from spatial layout text.
    Returns partial dict with Full_Name and/or Father_Name where found.
    """
    result: Dict[str, Tuple[str, float]] = {}
    for line in text.split('\n'):
        if '|' not in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        for i, label_raw in enumerate(parts[:-1]):
            label     = label_raw.strip()
            value_raw = parts[i + 1].strip()

            # Special case: OCR merges "Name: | FatherHusband: MUHAMMAD SHAHID" on one row.
            # The VALUE itself starts with "Father/Husband:" → extract father name from it.
            if _FATHER_VALUE_PREFIX.match(value_raw):
                father_val = _FATHER_VALUE_PREFIX.sub('', value_raw).strip()
                father_clean = _clean_name(re.sub(r'[^A-Za-z\s]', ' ', father_val))
                if father_clean and len(father_clean.split()) >= 1:
                    result['Father_Name'] = (father_clean, 0.85)
                continue

            # Clean value: remove stray punctuation, keep alpha+space
            value = re.sub(r'[^A-Za-z\s]', ' ', value_raw).strip()
            value = ' '.join(value.split())
            if len(value.split()) < 2:
                continue
            # Father name — label contains "ather", "fathr", "kathori" etc.
            if _SPATIAL_FATHER_LABEL.search(label):
                clean = _clean_name(value)
                if clean:
                    result['Father_Name'] = (clean, 0.82)
            # Full name — label is exactly "name"/"namo" without father keywords
            elif _SPATIAL_NAME_LABEL.match(label) or (
                    re.search(r'\bnam[eo]?\b', label, re.IGNORECASE)
                    and not _SPATIAL_FATHER_LABEL.search(label)):
                clean = _clean_name(value)
                if clean:
                    result['Full_Name'] = (clean, 0.82)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def build_cnic_profile(text: str) -> Tuple[Dict, Dict]:
    profile: Dict[str, str]   = {}
    conf:    Dict[str, float] = {}

    # ── Identity Number ───────────────────────────────────────────────────────
    m = _CNIC_RE.search(text)
    if m:
        profile["Identity_Number"] = _norm_cnic(m.group())
        conf["Identity_Number"]    = 0.95
    else:
        profile["Identity_Number"] = ""
        conf["Identity_Number"]    = 0.0

    # ── Dates (smart extraction) ──────────────────────────────────────────────
    dates = _smart_dates(text)
    for key in ("DOB", "Date_of_Issue", "Date_of_Expiry"):
        if key in dates:
            profile[key] = dates[key][0]
            conf[key]    = dates[key][1]
        else:
            profile[key] = ""
            conf[key]    = 0.0

    # ── Father Name (before Full Name to avoid cross-contamination) ───────────
    mf = _FATHER_RE.search(text)
    if mf:
        profile["Father_Name"] = _clean_name(mf.group(1))
        conf["Father_Name"]    = 0.82 if len(profile["Father_Name"].split()) >= 2 else 0.55
    else:
        profile["Father_Name"] = ""
        conf["Father_Name"]    = 0.0

    # ── Full Name ─────────────────────────────────────────────────────────────
    father_pos = text.find(mf.group(0)) if mf else len(text)
    search_text = text[:father_pos] if father_pos > 50 else text
    mn = _NAME_RE.search(search_text)
    if not mn:
        mn = _NAME_RE.search(text)
    if mn:
        name_val = _clean_name(mn.group(1))
        if name_val != profile["Father_Name"] and len(name_val.split()) >= 2:
            profile["Full_Name"] = name_val
            conf["Full_Name"]    = 0.82
        elif len(name_val.split()) == 1:
            profile["Full_Name"] = name_val
            conf["Full_Name"]    = 0.40
        else:
            profile["Full_Name"] = name_val
            conf["Full_Name"]    = 0.60
    else:
        profile["Full_Name"] = ""
        conf["Full_Name"]    = 0.0

    # ── Spatial layout supplement: override regex if spatial parsing does better ──
    spatial = _spatial_names(text)
    if spatial.get("Full_Name") and conf.get("Full_Name", 0) < 0.80:
        val, c = spatial["Full_Name"]
        if len(val.split()) >= 2:
            profile["Full_Name"] = val
            conf["Full_Name"]    = c
    if spatial.get("Father_Name") and conf.get("Father_Name", 0) < 0.80:
        val, c = spatial["Father_Name"]
        if len(val.split()) >= 2:
            profile["Father_Name"] = val
            conf["Father_Name"]    = c

    # ── Gender ────────────────────────────────────────────────────────────────
    mg = _GENDER_RE.search(text) or _GENDER_MF_RE.search(text)
    if mg:
        g = mg.group(1).lower()
        profile["Gender"] = "M" if g in ("m", "male") else "F"
        conf["Gender"]    = 0.90
    else:
        # Spatial layout fallback: look for standalone M or F token
        ms = _GENDER_STANDALONE.search(text)
        if ms:
            profile["Gender"] = ms.group(1).upper()
            conf["Gender"]    = 0.72
        else:
            profile["Gender"] = ""
            conf["Gender"]    = 0.0

    # ── Country ───────────────────────────────────────────────────────────────
    country, country_conf = _extract_country(text)
    profile["Country"] = country
    conf["Country"]    = country_conf

    return profile, conf


def build_dl_profile(text: str) -> Tuple[Dict, Dict]:
    profile: Dict[str, str]   = {}
    conf:    Dict[str, float] = {}

    # License Number — try label-anchored first, then standalone format
    m = _LICENSE_RE.search(text) or _DL_NUM_RE.search(text)
    if m:
        profile["License_Number"] = m.group(1).strip()
        conf["License_Number"]    = 0.95
    else:
        profile["License_Number"] = ""
        conf["License_Number"]    = 0.0

    # Father Name first
    mf = _FATHER_RE.search(text)
    if mf:
        profile["Father_Name"] = _clean_name(mf.group(1))
        conf["Father_Name"]    = 0.95 if len(profile["Father_Name"].split()) >= 2 else 0.60
    else:
        profile["Father_Name"] = ""
        conf["Father_Name"]    = 0.0

    # Full Name
    father_pos  = text.find(mf.group(0)) if mf else len(text)
    search_text = text[:father_pos] if father_pos > 50 else text
    mn = _NAME_RE.search(search_text) or _NAME_RE.search(text)
    if mn:
        name_val = _clean_name(mn.group(1))
        if name_val != profile["Father_Name"] and len(name_val.split()) >= 2:
            profile["Full_Name"] = name_val
            conf["Full_Name"]    = 0.95
        else:
            profile["Full_Name"] = name_val
            conf["Full_Name"]    = 0.55
    else:
        profile["Full_Name"] = ""
        conf["Full_Name"]    = 0.0

    # Spatial layout supplement for names
    spatial = _spatial_names(text)
    if spatial.get("Full_Name") and conf.get("Full_Name", 0) < 0.90:
        val, c = spatial["Full_Name"]
        if len(val.split()) >= 2:
            profile["Full_Name"] = val
            conf["Full_Name"]    = 0.95
    if spatial.get("Father_Name") and conf.get("Father_Name", 0) < 0.90:
        val, c = spatial["Father_Name"]
        if len(val.split()) >= 1:
            profile["Father_Name"] = val
            conf["Father_Name"]    = 0.95

    # All-caps name fallback: DL often prints "FIRSTNAME | LASTNAME" on its own
    # row without a "Name:" label — join parts, detect, use as Full Name.
    _DL_NAME_SKIP = frozenset({
        'license', 'licence', 'driving', 'dl', 'category', 'province',
        'authority', 'police', 'valid', 'motor', 'vehicle', 'pakistan',
    })
    if not profile.get("Full_Name") or conf.get("Full_Name", 0) < 0.75:
        for line in text.split('\n'):
            joined = re.sub(r'\s*\|\s*', ' ', line).strip()
            if re.match(r'^[A-Z]{2,}(?:\s+[A-Z]{2,}){1,4}$', joined):
                words_lower = {w.lower() for w in joined.split()}
                if not words_lower.intersection(_DL_NAME_SKIP):
                    clean = _clean_name(joined)
                    if clean and len(clean.split()) >= 2:
                        profile["Full_Name"] = clean
                        conf["Full_Name"]    = 0.82
                        break

    # Gender — only from explicit label ("Male"/"Female"/"Gender: M"); Sindh DL
    # has no gender field, so skip standalone M/F (would fire on "M CAR" category)
    mg = _GENDER_RE.search(text) or _GENDER_MF_RE.search(text)
    if mg:
        g = mg.group(1).lower()
        profile["Gender"] = "M" if g in ("m", "male") else "F"
        conf["Gender"]    = 0.92
    else:
        profile["Gender"] = ""
        conf["Gender"]    = 0.0

    # Dates
    dates = _smart_dates(text)
    for key in ("DOB", "Date_of_Issue", "Date_of_Expiry"):
        if key in dates:
            profile[key] = dates[key][0]
            conf[key]    = dates[key][1]
        else:
            profile[key] = ""
            conf[key]    = 0.0

    # Category — label-anchored first, then direct vehicle-type pattern
    m = _CATEGORY_RE.search(text)
    if m:
        cat = re.sub(r'\s*\|\s*', ' ', m.group(1)).strip()
        cat_words = []
        for w in cat.split():
            if w.lower() in _LABEL_STOP_WORDS:
                break
            cat_words.append(w)
        profile["Category"] = ' '.join(cat_words[:5]).strip()
        conf["Category"]    = 0.95 if profile["Category"] else 0.0
    else:
        mc = _DL_CAT_DIRECT.search(text)
        if mc:
            profile["Category"] = f"{mc.group(1).upper()} {mc.group(2).upper()}"
            conf["Category"]    = 0.90
        else:
            profile["Category"] = ""
            conf["Category"]    = 0.0

    # Province
    m = _PROVINCE_RE.search(text)
    if m:
        profile["Province"] = m.group(1).strip()
        conf["Province"]    = 0.95
    else:
        profile["Province"] = ""
        conf["Province"]    = 0.0

    # Country
    country, country_conf = _extract_country(text)
    profile["Country"] = country
    conf["Country"]    = country_conf

    return profile, conf


# ── Scoring ───────────────────────────────────────────────────────────────────

def overall_confidence(conf: Dict) -> float:
    if not conf:
        return 0.0
    # Only average fields we actually extracted (skip 0.0 = unknown/missing)
    values = [v for v in conf.values() if v > 0.0]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def low_confidence_fields(conf: Dict, threshold: float = CONF_THRESHOLD) -> list:
    return [k for k, v in conf.items() if v < threshold]
