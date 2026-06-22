"""
VLM-based document extraction using Qwen2-VL-2B-Instruct (GGUF).

Replaces the entire OCR → text → regex → SLM gap-fill chain with a single
image → JSON call.  The VLM sees the 2D layout of the document directly, so
2-column grids, rotated images and mixed-script text (Urdu + English) are all
handled correctly.

Model files required (~1.57 GB total):
  models/vlm/vlm-model.gguf   ← Qwen2-VL-2B-Instruct-Q4_K_M.gguf
  models/vlm/vlm-mmproj.gguf  ← mmproj-Qwen2-VL-2B-Instruct-f16.gguf

Download from: https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
from typing import Dict, Optional, Tuple

# ── Lazy loader ───────────────────────────────────────────────────────────────

_lock = threading.Lock()
_llm  = None


def _model_dir() -> str:
    env = os.environ.get("VLM_MODEL_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "..", "models", "vlm")


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    with _lock:
        if _llm is not None:
            return _llm
        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Qwen2VLChatHandler
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed.\n"
                "Run:  pip install llama-cpp-python"
            )

        mdir        = _model_dir()
        model_path  = os.path.join(mdir, "vlm-model.gguf")
        mmproj_path = os.path.join(mdir, "vlm-mmproj.gguf")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"VLM model not found: {model_path}\n"
                "Download Qwen2-VL-2B-Instruct-Q4_K_M.gguf from "
                "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF"
            )
        if not os.path.exists(mmproj_path):
            raise FileNotFoundError(
                f"VLM mmproj not found: {mmproj_path}\n"
                "Download mmproj-Qwen2-VL-2B-Instruct-f16.gguf from "
                "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF"
            )

        mb = os.path.getsize(model_path) // 1_048_576
        print(f"[VLM] Loading {mb} MB model …")
        handler = Qwen2VLChatHandler(clip_model_path=mmproj_path, verbose=False)
        _llm = Llama(
            model_path=model_path,
            chat_handler=handler,
            n_ctx=2048,
            n_threads=min(os.cpu_count() or 4, 8),
            verbose=False,
        )
        print("[VLM] Model ready.")
        return _llm


# ── Prompts ───────────────────────────────────────────────────────────────────

_CNIC_PROMPT = """\
You are a document OCR assistant. Carefully read every field printed on this \
Pakistani National Identity Card (CNIC) image and return ONLY a single JSON \
object — no markdown, no extra text.

Required JSON structure:
{
  "Full_Name": "",
  "Father_Name": "",
  "Gender": "M or F",
  "Identity_Number": "XXXXX-XXXXXXX-X",
  "DOB": "DD.MM.YYYY",
  "Date_of_Issue": "DD.MM.YYYY",
  "Date_of_Expiry": "DD.MM.YYYY",
  "Country": "Pakistan"
}

Rules:
- All dates must be in DD.MM.YYYY format (e.g. 08.08.2025).
- Identity_Number must be in the exact format XXXXX-XXXXXXX-X (13 digits with hyphens).
- Gender: output only "M" or "F".
- Country is always "Pakistan" for Pakistani CNICs.
- Use empty string "" for any field that is not legible or not present.
- Do NOT guess or invent values — only output what is clearly visible.
"""

_DL_PROMPT = """\
You are a document OCR assistant. Carefully read every field printed on this \
Pakistani Driving License image and return ONLY a single JSON object — \
no markdown, no extra text.

Required JSON structure:
{
  "Full_Name": "",
  "Father_Name": "",
  "Gender": "M or F",
  "License_Number": "",
  "DOB": "DD.MM.YYYY",
  "Date_of_Issue": "DD.MM.YYYY",
  "Date_of_Expiry": "DD.MM.YYYY",
  "Country": "Pakistan",
  "Province": "",
  "Category": ""
}

Rules:
- All dates must be in DD.MM.YYYY format.
- Gender: output only "M" or "F".
- Use empty string "" for any field that is not legible.
- Do NOT guess or invent values — only output what is clearly visible.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _image_b64(image_path: str) -> Tuple[str, str]:
    ext  = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime


