"""
Orchestrator — coordinates all three agents end-to-end.

Pipeline:
  Step 0  OCR + LLM extraction   brain_format_cnic / brain_format_dl
  Step 1  Form inspection         agent_form_inspector
  Step 2  LLM field mapping       agent_field_mapper
  Step 3  Selenium form filling   agent_form_filler

Usage (CLI):
  python agent_orchestrator.py <image_path> <form_url_or_path> [CNIC|DL] [--headless]
"""
import json
import os
import sys
import traceback

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)

import brain_format_cnic
import brain_format_dl
import agent_form_inspector
import agent_field_mapper
import agent_form_filler

DRIVER_PATH = os.path.join(_BASE, "msedgedriver.exe")


def _normalise_url(form_source: str) -> str:
    """Ensure local paths become file:// URLs for Selenium."""
    if form_source.startswith(("http://", "https://", "file://")):
        return form_source
    if form_source.lower().endswith(".pdf"):
        return form_source          # handled by PDF inspector, not Selenium
    abs_p = os.path.abspath(form_source)
    return "file:///" + abs_p.replace("\\", "/")


def run(
    image_path: str,
    form_source: str,
    doc_type: str  = "CNIC",
    headless: bool = False,
) -> dict:
    """
    Full multi-agent pipeline.
    Returns a result dict with keys:
      doc_data, form_field_count, actions, fill_result, errors
    """
    sep = "=" * 60
    errors = []

    print(f"\n{sep}")
    print(f"[ORCHESTRATOR] Pipeline start")
    print(f"  Image   : {image_path}")
    print(f"  Form    : {form_source}")
    print(f"  DocType : {doc_type}")
    print(sep)

    # ── Step 0: Extract document data ─────────────────────────────────────────
    print("\n[STEP 0] Extracting document data (OCR + LLM)…")
    try:
        if doc_type.upper() == "DL":
            doc_data = brain_format_dl.extract_dl_info(image_path)
        else:
            doc_data = brain_format_cnic.extract_cnic_info(image_path)
    except Exception as e:
        traceback.print_exc()
        return {"error": f"Step 0 — document extraction crashed: {e}"}

    if "error" in doc_data:
        return {"error": f"Step 0 — {doc_data['error']}"}

    # Strip internal metadata before logging
    clean_doc = {k: v for k, v in doc_data.items()
                 if not k.startswith("_") and "Base64" not in k and k != "Photo_Path"}
    print(f"[STEP 0] Extracted fields: {list(clean_doc.keys())}")
    confidence = doc_data.get("_confidence", 0)
    print(f"[STEP 0] Overall confidence: {confidence:.0%}")

    # ── Step 1: Inspect form ───────────────────────────────────────────────────
    print("\n[STEP 1] Inspecting form…")
    try:
        dp = DRIVER_PATH if os.path.exists(DRIVER_PATH) else None
        form_schema = agent_form_inspector.inspect_form(form_source, dp)
        n_fields = form_schema.get("field_count", 0)
        print(f"[STEP 1] Discovered {n_fields} form fields")
        if n_fields == 0:
            errors.append("Step 1 — no form fields found at the given source")
    except Exception as e:
        traceback.print_exc()
        errors.append(f"Step 1 — form inspection failed: {e}")
        form_schema = {"fields": [], "field_count": 0}

    # ── Step 2: Map fields with LLM ───────────────────────────────────────────
    print("\n[STEP 2] Mapping fields with LLM…")
    actions = []
    try:
        actions = agent_field_mapper.map_fields(doc_data, form_schema)
        print(f"[STEP 2] Produced {len(actions)} fill actions")
        if not actions:
            errors.append("Step 2 — mapper produced no actions (check Ollama or field labels)")
    except Exception as e:
        traceback.print_exc()
        errors.append(f"Step 2 — field mapping failed: {e}")

    # ── Step 3: Fill the form ─────────────────────────────────────────────────
    fill_result = {}
    if actions:
        print("\n[STEP 3] Filling form with Selenium…")
        try:
            url = _normalise_url(form_source)
            # PDF forms are filled differently (not Selenium)
            if form_source.lower().endswith(".pdf") and not form_source.startswith("http"):
                fill_result = _fill_pdf(form_source, actions)
            else:
                fill_result = agent_form_filler.fill_web_form(
                    url, actions, dp, headless=headless
                )
            filled = len(fill_result.get("filled", []))
            failed = len(fill_result.get("failed", []))
            print(f"[STEP 3] Filled: {filled}  Failed: {failed}  "
                  f"Skipped: {len(fill_result.get('skipped', []))}")
            if failed:
                errors.append(f"Step 3 — {failed} field(s) failed to fill")
        except Exception as e:
            traceback.print_exc()
            errors.append(f"Step 3 — form filling crashed: {e}")
    else:
        errors.append("Step 3 — skipped (no actions to execute)")

    return {
        "doc_data":         clean_doc,
        "form_field_count": form_schema.get("field_count", 0),
        "actions":          actions,
        "fill_result":      {k: v for k, v in fill_result.items() if k != "page_source"},
        "errors":           errors,
        "confidence":       round(confidence * 100, 1),
    }


def _fill_pdf(pdf_path: str, actions: list) -> dict:
    """
    Fill a PDF form using PyMuPDF.
    Falls back to this when the source is a local PDF.
    """
    import fitz

    results = {"filled": [], "failed": [], "skipped": []}
    doc     = fitz.open(pdf_path)

    for action in actions:
        field_name = action.get("field_name") or action.get("field_id") or ""
        value      = str(action.get("value", "")).strip()
        if not value:
            results["skipped"].append(f"{field_name}: empty")
            continue

        found = False
        for page in doc:
            for widget in page.widgets():
                if widget.field_name == field_name:
                    widget.field_value = value
                    widget.update()
                    results["filled"].append(f"{field_name} = {value}")
                    found = True
                    break
            if found:
                break
        if not found:
            results["failed"].append(f"{field_name}: not found in PDF")

    out_path = pdf_path.replace(".pdf", "_filled.pdf")
    doc.save(out_path)
    doc.close()
    results["output_path"] = out_path
    return results


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python agent_orchestrator.py <image> <form_url_or_path> [CNIC|DL] [--headless]")
        sys.exit(1)

    img    = sys.argv[1]
    form   = sys.argv[2]
    dtype  = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "CNIC"
    hless  = "--headless" in sys.argv

    result = run(img, form, dtype, hless)
    print("\n" + "=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
