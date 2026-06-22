"""
SLM client — llamafile (OpenAI-compatible API on port 8080).
Uses a persistent session with retry logic to prevent ECONNRESET on large models.
"""
import json
import os
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LLM_URL     = os.environ.get("LLM_URL", "http://localhost:8080")
MODEL       = os.environ.get("LLM_MODEL", "model.gguf")
TIMEOUT     = 180
MAX_RETRIES = 3

# ── Persistent session with automatic retry on connection errors ──────────────

def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

_session = _make_session()


def _ollama_running() -> bool:
    """Health check — works for both llamafile (/health) and llama-cpp-python server (/v1/models)."""
    for path in ("/health", "/v1/models"):
        try:
            r = _session.get(f"{LLM_URL}{path}", timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
    return False


def _parse_json(text: str) -> dict:
    """Extract first JSON object or array from a string."""
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    m = re.search(r'(\{.*?\}|\[.*?\])', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


def _stream_ollama(prompt: str, attempt: int = 0) -> str:
    """
    Stream tokens from llamafile /v1/completions (OpenAI-compatible SSE)
    and collect the full response text.
    """
    try:
        resp = _session.post(
            f"{LLM_URL}/v1/completions",
            json={
                "model":       MODEL,
                "prompt":      prompt,
                "max_tokens":  512,
                "temperature": 0.0,
                "stream":      True,
            },
            stream=True,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()

        parts = []
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if line.startswith("data: "):
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    for choice in chunk.get("choices", []):
                        parts.append(choice.get("text", ""))
                except json.JSONDecodeError:
                    continue
        return "".join(parts)

    except (
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ConnectionError,
        ConnectionResetError,
    ) as e:
        if attempt < MAX_RETRIES - 1:
            wait = 2 ** attempt
            print(f"[SLM] Connection reset (attempt {attempt+1}/{MAX_RETRIES}), retrying in {wait}s: {e}")
            time.sleep(wait)
            return _stream_ollama(prompt, attempt + 1)
        raise

    except requests.exceptions.Timeout:
        if attempt < MAX_RETRIES - 1:
            print(f"[SLM] Timeout (attempt {attempt+1}/{MAX_RETRIES}), retrying…")
            return _stream_ollama(prompt, attempt + 1)
        raise


def _build_prompt(ocr_text: str, fields: list, doc_type: str) -> str:
    fields_str = ", ".join(fields)
    return (
        f"You are extracting fields from a scanned {doc_type} document.\n"
        f"OCR text: {ocr_text}\n\n"
        f"Extract ONLY these fields: {fields_str}\n"
        f"Rules: Dates in DD.MM.YYYY format. Gender as M or F.\n"
        f"Return ONLY a JSON object with exactly these keys, nothing else.\n"
        f"JSON:"
    )


def ask_slm(ocr_text: str, missing_fields: list, doc_type: str = "CNIC") -> dict:
    """
    Ask llamafile to fill low-confidence fields.
    Returns {field: value} or {} if server is offline/errors.
    """
    if not missing_fields:
        return {}
    if not _ollama_running():
        print("[SLM] llamafile not running — rules-only output")
        return {}

    prompt = _build_prompt(ocr_text, missing_fields, doc_type)
    print(f"[SLM] llamafile queried for: {missing_fields}")

    try:
        raw    = _stream_ollama(prompt)
        result = _parse_json(raw)
        if result:
            print(f"[SLM] llamafile returned: {list(result.keys())}")
            return result
        print(f"[SLM] No parseable JSON in response: {raw[:120]}")
    except requests.exceptions.Timeout:
        print("[SLM] llamafile timed out — model may be loading, try again")
    except requests.exceptions.ConnectionError as e:
        print(f"[SLM] Cannot reach llamafile after {MAX_RETRIES} retries: {e}")
    except requests.exceptions.HTTPError as e:
        print(f"[SLM] llamafile HTTP error: {e}")
    except Exception as e:
        print(f"[SLM] Unexpected error: {e}")

    return {}


CNIC_FIELDS = [
    "Full_Name", "Father_Name", "Gender", "Identity_Number",
    "DOB", "Date_of_Issue", "Date_of_Expiry", "Country",
]
DL_FIELDS = [
    "Full_Name", "Father_Name", "Gender", "License_Number",
    "DOB", "Date_of_Expiry", "Country", "Category", "Province",
]
# Date_of_Issue is intentionally excluded from SLM primary extraction:
# SLMs hallucinate DOI by copying context from other cards.
# DOI is derived from OCR (regex) when visible, or via calculate_doi(doe) when not.


def primary_extract(ocr_texts: list, doc_type: str) -> tuple:
    """
    SLM as primary extractor — receives multiple OCR passes and returns
    (profile, confidence).  Works for any document format without hardcoded rules.
    """
    if not _ollama_running():
        return {}, {}

    combined = "\n\n".join(
        f"[Pass {i+1}]\n{t.strip()}" for i, t in enumerate(ocr_texts) if t.strip()
    )
    fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS

    doi_hint = (
        "\n- Date_of_Issue: Pakistani driving licenses are valid for exactly 5 years."
        "\n  If Issue Date is not clearly visible in the OCR text, calculate it:"
        "\n  Issue Date = (Expiry Day + 1).(Expiry Month).(Expiry Year - 5)"
        "\n  Example: Valid Upto = 10.12.2026 → Issue Date = 11.12.2021"
        "\n  CRITICAL: Issue Date year must be 5 years BEFORE Expiry Date year."
        if doc_type != "CNIC" else ""
    )

    prompt = (
        f"You are extracting fields from a scanned Pakistani {doc_type} document.\n"
        f"The OCR text may have errors — read garbled text intelligently.\n"
        f"Multiple preprocessing passes are provided; use the clearest reading of each field.\n\n"
        f"{combined}\n\n"
        f"Extract these fields: {', '.join(fields)}\n\n"
        f"Rules:\n"
        f"- Dates → DD.MM.YYYY  (example: 11.12.2021)\n"
        f"- Names → Title Case  (example: Muhammad Shahid)\n"
        f"- CNIC Identity_Number → XXXXX-XXXXXXX-X\n"
        f"- DL License_Number → copy exactly as seen (keep # and dashes)\n"
        f"- Gender → M or F only\n"
        f"- Category → vehicle class  (example: M CAR, A MC, B LTV)\n"
        f"- Province → full province name  (example: Sindh, Punjab, KPK, Balochistan)\n"
        f"- Country → Pakistan{doi_hint}\n"
        f"- Missing field → empty string \"\"\n"
        f"Return ONLY a valid JSON object with exactly these keys. No explanation.\n"
        f"JSON:"
    )

    print(f"[SLM-PRIMARY] Querying for {doc_type}…")
    try:
        raw    = _stream_ollama(prompt)
        result = _parse_json(raw)
        if result:
            print(f"[SLM-PRIMARY] Got: {[k for k,v in result.items() if v]}")
            conf = {k: (0.90 if result.get(k) else 0.0) for k in fields}
            return result, conf
        print(f"[SLM-PRIMARY] No JSON in: {raw[:150]}")
    except Exception as e:
        print(f"[SLM-PRIMARY] Error: {e}")
    return {}, {}


def calculate_doi(doe: str) -> str:
    """
    Ask the SLM to derive Issue Date from Expiry Date using Pakistani DL validity rules.
    Returns DD.MM.YYYY string or "" if SLM is offline / fails.
    """
    if not _ollama_running() or not doe:
        return ""

    prompt = (
        f"A Pakistani driving license has expiry date (Valid Upto): {doe}\n"
        f"Pakistani driving licenses are valid for exactly 5 years.\n"
        f"Calculate the Issue Date using this formula:\n"
        f"  Issue Date = (Expiry Day + 1).(Expiry Month).(Expiry Year - 5)\n"
        f"Examples:\n"
        f"  10.12.2026 → 11.12.2021\n"
        f"  15.06.2025 → 16.06.2020\n"
        f"  31.03.2028 → 01.04.2023\n"
        f"For expiry date {doe}, what is the Issue Date?\n"
        f"Return ONLY valid JSON: {{\"Date_of_Issue\": \"DD.MM.YYYY\"}}\n"
        f"JSON:"
    )

    print(f"[SLM-DOI] Calculating Issue Date from expiry {doe}…")
    try:
        raw    = _stream_ollama(prompt)
        result = _parse_json(raw)
        if result and result.get("Date_of_Issue"):
            doi = result["Date_of_Issue"].strip()
            print(f"[SLM-DOI] Got: {doi}")
            return doi
        print(f"[SLM-DOI] No result in: {raw[:100]}")
    except Exception as e:
        print(f"[SLM-DOI] Error: {e}")
    return ""


def full_extract(ocr_text: str, doc_type: str = "CNIC") -> dict:
    """
    Deep full-extraction pass when rule-based confidence is still low.
    """
    if not _ollama_running():
        return {}

    fields     = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS
    fields_str = ", ".join(fields)

    prompt = (
        f"You are a precise OCR post-processor for Pakistani {doc_type} documents.\n"
        f"Read the OCR text carefully and extract every field.\n\n"
        f"OCR Text:\n{ocr_text}\n\n"
        f"Extract these fields: {fields_str}\n\n"
        f"Strict output rules:\n"
        f"- Dates → DD.MM.YYYY  (example: 15.03.1990)\n"
        f"- Gender → M or F only\n"
        f"- CNIC Identity_Number → XXXXX-XXXXXXX-X format\n"
        f"- Names → Title Case, max 3 words\n"
        f"- Missing field → empty string \"\"\n"
        f"Return ONLY a valid JSON object. Zero explanation.\n"
        f"JSON:"
    )

    print(f"[GAP2] Deep llamafile full extraction for {doc_type}…")
    try:
        raw    = _stream_ollama(prompt)
        result = _parse_json(raw)
        if result:
            print(f"[GAP2] llamafile deep-extracted: {list(result.keys())}")
            return result
        print(f"[GAP2] No JSON in response: {raw[:120]}")
    except Exception as e:
        print(f"[GAP2] Deep extraction error: {e}")
    return {}


def status() -> str:
    if _ollama_running():
        return "llamafile (port 8080)"
    return "offline"
