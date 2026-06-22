"""
OCR engine — RapidOCR (primary) with EasyOCR fallback.
When running as a frozen PyInstaller EXE the model files live inside the
bundle; paths are resolved automatically.
"""
import os
import sys
import cv2
from preprocess import preprocess_image, preprocess_dl, preprocess_dl_red_strip

# ── Resolve bundled model directory ───────────────────────────────────────────

def _bundle_dir() -> str:
    """Return the root of the frozen bundle, or the source directory."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _easyocr_model_dir() -> str:
    # EASYOCR_MODELS_DIR set by launcher when running from bundled EXE
    if os.environ.get("EASYOCR_MODELS_DIR"):
        return os.environ["EASYOCR_MODELS_DIR"]
    if getattr(sys, "frozen", False):
        work_dir = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.join(work_dir, "models", "easyocr")
    return os.path.join(os.path.expanduser("~"), ".EasyOCR", "model")


# ── Lazy-loaded engines ────────────────────────────────────────────────────────

_rapid_engine = None
_rapid_ok     = None   # None = untested, True/False = result cached

_easy_reader  = None
_easy_ok      = None


def _get_rapid():
    global _rapid_engine, _rapid_ok
    if _rapid_ok is False:
        return None
    if _rapid_engine is not None:
        return _rapid_engine
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_engine = RapidOCR()
        _rapid_ok = True
        print("[OCR] RapidOCR loaded")
        return _rapid_engine
    except Exception as e:
        _rapid_ok = False
        print(f"[OCR] RapidOCR unavailable: {e}")
        return None


def _get_easy():
    global _easy_reader, _easy_ok
    if _easy_ok is False:
        return None
    if _easy_reader is not None:
        return _easy_reader
    try:
        import easyocr
        model_dir = _easyocr_model_dir()
        os.makedirs(model_dir, exist_ok=True)
        _easy_reader = easyocr.Reader(
            ["en"],
            gpu=True,
            verbose=False,
            model_storage_directory=model_dir,
        )
        _easy_ok = True
        print(f"[OCR] EasyOCR loaded (models: {model_dir})")
        return _easy_reader
    except ImportError:
        _easy_ok = False
        print("[OCR] EasyOCR not installed — skipping fallback")
        return None
    except Exception as e:
        _easy_ok = False
        print(f"[OCR] EasyOCR unavailable: {e}")
        return None


# ── Spatial layout helpers ────────────────────────────────────────────────────

def _blocks_to_layout(blocks):
    """
    Convert [(y_top, x_left, text), ...] to a layout-preserving string.

    Blocks in the same horizontal row (y within 0.6× median height) are
    joined with ' | '; rows are separated by newlines.  This preserves the
    2-column label/value grid on CNICs so regex can pair them correctly.
    """
    if not blocks:
        return ""

    # Estimate typical text height from y-spread of all blocks
    ys = sorted(b[0] for b in blocks)
    if len(ys) > 1:
        heights = [ys[i+1] - ys[i] for i in range(len(ys)-1) if ys[i+1] - ys[i] > 0]
        row_tol = (sum(heights) / len(heights)) * 0.55 if heights else 12
    else:
        row_tol = 12

    # Sort blocks top-to-bottom, left-to-right
    blocks_sorted = sorted(blocks, key=lambda b: (b[0], b[1]))

    rows = []
    current_row = [blocks_sorted[0]]
    for block in blocks_sorted[1:]:
        if abs(block[0] - current_row[0][0]) <= row_tol:
            current_row.append(block)
        else:
            rows.append(current_row)
            current_row = [block]
    rows.append(current_row)

    lines = []
    for row in rows:
        row_sorted = sorted(row, key=lambda b: b[1])
        lines.append(" | ".join(b[2] for b in row_sorted))
    return "\n".join(lines)


def extract_blocks(image_path: str):
    """
    Run OCR and return [(y_top, x_left, text), ...] sorted spatially.
    Returns (blocks, engine_name).
    """
    processed = None
    try:
        processed = preprocess_image(image_path)
        tmp_path  = image_path + "_preprocessed.jpg"
        cv2.imwrite(tmp_path, processed)
    except Exception:
        tmp_path  = image_path
        processed = None

    # RapidOCR
    rapid = _get_rapid()
    if rapid is not None:
        try:
            result, _ = rapid(processed if processed is not None else tmp_path)
            if result:
                blocks = []
                for item in result:
                    if len(item) >= 2 and item[1].strip():
                        bbox = item[0]
                        text = item[1]
                        # bbox is [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), text))
                _cleanup(tmp_path, image_path)
                return blocks, "RapidOCR"
        except Exception as e:
            print(f"[OCR] RapidOCR spatial error: {e}")

    # EasyOCR fallback
    easy = _get_easy()
    if easy is not None:
        try:
            result = easy.readtext(image_path, detail=1)
            if result:
                blocks = []
                for bbox, text, conf in result:
                    if text.strip():
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), text))
                _cleanup(tmp_path, image_path)
                return blocks, "EasyOCR"
        except Exception as e:
            print(f"[OCR] EasyOCR spatial error: {e}")

    _cleanup(tmp_path, image_path)
    return [], None


def extract_blocks_dl(image_path: str):
    """
    DL-specific OCR: uses B&W Otsu preprocessing to handle wavy background
    and red text that the standard adaptive-threshold pipeline garbles.
    """
    processed = None
    tmp_path  = image_path
    try:
        processed = preprocess_dl(image_path)
        tmp_path  = image_path + "_dl_bw.jpg"
        cv2.imwrite(tmp_path, processed)
    except Exception as e:
        print(f"[OCR-DL] Preprocess failed: {e}")
        return extract_blocks(image_path)   # fallback to standard

    rapid = _get_rapid()
    if rapid is not None:
        try:
            result, _ = rapid(processed)
            if result:
                blocks = []
                for item in result:
                    if len(item) >= 2 and item[1].strip():
                        bbox = item[0]
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), item[1]))
                _cleanup(tmp_path, image_path)
                if blocks:
                    return blocks, "RapidOCR-DL-BW"
        except Exception as e:
            print(f"[OCR-DL] RapidOCR error: {e}")

    easy = _get_easy()
    if easy is not None:
        try:
            result = easy.readtext(tmp_path, detail=1)
            if result:
                blocks = []
                for bbox, text, conf in result:
                    if text.strip():
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), text))
                _cleanup(tmp_path, image_path)
                return blocks, "EasyOCR-DL-BW"
        except Exception as e:
            print(f"[OCR-DL] EasyOCR error: {e}")

    _cleanup(tmp_path, image_path)
    return [], None


def extract_blocks_dl_strip(image_path: str):
    """
    OCR just the bottom strip of the DL using green-channel preprocessing
    to read red-text labels (Issue Date, Valid Upto) that the main pass misses.
    """
    tmp_path = image_path + "_dl_strip.jpg"
    try:
        processed = preprocess_dl_red_strip(image_path)
        cv2.imwrite(tmp_path, processed)
    except Exception as e:
        print(f"[OCR-STRIP] Preprocess failed: {e}")
        return [], None

    rapid = _get_rapid()
    if rapid is not None:
        try:
            result, _ = rapid(processed)
            if result:
                blocks = []
                for item in result:
                    if len(item) >= 2 and item[1].strip():
                        bbox = item[0]
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), item[1]))
                _cleanup(tmp_path, image_path)
                if blocks:
                    return blocks, "RapidOCR-STRIP"
        except Exception as e:
            print(f"[OCR-STRIP] RapidOCR error: {e}")

    easy = _get_easy()
    if easy is not None:
        try:
            result = easy.readtext(tmp_path, detail=1)
            if result:
                blocks = []
                for bbox, text, conf in result:
                    if text.strip():
                        ys = [pt[1] for pt in bbox]
                        xs = [pt[0] for pt in bbox]
                        blocks.append((min(ys), min(xs), text))
                _cleanup(tmp_path, image_path)
                return blocks, "EasyOCR-STRIP"
        except Exception as e:
            print(f"[OCR-STRIP] EasyOCR error: {e}")

    _cleanup(tmp_path, image_path)
    return [], None


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_text(image_path: str) -> tuple:
    """
    Preprocess image then run OCR.
    Returns (text: str, engine_name: str).
    Primary: RapidOCR.  Fallback: EasyOCR.
    """
    # Preprocess for better accuracy
    tmp_path = image_path
    processed = None
    try:
        processed = preprocess_image(image_path)
        tmp_path  = image_path + "_preprocessed.jpg"
        cv2.imwrite(tmp_path, processed)
    except Exception as e:
        print(f"[OCR] Preprocess failed, using raw image: {e}")
        tmp_path  = image_path
        processed = None

    # RapidOCR (primary)
    rapid = _get_rapid()
    if rapid is not None:
        try:
            result, _ = rapid(processed if processed is not None else tmp_path)
            if result:
                text = " ".join(r[1] for r in result if r[1].strip())
                if text.strip():
                    _cleanup(tmp_path, image_path)
                    return text, "RapidOCR"
        except Exception as e:
            print(f"[OCR] RapidOCR run error: {e}")

    # EasyOCR fallback
    easy = _get_easy()
    if easy is not None:
        try:
            result = easy.readtext(image_path, detail=0)
            if result:
                _cleanup(tmp_path, image_path)
                return " ".join(result), "EasyOCR"
        except Exception as e:
            print(f"[OCR] EasyOCR run error: {e}")

    _cleanup(tmp_path, image_path)
    return "", None


def _cleanup(tmp_path: str, original: str):
    if tmp_path != original and os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except Exception:
            pass
