"""
Phase 2 — Semantic Anchoring via Embeddings.

Matches form field labels to CNIC/DL data keys using cosine similarity
against a hardcoded anchor dictionary.  No LLM involved — runs in <50 ms.

Model: all-MiniLM-L6-v2  (~90 MB, downloaded once, cached locally)
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# ── Lazy model loader ─────────────────────────────────────────────────────────

_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        import os
        # ST_MODELS_DIR is set by launcher when running from bundled EXE
        model_path = os.environ.get("ST_MODELS_DIR", "all-MiniLM-L6-v2")
        print(f"[EMBED] Loading model from: {model_path}")
        _model = SentenceTransformer(model_path)
        print("[EMBED] Model ready.")
    return _model


# ── Anchor dictionary ─────────────────────────────────────────────────────────
# Each CNIC/DL key maps to a list of how that field commonly appears on forms.
# Covers: English labels, placeholder text, field names, abbreviations.

ANCHORS: Dict[str, List[str]] = {
    "Full_Name": [
        "full name", "name", "fullname", "full_name",
        "applicant name", "candidate name", "complete name",
        "your name", "person name", "applicant", "holder name",
        "customer name", "employee name", "subscriber name",
        "name of applicant", "name of person",
    ],
    "Father_Name": [
        "father name", "father's name", "fathers name",
        "father or husband name", "guardian name", "parent name",
        "father", "guardian", "s/o", "son of", "d/o", "daughter of",
        "w/o", "wife of", "relative name", "relation name",
    ],
    "Gender": [
        "gender", "sex", "male female", "male or female",
        "gender identity", "select gender",
    ],
    "Identity_Number": [
        "cnic", "cnic number", "national identity card number",
        "nic", "national id", "identity number", "id number",
        "identity no", "id no", "national registration number",
        "id card number", "identity card", "national identification",
        "national identification number", "citizen id",
        "cnic no", "nic number", "identity card number",
    ],
    "DOB": [
        "date of birth", "dob", "birth date", "birthdate",
        "born on", "born", "birth", "date of birth dd mm yyyy",
        "birthday", "birth day", "date birth", "d.o.b",
    ],
    "Date_of_Issue": [
        "date of issue", "issue date", "issued on", "issued date",
        "doi", "issuance date", "card issue date", "issue",
        "registration date", "date issued",
    ],
    "Date_of_Expiry": [
        "date of expiry", "expiry date", "expiry", "expiration date",
        "valid until", "validity", "doe", "valid through",
        "expires on", "expiration", "valid upto", "card expiry",
        "valid till",
    ],
    "Country": [
        "country", "nationality", "country of origin",
        "citizenship", "country of residence", "nation",
    ],
    "Province": [
        "province", "state", "region", "district",
        "province state", "administrative division",
    ],
    "License_Number": [
        "license number", "licence number", "dl number",
        "driving license number", "license no", "licence no",
        "driving license no", "dl no", "driving licence",
        "license id", "dl", "driving license",
    ],
    "Category": [
        "category", "vehicle category", "vehicle class", "class",
        "license category", "type of vehicle", "vehicle type",
        "licence class", "driving class",
    ],
}

# Flat lookup: anchor phrase → CNIC field key
_FLAT: Dict[str, str] = {
    phrase: key
    for key, phrases in ANCHORS.items()
    for phrase in phrases
}

# Action type map
_ACTION_MAP: Dict[str, str] = {
    "text":            "type_text",
    "email":           "type_text",
    "tel":             "type_text",
    "url":             "type_text",
    "search":          "type_text",
    "password":        "type_text",
    "date":            "set_date",
    "datetime-local":  "set_date",
    "month":           "set_date",
    "number":          "set_number",
    "range":           "set_number",
    "select-one":      "select_option",
    "select":          "select_option",
    "radio":           "click_radio",
    "checkbox":        "check_checkbox",
    "textarea":        "type_textarea",
}


# ── Text helpers ──────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[*:()\[\]{}|/\\_.,-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _field_text(field: dict) -> str:
    """Combine all textual signals from a form field into one query string."""
    parts = [
        field.get("label", ""),
        field.get("placeholder", ""),
        field.get("nearby_text", ""),
        field.get("name", ""),
        field.get("id", ""),
    ]
    return _clean(" ".join(p for p in parts if p))


# ── Exact/substring fast path ─────────────────────────────────────────────────

def _exact_match(query: str) -> Optional[str]:
    """Try direct substring match against anchor phrases first (no GPU needed)."""
    # full phrase match
    for phrase, key in _FLAT.items():
        if phrase == query:
            return key
    # substring: query contains phrase or phrase contains query
    for phrase, key in _FLAT.items():
        if len(phrase) >= 4 and (phrase in query or query in phrase):
            return key
    return None


# ── Value formatter ───────────────────────────────────────────────────────────

def _format_value(value: str, doc_key: str, field: dict) -> str:
    ftype = field.get("type", "text").lower()

    # Date: DD.MM.YYYY → YYYY-MM-DD
    is_date_field = ftype in ("date", "datetime-local", "month") or any(
        kw in (field.get("name", "") + field.get("id", "") + field.get("label", "")).lower()
        for kw in ("date", "dob", "birth", "issue", "expir")
    )
    if is_date_field:
        m = re.match(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", value)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # Number: strip non-digits
    if ftype == "number":
        return re.sub(r"[^\d\-]", "", value)

    # Gender: adapt to available options
    if doc_key == "Gender":
        opts_raw = (
            [o.get("text", "") for o in field.get("options", [])] +
            [r.get("label", "") or r.get("value", "") for r in field.get("radio_options", [])]
        )
        opts = [o.strip().lower() for o in opts_raw if o.strip()]
        if any(o in ("male", "female") for o in opts):
            return "Male" if value in ("M", "Male") else "Female"
        if any(o in ("m", "f") for o in opts):
            return "M" if value in ("M", "Male") else "F"

    return value


# ── Main matching function ────────────────────────────────────────────────────

def match_fields(
    doc_data: dict,
    form_schema: dict,
    threshold: float = 0.38,
) -> List[dict]:
    """
    Match doc_data keys to form fields using cosine similarity.
    Returns fill-action list compatible with agent_form_filler.

    threshold: minimum cosine similarity to accept a match (0-1).
    """
    import numpy as np

    # Strip internal/photo keys from doc data
    clean_doc = {
        k: v for k, v in doc_data.items()
        if v and not k.startswith("_") and k not in ("Photo_Path", "Photo_Base64")
    }
    if not clean_doc:
        return []

    fields = form_schema.get("fields", [])
    if not fields:
        return []

    model = _get_model()

    # Pre-encode all anchor phrases once
    anchor_phrases  = list(_FLAT.keys())
    anchor_vecs     = model.encode(
        anchor_phrases,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    actions: List[dict] = []
    used_ids: set = set()

    for field in fields:
        fid   = field.get("id") or field.get("name") or ""
        ftype = field.get("type", "text").lower()
        query = _field_text(field)

        if not query or fid in used_ids:
            continue

        # ── Fast path: exact/substring match ─────────────────────────────────
        matched_key = _exact_match(query)
        score_used  = 1.0

        # ── Embedding path ────────────────────────────────────────────────────
        if matched_key is None:
            q_vec  = model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            scores = (anchor_vecs @ q_vec.T).flatten()
            best_i = int(np.argmax(scores))
            score_used = float(scores[best_i])

            if score_used >= threshold:
                matched_key = _FLAT[anchor_phrases[best_i]]
            else:
                continue

        value = clean_doc.get(matched_key, "")
        if not value:
            continue

        value  = _format_value(value, matched_key, field)
        action = _ACTION_MAP.get(ftype, "type_text")

        log_method = "exact" if score_used == 1.0 else f"embed({score_used:.2f})"
        print(f"[EMBED] '{query[:40]}' → {matched_key}  [{log_method}]")

        used_ids.add(fid)
        actions.append({
            "field_id":   field.get("id", ""),
            "field_name": field.get("name", ""),
            "field_type": ftype,
            "value":      value,
            "action":     action,
        })

    print(f"[EMBED] Matched {len(actions)}/{len(fields)} fields")
    return actions