def _norm_date(s: str) -> str:
    """Normalise any date variant → DD.MM.YYYY."""
    if not s:
        return s
    # Already correct
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', s):
        return s
    # YYYY-MM-DD or YYYY/MM/DD
    m = re.match(r'^(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})$', s)
    if m:
        return f"{int(m.group(3)):02d}.{int(m.group(2)):02d}.{m.group(1)}"
    # DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r'^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})$', s)
    if m:
        return f"{int(m.group(1)):02d}.{int(m.group(2)):02d}.{m.group(3)}"
    return s


def _norm_cnic(s: str) -> str:
    digits = re.sub(r'\D', '', s)
    if len(digits) >= 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return s


def _parse_json(text: str) -> Optional[dict]:
    """Extract the first JSON object from a model response."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find JSON block
    m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Core VLM call ─────────────────────────────────────────────────────────────

def _call_vlm(image_path: str, prompt: str) -> Optional[dict]:
    b64, mime = _image_b64(image_path)
    llm = _get_llm()
    try:
        resp = llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=512,
            temperature=0.0,
            stop=["</s>", "<|im_end|>", "<|endoftext|>"],
        )
        raw = resp["choices"][0]["message"]["content"]
        print(f"[VLM] Raw response ({len(raw)} chars): {raw[:200]}")
        return _parse_json(raw)
    except Exception as e:
        print(f"[VLM] Inference error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def _build_result(raw: dict, field_specs: list) -> Tuple[Dict, Dict]:
    """
    Convert raw VLM JSON → (profile, confidence).

    field_specs: [(json_key, profile_key, base_confidence), ...]
    """
    profile: Dict[str, str]   = {}
    conf:    Dict[str, float] = {}

    for json_key, profile_key, base_conf in field_specs:
        val = str(raw.get(json_key, "")).strip()
        if val and val not in ("N/A", "null", "None", "n/a"):
            profile[profile_key] = val
            conf[profile_key]    = base_conf
        else:
            profile[profile_key] = ""
            conf[profile_key]    = 0.0

    # Normalise dates
    for key in ("DOB", "Date_of_Issue", "Date_of_Expiry"):
        if profile.get(key):
            profile[key] = _norm_date(profile[key])

    # Normalise CNIC number
    if profile.get("Identity_Number"):
        profile["Identity_Number"] = _norm_cnic(profile["Identity_Number"])

    return profile, conf


_CNIC_FIELDS = [
    ("Full_Name",      "Full_Name",      0.90),
    ("Father_Name",    "Father_Name",    0.90),
    ("Gender",         "Gender",         0.92),
    ("Identity_Number","Identity_Number",0.95),
    ("DOB",            "DOB",            0.92),
    ("Date_of_Issue",  "Date_of_Issue",  0.92),
    ("Date_of_Expiry", "Date_of_Expiry", 0.92),
    ("Country",        "Country",        0.95),
]

_DL_FIELDS = [
    ("Full_Name",      "Full_Name",      0.90),
    ("Father_Name",    "Father_Name",    0.90),
    ("Gender",         "Gender",         0.92),
    ("License_Number", "License_Number", 0.92),
    ("DOB",            "DOB",            0.92),
    ("Date_of_Issue",  "Date_of_Issue",  0.92),
    ("Date_of_Expiry", "Date_of_Expiry", 0.92),
    ("Country",        "Country",        0.95),
    ("Province",       "Province",       0.85),
    ("Category",       "Category",       0.85),
]


def extract_cnic(image_path: str) -> Tuple[Dict, Dict]:
    """Extract CNIC fields from image. Returns (profile, confidence)."""
    raw = _call_vlm(image_path, _CNIC_PROMPT)
    if raw is None:
        return {}, {}
    return _build_result(raw, _CNIC_FIELDS)


def extract_dl(image_path: str) -> Tuple[Dict, Dict]:
    """Extract Driving License fields from image. Returns (profile, confidence)."""
    raw = _call_vlm(image_path, _DL_PROMPT)
    if raw is None:
        return {}, {}
    return _build_result(raw, _DL_FIELDS)


def is_available() -> bool:
    """Return True if the VLM model files are present and llama-cpp-python installed."""
    try:
        mdir = _model_dir()
        return (
            os.path.exists(os.path.join(mdir, "vlm-model.gguf"))
            and os.path.exists(os.path.join(mdir, "vlm-mmproj.gguf"))
        )
    except Exception:
        return False
