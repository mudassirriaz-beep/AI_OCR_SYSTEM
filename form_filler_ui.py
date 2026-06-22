"""
Flask web UI — full workflow diagram implementation.
Path handling works both as .py and PyInstaller EXE.
"""
import os
import sys
import uuid
import json
import threading
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup

from brain_format_cnic import extract_cnic_info, extract_photo as extract_photo_cnic
from brain_format_dl   import extract_dl_info,  extract_photo as extract_photo_dl
import form_mapper
import agent_orchestrator

# ── Resolve paths (works as .py and as frozen EXE) ───────────────────────────
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = sys._MEIPASS
    # %APPDATA% is always writable — Program Files is not
    _WORK_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                             "AI Document System")
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    _WORK_DIR   = _BUNDLE_DIR

TEMPLATE_FOLDER = os.path.join(_BUNDLE_DIR, 'templates')
UPLOAD_FOLDER   = os.path.join(_WORK_DIR,   'uploads')
FILLED_FOLDER   = os.path.join(_WORK_DIR,   'filled_forms')
REVIEW_FOLDER   = os.path.join(_WORK_DIR,   'pending_review')

for _d in (UPLOAD_FOLDER, FILLED_FOLDER, REVIEW_FOLDER):
    os.makedirs(_d, exist_ok=True)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=TEMPLATE_FOLDER)
app.config['UPLOAD_FOLDER']       = UPLOAD_FOLDER
app.config['FILLED_FOLDER']       = FILLED_FOLDER
app.config['REVIEW_FOLDER']       = REVIEW_FOLDER
app.config['MAX_CONTENT_LENGTH']  = 16 * 1024 * 1024


# ── Job store (file-backed) ───────────────────────────────────────────────────

def _job_path(job_id):
    return os.path.join(REVIEW_FOLDER, f"{job_id}.json")

