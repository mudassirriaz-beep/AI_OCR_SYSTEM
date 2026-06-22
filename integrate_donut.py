"""
DONUT inference integration — drop-in replacement for brain_format_cnic/dl.

Loads the fine-tuned model lazily on first call.
Falls back to legacy OCR pipeline if the model is not found.

Public API (same signature as brain_format_cnic / brain_format_dl):
    extract_cnic_info(image_path) -> dict
    extract_dl_info(image_path)   -> dict
    extract_card_info(image_path) -> dict   # auto-detects doc type

Internal keys in the returned dict:
    _confidence   : float  0‑1
    _needs_review : bool
    doc_type      : "CNIC" | "DL"
"""

import json
import re
import os
import sys
from pathlib import Path

import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

MODEL_DIR  = BASE_DIR / "models" / "donut_round5"
TASK_START = "<s_parse>"
TASK_END   = "</s_parse>"
MAX_LENGTH = 512
CONFIDENCE_THRESHOLD = 0.70   # below this → _needs_review = True

_processor = None
_model     = None
_device    = None


def _load_model():
    global _processor, _model, _device
    if _model is not None:
        return True
    if not MODEL_DIR.exists():
        return False
    try:
        _processor = DonutProcessor.from_pretrained(str(MODEL_DIR))
        _model     = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR))
        _device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _model.to(_device).eval()
        return True
    except Exception as e:
        print(f"[DONUT] Failed to load model: {e}")
        return False


def _run_inference(image_path: str) -> dict:
    img = Image.open(image_path).convert("RGB")
    pv  = _processor(img, return_tensors="pt").pixel_values.to(_device)

    start_id      = _processor.tokenizer.convert_tokens_to_ids([TASK_START])[0]
    decoder_input = torch.tensor([[start_id]], device=_device)

    with torch.no_grad():
        out = _model.generate(
            pv,
            decoder_input_ids=decoder_input,
            max_length=MAX_LENGTH,
            num_beams=4,
            early_stopping=True,
            pad_token_id=_processor.tokenizer.pad_token_id,
            eos_token_id=_processor.tokenizer.eos_token_id,
        )

    pred = _processor.tokenizer.decode(out[0], skip_special_tokens=False)
    return _parse_output(pred)


def _parse_output(pred: str) -> dict:
    # Find the LAST task-start token and extract JSON up to first task-end
    last_start = pred.rfind(TASK_START)
    if last_start >= 0:
        after = pred[last_start + len(TASK_START):].strip()
        end   = after.find(TASK_END)
        candidate = after[:end].strip() if end >= 0 else after.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Fallback: find first balanced JSON object
    m = re.search(r'\{[^}]*\}', pred, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Last resort: greedy match
    m2 = re.search(r'\{.*\}', pred, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group())
        except json.JSONDecodeError:
            pass
    return {}


def _compute_confidence(fields: dict, expected_fields: list[str]) -> float:
    """Fraction of expected fields that were extracted with a non-empty value."""
    if not expected_fields:
        return 0.0
    filled = sum(1 for f in expected_fields if fields.get(f, "").strip())
    return filled / len(expected_fields)


CNIC_FIELDS = ["Full_Name", "Father_Name", "Gender", "Identity_Number",
               "DOB", "Date_of_Issue", "Date_of_Expiry", "Country"]
DL_FIELDS   = ["Full_Name", "Father_Name", "Gender", "License_Number",
               "DOB", "Date_of_Issue", "Date_of_Expiry", "Country", "Category", "Province"]


def extract_card_info(image_path: str) -> dict:
    """
    Auto-detect doc type and extract all fields using DONUT.
    Falls back to legacy OCR pipeline when model is unavailable.
    """
    if not _load_model():
        # Legacy fallback
        try:
            from brain_format_cnic import extract_cnic_info
            return extract_cnic_info(image_path)
        except Exception:
            return {"error": "DONUT model not found and legacy OCR failed"}

    raw = _run_inference(image_path)
    if not raw:
        return {"error": "DONUT returned empty output"}

    doc_type = raw.get("doc_type", "").upper()
    if "DL" in doc_type or "LICENSE" in doc_type or "DRIVING" in doc_type:
        doc_type   = "DL"
        exp_fields = DL_FIELDS
    else:
        doc_type   = "CNIC"
        exp_fields = CNIC_FIELDS

    result = {"doc_type": doc_type}
    for field in exp_fields:
        result[field] = str(raw.get(field, "")).strip()

    conf   = _compute_confidence(result, exp_fields)
    result["_confidence"]   = conf
    result["_needs_review"] = conf < CONFIDENCE_THRESHOLD
    return result


def extract_cnic_info(image_path: str) -> dict:
    """CNIC extraction. Matches signature of brain_format_cnic.extract_cnic_info."""
    if not _load_model():
        from brain_format_cnic import extract_cnic_info as _legacy
        return _legacy(image_path)

    raw = _run_inference(image_path)
    result = {"doc_type": "CNIC"}
    for field in CNIC_FIELDS:
        result[field] = str(raw.get(field, "")).strip()

    conf   = _compute_confidence(result, CNIC_FIELDS)
    result["_confidence"]   = conf
    result["_needs_review"] = conf < CONFIDENCE_THRESHOLD
    return result


def extract_dl_info(image_path: str) -> dict:
    """DL extraction. Matches signature of brain_format_dl.extract_dl_info."""
    if not _load_model():
        from brain_format_dl import extract_dl_info as _legacy
        return _legacy(image_path)

    raw = _run_inference(image_path)
    result = {"doc_type": "DL"}
    for field in DL_FIELDS:
        result[field] = str(raw.get(field, "")).strip()

    conf   = _compute_confidence(result, DL_FIELDS)
    result["_confidence"]   = conf
    result["_needs_review"] = conf < CONFIDENCE_THRESHOLD
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python integrate_donut.py <image_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"\nExtracting from: {path}")
    result = extract_card_info(path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
