"""
Agent 2 — Field Mapper  (Semantic Edition)

Pipeline:
  Phase 1  Form topology already extracted by agent_form_inspector.py
  Phase 2  Cosine similarity via all-MiniLM-L6-v2  (semantic_mapper.py)
  Phase 3  Micro-prompt SLM for value normalisation only (optional)
  Phase 4  Return fill-action list → agent_form_filler.py

No LLM is used for structural decisions.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from semantic_mapper import match_fields as _semantic_match

LLM_URL     = os.environ.get("LLM_URL", "http://localhost:8080")
MODEL       = "default"
TIMEOUT     = 60
MAX_RETRIES = 2

# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
    s = requests.Session()
    r = Retry(total=MAX_RETRIES, backoff_factor=0.5,
              status_forcelist=[500, 502, 503, 504],
              allowed_methods=["POST", "GET"])
    a = HTTPAdapter(max_retries=r)
    s.mount("http://", a)
    s.mount("https://", a)
    return s

_session = _make_session()


def _llm_up() -> bool:
    try:
        return _session.get(f"{LLM_URL}/health", timeout=3).status_code == 200
    except Exception:
        return False


# ── Phase 3: Micro-prompt for value normalisation only ───────────────────────

_NORM_RULES = {
    "date":   "Convert this date value to YYYY-MM-DD format. Return ONLY the formatted date, nothing else.",
    "number": "Extract only the digits from this value. Return ONLY the number, nothing else.",
    "upper":  "Convert this text to UPPERCASE. Return ONLY the result, nothing else.",
    "title":  "Convert this text to Title Case. Return ONLY the result, nothing else.",
}


def _normalize_via_slm(value: str, rule_key: str) -> str:
    """
    Phase 3: Ask SLM to normalise a single value.
    Only called for edge cases that _format_value() could not handle.
    """
    if not _llm_up():
        return value

    rule = _NORM_RULES.get(rule_key, "")
    if not rule:
        return value

    prompt = f"{rule}\nInput: {value}\nOutput:"
    try:
        resp = _session.post(
            f"{LLM_URL}/v1/completions",
            json={"model": MODEL, "prompt": prompt,
                  "max_tokens": 32, "temperature": 0.0, "stream": False},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
        text = result.get("choices", [{}])[0].get("text", "").strip()
        if text:
            return text.split("\n")[0].strip()
    except Exception as e:
        print(f"[MAPPER] SLM normalise error: {e}")

    return value


# ── Main entry point ──────────────────────────────────────────────────────────

def map_fields(doc_data: dict, form_schema: dict) -> List[dict]:
    """
    Phase 2 + 3: Match document data to form fields.

    1. semantic_mapper does cosine-similarity matching (no LLM).
    2. Optionally micro-prompt SLM for edge-case value normalisation.
    3. Return fill-action list.
    """
    actions = _semantic_match(doc_data, form_schema)

    if not actions:
        print("[MAPPER] Semantic match returned 0 actions — trying rule fallback")
        actions = _rule_fallback(doc_data, form_schema)

    return actions


# ── Rule-based fallback (no external dependencies) ───────────────────────────

_HINTS = {
    "Full_Name":       ["name", "full name", "fullname", "applicant"],
    "Father_Name":     ["father", "guardian", "parent", "s/o", "d/o"],
    "Gender":          ["gender", "sex"],
    "Identity_Number": ["cnic", "identity", "nic", "id number", "national"],
    "License_Number":  ["license", "licence", "dl number"],
    "DOB":             ["date of birth", "dob", "birth date", "birthdate"],
    "Date_of_Issue":   ["date of issue", "issue date", "doi", "issued"],
    "Date_of_Expiry":  ["expiry", "expiry date", "doe", "valid until"],
    "Country":         ["country", "nationality"],
    "Category":        ["category", "class", "vehicle"],
    "Province":        ["province", "state", "region"],
}

_ACTION_MAP = {
    "text": "type_text", "email": "type_text", "tel": "type_text",
    "url": "type_text", "search": "type_text", "password": "type_text",
    "date": "set_date", "datetime-local": "set_date", "month": "set_date",
    "number": "set_number", "range": "set_number",
    "select-one": "select_option", "select": "select_option",
    "radio": "click_radio",
    "checkbox": "check_checkbox",
    "textarea": "type_textarea",
}


def _fmt_fallback(value: str, doc_key: str, field: dict) -> str:
    ftype = field.get("type", "text").lower()
    if ftype in ("date", "datetime-local", "month") or "date" in (
        field.get("name", "") + field.get("id", "") + field.get("label", "")
    ).lower():
        m = re.match(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", value)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    if ftype == "number":
        return re.sub(r"[^\d\-]", "", value)
    if doc_key == "Gender":
        opts = [o.get("text", "").strip().lower() for o in field.get("options", [])]
        opts += [r.get("label", "").strip().lower() for r in field.get("radio_options", [])]
        if any(o in ("male", "female") for o in opts):
            return "Male" if value in ("M", "Male") else "Female"
        if any(o in ("m", "f") for o in opts):
            return "M" if value in ("M", "Male") else "F"
    return value


def _rule_fallback(doc_data: dict, form_schema: dict) -> List[dict]:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None

    clean_doc = {
        k: v for k, v in doc_data.items()
        if v and not k.startswith("_") and k not in ("Photo_Path", "Photo_Base64")
    }

    actions = []
    used_ids: set = set()

    for doc_key, hints in _HINTS.items():
        value = clean_doc.get(doc_key, "")
        if not value:
            continue

        best_field = None
        best_score = 55

        for f in form_schema.get("fields", []):
            fid = f.get("id") or f.get("name") or ""
            if fid in used_ids:
                continue
            label = " ".join([
                f.get("label", ""), f.get("name", ""),
                f.get("id", ""), f.get("placeholder", ""),
                f.get("nearby_text", ""),
            ]).lower()

            if fuzz:
                score = max(fuzz.partial_ratio(h, label) for h in hints)
            else:
                score = max((100 if h in label else 0) for h in hints)

            if score > best_score:
                best_score = score
                best_field = f

        if best_field is None:
            continue

        ftype  = best_field.get("type", "text").lower()
        action = _ACTION_MAP.get(ftype, "type_text")
        fmtval = _fmt_fallback(value, doc_key, best_field)
        fid    = best_field.get("id") or best_field.get("name") or ""
        used_ids.add(fid)

        actions.append({
            "field_id":   best_field.get("id", ""),
            "field_name": best_field.get("name", ""),
            "field_type": ftype,
            "value":      fmtval,
            "action":     action,
        })

    print(f"[MAPPER] Rule fallback produced {len(actions)} actions")
    return actions


if __name__ == "__main__":
    sample_doc = {
        "Full_Name": "Ahmed Ali Khan",
        "Father_Name": "Ghulam Ali",
        "Gender": "M",
        "Identity_Number": "42301-1234567-1",
        "DOB": "15.03.1990",
        "Date_of_Issue": "01.01.2020",
        "Date_of_Expiry": "01.01.2030",
        "Country": "Pakistan",
    }
    sample_schema = {"fields": [
        {"tag": "input", "type": "text",      "id": "fullName",   "name": "fullName",   "label": "Full Name",     "placeholder": "", "options": [], "radio_options": []},
        {"tag": "input", "type": "date",      "id": "dob",        "name": "dob",        "label": "Date of Birth", "placeholder": "", "options": [], "radio_options": []},
        {"tag": "input", "type": "text",      "id": "cnic",       "name": "cnic",       "label": "CNIC Number",   "placeholder": "", "options": [], "radio_options": []},
        {"tag": "select","type": "select-one","id": "gender",     "name": "gender",     "label": "Gender",        "placeholder": "", "options": [{"value":"Male","text":"Male"},{"value":"Female","text":"Female"}], "radio_options": []},
    ]}
    result = map_fields(sample_doc, sample_schema)
    print(json.dumps(result, indent=2, ensure_ascii=False))