def _save_job(job_id, data):
    with open(_job_path(job_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_job(job_id):
    p = _job_path(job_id)
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def _delete_job(job_id):
    p = _job_path(job_id)
    if os.path.exists(p):
        os.remove(p)


# ── Core pipeline ─────────────────────────────────────────────────────────────

def _run_pipeline(image_path, html_path, output_path, doc_type):
    if doc_type == "CNIC":
        extracted = extract_cnic_info(image_path)
        _, photo_b64 = extract_photo_cnic(image_path)
    else:
        extracted = extract_dl_info(image_path)
        _, photo_b64 = extract_photo_dl(image_path)

    if "error" in extracted:
        return False, extracted["error"], {}

    confidence     = extracted.pop("_confidence",     0.0)
    needs_review   = extracted.pop("_needs_review",   True)
    confidence_map = extracted.pop("_confidence_map", {})
    photo_b64      = extracted.pop("Photo_Base64",    None) or photo_b64
    extracted.pop("Photo_Path", None)

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    if photo_b64:
        soup = form_mapper.inject_photo(soup, photo_b64)

    soup, fill_log = form_mapper.fill_soup_form(soup, extracted)
    for entry in fill_log:
        print(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    meta = {
        "confidence":     round(confidence * 100, 1),
        "needs_review":   needs_review,
        "fields":         dict(extracted),
        "confidence_map": confidence_map,
        "photo_b64":      photo_b64,
        "html_path":      html_path,
        "output_path":    output_path,
    }
    return True, output_path, meta


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("form_filler.html")


@app.route("/process", methods=["POST"])
def process():
    try:
        if "image_file" not in request.files or "html_file" not in request.files:
            return jsonify({"error": "Missing files"}), 400

        img_file  = request.files["image_file"]
        html_file = request.files["html_file"]
        doc_type  = request.form.get("doc_type", "CNIC")

        if not img_file.filename or not html_file.filename:
            return jsonify({"error": "Empty filenames"}), 400

        img_path  = os.path.join(UPLOAD_FOLDER, secure_filename(img_file.filename))
        html_path = os.path.join(UPLOAD_FOLDER, secure_filename(html_file.filename))
        img_file.save(img_path)
        html_file.save(html_path)

        out_name = request.form.get("output_name", "filled_form.html")
        if not out_name.endswith(".html"):
            out_name += ".html"
        output_path = os.path.join(FILLED_FOLDER, out_name)

        success, result, meta = _run_pipeline(img_path, html_path, output_path, doc_type)
        if not success:
            return jsonify({"error": result}), 500

        if not meta["needs_review"]:
            return jsonify({
                "download_url": f"/download/{out_name}",
                "confidence":   meta["confidence"],
                "needs_review": False,
                "fields":       meta["fields"],
            })

        job_id = str(uuid.uuid4())
        _save_job(job_id, {
            "fields":         meta["fields"],
            "confidence":     meta["confidence"],
            "confidence_map": meta["confidence_map"],
            "photo_b64":      meta["photo_b64"],
            "html_path":      html_path,
            "output_path":    output_path,
        })
        return jsonify({
            "needs_review": True,
            "review_url":   f"/review/{job_id}",
            "confidence":   meta["confidence"],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/review/<job_id>")
def review(job_id):
    try:
        job = _load_job(job_id)
        if not job:
            return "Review session not found or expired.", 404

        confidence = job.get("confidence", 0)
        if confidence >= 70:
            conf_class, conf_message = "high",   "Acceptable — minor corrections may be needed"
        elif confidence >= 40:
            conf_class, conf_message = "medium", "Moderate — please check highlighted fields"
        else:
            conf_class, conf_message = "low",    "Low — most fields need manual verification"

        return render_template(
            "review.html",
            job_id         = job_id,
            fields         = job.get("fields", {}),
            confidence     = confidence,
            confidence_map = job.get("confidence_map", {}),
            photo_b64      = job.get("photo_b64"),
            conf_class     = conf_class,
            conf_message   = conf_message,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error loading review screen: {e}", 500


@app.route("/approve/<job_id>", methods=["POST"])
def approve(job_id):
    try:
        job = _load_job(job_id)
        if not job:
            return jsonify({"error": "Review session not found or expired."}), 404

        corrected   = request.get_json(force=True) or {}
        html_path   = job["html_path"]
        output_path = job["output_path"]
        photo_b64   = job.get("photo_b64")

        if not os.path.exists(html_path):
            return jsonify({"error": "Original HTML form file missing."}), 500

        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        if photo_b64:
            soup = form_mapper.inject_photo(soup, photo_b64)

        soup, _ = form_mapper.fill_soup_form(soup, corrected)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        _delete_job(job_id)
        return jsonify({"download_url": f"/download/{os.path.basename(output_path)}"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download(filename):
    try:
        filename = os.path.basename(filename)
        path = os.path.join(FILLED_FOLDER, filename)
        if os.path.exists(path):
            return send_file(path, mimetype="text/html", as_attachment=False)
        return f"File not found: {filename}", 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Download error: {e}", 500


# ── Multi-agent URL-based form filling ────────────────────────────────────────

# In-memory job store for async URL pipeline jobs
_url_jobs: dict = {}
_url_jobs_lock  = threading.Lock()


@app.route("/process-url", methods=["POST"])
def process_url():
    """
    Start the multi-agent pipeline asynchronously.
    Expects multipart/form-data with:
      image_file  — scanned CNIC or DL image
      form_url    — target form URL (http/https) or path
      doc_type    — "CNIC" or "DL"
    Returns immediately with a job_id for polling.
    """
    try:
        if "image_file" not in request.files:
            return jsonify({"error": "Missing image_file"}), 400
        img_file = request.files["image_file"]
        if not img_file.filename:
            return jsonify({"error": "Empty image filename"}), 400

        form_url = (request.form.get("form_url") or "").strip()
        if not form_url:
            return jsonify({"error": "Missing form_url"}), 400

        doc_type = request.form.get("doc_type", "CNIC").upper()
        headless = request.form.get("headless", "true").lower() == "true"

        img_path = os.path.join(UPLOAD_FOLDER, secure_filename(img_file.filename))
        img_file.save(img_path)



        with _url_jobs_lock:
            _url_jobs[job_id] = {"status": "running", "result": None}

        def _run():
            try:
                result = agent_orchestrator.run(img_path, form_url, doc_type, headless)
            except Exception as exc:
                import traceback as tb
                tb.print_exc()
                result = {"error": str(exc)}
            with _url_jobs_lock:
                _url_jobs[job_id]["status"] = "done"
                _url_jobs[job_id]["result"] = result

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({"job_id": job_id, "status": "running"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/job-status/<job_id>")
def job_status(job_id):
    """Poll for the result of a /process-url job."""
    with _url_jobs_lock:
        job = _url_jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Unknown job_id"}), 404
    if job["status"] == "running":
        return jsonify({"status": "running"})
    with _url_jobs_lock:
        _url_jobs.pop(job_id, None)
    return jsonify({"status": "done", "result": job["result"]})


@app.route("/screenshot")
def screenshot():
    """Serve the most recent form-filled screenshot."""
    path = os.path.join(_WORK_DIR, "form_filled_screenshot.png")
    if os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return "Screenshot not found", 404


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
