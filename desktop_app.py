import os
import sys
import threading
import webbrowser
import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from bs4 import BeautifulSoup
import form_mapper

# ── resolve base directory (works both as .py and PyInstaller .exe) ──
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
# Use %APPDATA% when frozen so writes don't hit read-only Program Files
if getattr(sys, "frozen", False):
    WORK_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "AI Document System")
else:
    WORK_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
UPLOADS_DIR  = os.path.join(WORK_DIR, "uploads")
FILLED_DIR   = os.path.join(WORK_DIR, "filled_forms")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FILLED_DIR,  exist_ok=True)

# ── colours ──
BG       = "#1e1e2e"
SURFACE  = "#2a2a3e"
ACCENT   = "#7c3aed"
ACCENT2  = "#6d28d9"
SUCCESS  = "#22c55e"
ERROR    = "#ef4444"
WARN     = "#f59e0b"
FG       = "#e2e8f0"
FG_DIM   = "#94a3b8"
ENTRY_BG = "#16213e"


# ════════════════════════════════════════════════════════
#  UNIVERSAL IMAGE CONVERTER
#  Normalises ANY format (WebP, PDF, HEIC, BMP, TIFF …)
#  to a plain JPEG the OCR engines can always read.
# ════════════════════════════════════════════════════════

def convert_to_jpeg(src_path: str) -> str:
    """
    Return a path to a JPEG version of the input.
    If the input is already a JPEG/PNG that OpenCV can open, return it unchanged.
    Converts: WebP, PDF (first page), BMP, TIFF, GIF, HEIC, etc.
    """
    ext = os.path.splitext(src_path)[1].lower()

    # PDF → JPEG via PyMuPDF
    if ext == ".pdf":
        try:
            import fitz
            doc  = fitz.open(src_path)
            pix  = doc[0].get_pixmap(dpi=200)
            out  = src_path + "_converted.jpg"
            pix.save(out, "jpeg")
            doc.close()
            return out
        except Exception as e:
            raise RuntimeError(f"PDF conversion failed: {e}")

    # Everything else → PIL → JPEG
    try:
        from PIL import Image as _PImage
        import numpy as _np
        img = _PImage.open(src_path).convert("RGB")
        if ext in (".jpg", ".jpeg"):
            # Already JPEG — verify OpenCV can open it
            import cv2 as _cv2
            if _cv2.imread(src_path) is not None:
                return src_path
        out = src_path + "_converted.jpg"
        img.save(out, "JPEG", quality=95)
        return out
    except Exception as e:
        raise RuntimeError(f"Image conversion failed for '{os.path.basename(src_path)}': {e}")


# ════════════════════════════════════════════════════════
#  FORM-FILL LOGIC  (same as form_filler_ui.py)
# ════════════════════════════════════════════════════════

# Field matching is now handled by form_mapper (rapidfuzz)


def fill_html_form(image_path, html_path, output_path, doc_type, log):
    """
    Full pipeline per diagram:
      OCR (RapidOCR) → Rules → [SLM if needed] → rapidfuzz fill → confidence gate
    """
    # Normalise image to JPEG
    orig_ext = os.path.splitext(image_path)[1].lower()
    if orig_ext not in (".jpg", ".jpeg"):
        log(f"Converting {orig_ext.upper()} to JPEG…")
        try:
            image_path = convert_to_jpeg(image_path)
            log("Conversion OK")
        except Exception as e:
            return False, str(e), {}

    # Step 1–3: DONUT fine-tuned model
    from integrate_donut import extract_cnic_info, extract_dl_info
    from photo_extractor import extract_photo

    if doc_type == "CNIC":
        log("Step 1-3: DONUT fine-tuned model (CNIC)…")
        extracted = extract_cnic_info(image_path)
    else:
        log("Step 1-3: DONUT fine-tuned model (Driving License)…")
        extracted = extract_dl_info(image_path)

    _, photo_b64 = extract_photo(image_path)

    if "error" in extracted:
        return False, extracted["error"], {}

    # Pull confidence meta
    confidence   = extracted.pop("_confidence",   0.0)
    needs_review = extracted.pop("_needs_review", True)
    extracted.pop("Photo_Path",   None)
    extracted.pop("Photo_Base64", None)

    log(f"Confidence: {confidence*100:.1f}%  |  Needs review: {needs_review}")
    log("Extracted fields:")
    display = {}
    for k, v in extracted.items():
        log(f"   {k}: {v}")
        display[k] = v

    # Step 4: Parse target form
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Step 5: Inject photo
    if photo_b64:
        soup = form_mapper.inject_photo(soup, photo_b64)
        log("Photo injected")

    # Step 6: Apply rule mapping with rapidfuzz
    log("Step 6: Filling form with rapidfuzz…")
    soup, fill_log = form_mapper.fill_soup_form(soup, extracted)
    for entry in fill_log:
        log(entry)

    # Save filled form
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    log(f"Saved → {output_path}")

    # Step 7: Confidence gate
    if needs_review:
        log("WARNING: Confidence below threshold — flagged for human review", "warn")

    display["_confidence"]   = f"{confidence*100:.1f}%"
    display["_needs_review"] = "YES — please verify" if needs_review else "No"
    display["_photo_b64"]    = photo_b64
    return True, output_path, display




# ════════════════════════════════════════════════════════
#  TKINTER UI
# ════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Document System")
        self.geometry("900x680")
        self.minsize(780, 560)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._last_output = None
        self._last_fields = {}
        self._build_ui()

    # ── build ──────────────────────────────────────────
    def _build_ui(self):
        # ── header ──
        hdr = tk.Frame(self, bg=ACCENT, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="AI Document System",
                 font=("Segoe UI", 16, "bold"), bg=ACCENT, fg="white").pack(side="left", padx=20, pady=10)
        tk.Label(hdr, text="● DONUT AI  •  91.7% accuracy",
                 font=("Segoe UI", 10), bg=ACCENT, fg="#86efac").pack(side="right", padx=20)

        # ── main split ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        left  = tk.Frame(body, bg=BG)
        right = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))
        right.pack(side="left", fill="both", expand=True)

        # ── LEFT: inputs ──
        self._section(left, "Document Image")
        self._img_var  = tk.StringVar()
        self._file_row(left, self._img_var, self._browse_image)

        self._section(left, "HTML Form to Fill")
        self._html_var = tk.StringVar()
        self._file_row(left, self._html_var, self._browse_html)

        self._section(left, "Document Type")
        self._doc_type = tk.StringVar(value="CNIC")
        rb_frame = tk.Frame(left, bg=BG)
        rb_frame.pack(fill="x", pady=(0, 6))
        for t in ("CNIC", "Driving License"):
            tk.Radiobutton(rb_frame, text=t, variable=self._doc_type, value=t,
                           bg=BG, fg=FG, selectcolor=SURFACE,
                           activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 10)).pack(side="left", padx=(0, 14))

        self._section(left, "Output Filename")
        out_frame = tk.Frame(left, bg=BG)
        out_frame.pack(fill="x", pady=(0, 10))
        self._out_var = tk.StringVar(value="filled_form.html")
        tk.Entry(out_frame, textvariable=self._out_var,
                 bg=ENTRY_BG, fg=FG, insertbackground=FG,
                 relief="flat", font=("Segoe UI", 10),
                 highlightthickness=1, highlightbackground="#334155",
                 highlightcolor=ACCENT).pack(fill="x", ipady=6)

        # ── extracted fields preview ──
        self._section(left, "Extracted Fields")
        fields_outer = tk.Frame(left, bg=SURFACE, bd=0)
        fields_outer.pack(fill="x", pady=(0, 8))
        self._fields_frame = tk.Frame(fields_outer, bg=SURFACE)
        self._fields_frame.pack(fill="x", padx=8, pady=8)
        tk.Label(self._fields_frame, text="(will appear after extraction)",
                 font=("Segoe UI", 9, "italic"), bg=SURFACE, fg=FG_DIM).pack(anchor="w")

        # ── action buttons ──
        btn_frame = tk.Frame(left, bg=BG)
        btn_frame.pack(fill="x", pady=(8, 0))
        self._run_btn = tk.Button(btn_frame, text="Extract & Fill Form",
                                  command=self._start_process,
                                  bg=ACCENT, fg="white",
                                  font=("Segoe UI", 11, "bold"),
                                  relief="flat", cursor="hand2",
                                  activebackground=ACCENT2, activeforeground="white",
                                  pady=10)
        self._run_btn.pack(fill="x", pady=(0, 6))

        self._open_btn = tk.Button(btn_frame, text="Open Filled Form in Browser",
                                   command=self._open_result,
                                   bg=SUCCESS, fg="white",
                                   font=("Segoe UI", 10),
                                   relief="flat", cursor="hand2",
                                   activebackground="#16a34a", activeforeground="white",
                                   pady=8, state="disabled")
        self._open_btn.pack(fill="x", pady=(0, 6))

        self._preview_btn = tk.Button(btn_frame, text="View Extracted Data",
                                      command=self._show_preview_window,
                                      bg="#0ea5e9", fg="white",
                                      font=("Segoe UI", 10),
                                      relief="flat", cursor="hand2",
                                      activebackground="#0284c7", activeforeground="white",
                                      pady=8, state="disabled")
        self._preview_btn.pack(fill="x")

        # ── RIGHT: log ──
        log_hdr = tk.Frame(right, bg=SURFACE)
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="  Processing Log", font=("Segoe UI", 10, "bold"),
                 bg=SURFACE, fg=FG).pack(side="left", pady=6)
        tk.Button(log_hdr, text="Clear", command=self._clear_log,
                  bg=SURFACE, fg=FG_DIM, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2").pack(side="right", padx=8)

        log_wrap = tk.Frame(right, bg=ENTRY_BG, bd=0,
                            highlightthickness=1, highlightbackground="#334155")
        log_wrap.pack(fill="both", expand=True, pady=(1, 0))

        self._log_text = tk.Text(log_wrap, bg=ENTRY_BG, fg=FG_DIM,
                                 font=("Consolas", 9), relief="flat",
                                 wrap="word", state="disabled", cursor="arrow")
        scroll = ttk.Scrollbar(log_wrap, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=6, pady=6)

        # colour tags
        self._log_text.tag_config("ok",   foreground=SUCCESS)
        self._log_text.tag_config("err",  foreground=ERROR)
        self._log_text.tag_config("warn", foreground=WARN)
        self._log_text.tag_config("info", foreground="#38bdf8")

        # ── status bar ──
        self._status = tk.Label(self, text="Ready",
                                bg=SURFACE, fg=FG_DIM,
                                font=("Segoe UI", 9), anchor="w", padx=10, pady=4)
        self._status.pack(fill="x", side="bottom")

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=FG_DIM).pack(anchor="w", pady=(10, 2))

    def _file_row(self, parent, var, cmd):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 4))
        e = tk.Entry(row, textvariable=var,
                     bg=ENTRY_BG, fg=FG, insertbackground=FG,
                     relief="flat", font=("Segoe UI", 10),
                     highlightthickness=1, highlightbackground="#334155",
                     highlightcolor=ACCENT)
        e.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        tk.Button(row, text="Browse", command=cmd,
                  bg=SURFACE, fg=FG, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2",
                  activebackground="#374151", activeforeground=FG,
                  padx=10, pady=6).pack(side="right")

    # ── helpers ────────────────────────────────────────
    def _log(self, msg, tag=""):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _set_status(self, msg, colour=FG_DIM):
        self._status.configure(text=msg, fg=colour)


    def _browse_image(self):
        path = filedialog.askopenfilename(
            title="Select document image",
            filetypes=[
                ("All supported", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp *.gif *.heic *.heif *.pdf"),
                ("JPEG",  "*.jpg *.jpeg"),
                ("PNG",   "*.png"),
                ("WebP",  "*.webp"),
                ("PDF",   "*.pdf"),
                ("BMP/TIFF", "*.bmp *.tiff *.tif"),
                ("All files", "*.*"),
            ])
        if path:
            self._img_var.set(path)

    def _browse_html(self):
        path = filedialog.askopenfilename(
            title="Select HTML form",
            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")])
        if path:
            self._html_var.set(path)

    def _open_result(self):
        if self._last_output and os.path.exists(self._last_output):
            webbrowser.open(f"file:///{self._last_output.replace(os.sep, '/')}")
        else:
            messagebox.showwarning("Not found", "No filled form available yet.")

    # ── process ────────────────────────────────────────
    def _start_process(self):
        img  = self._img_var.get().strip()
        html = self._html_var.get().strip()
        out  = self._out_var.get().strip() or "filled_form.html"

        if not img:
            messagebox.showerror("Missing input", "Please select a document image.")
            return
        if not os.path.exists(img):
            messagebox.showerror("File not found", f"Image not found:\n{img}")
            return
        if not html:
            messagebox.showerror("Missing input", "Please select an HTML form.")
            return
        if not os.path.exists(html):
            messagebox.showerror("File not found", f"HTML form not found:\n{html}")
            return

        if not out.endswith(".html"):
            out += ".html"
        output_path = os.path.join(FILLED_DIR, out)

        self._run_btn.configure(state="disabled", text="Processing…")
        self._open_btn.configure(state="disabled")
        self._set_status("Processing…", WARN)
        self._clear_log()
        self._log(f"Image  : {img}", "info")
        self._log(f"Form   : {html}", "info")
        self._log(f"Type   : {self._doc_type.get()}", "info")
        self._log(f"Output : {output_path}", "info")
        self._log("─" * 55)

        threading.Thread(target=self._run_process,
                         args=(img, html, output_path, self._doc_type.get()),
                         daemon=True).start()

    def _run_process(self, img, html, output_path, doc_type):
        def log(m, tag=""): self.after(0, self._log, m, tag)

        try:
            ok, result, fields = fill_html_form(img, html, output_path, doc_type, log)
        except Exception as e:
            ok, result, fields = False, str(e), {}

        def finish():
            self._run_btn.configure(state="normal", text="Extract & Fill Form")
            if ok:
                self._last_output = result
                self._last_fields = fields
                self._open_btn.configure(state="normal")
                self._preview_btn.configure(state="normal")
                self._set_status("Done! Form filled successfully.", SUCCESS)
                self._log("─" * 55)
                self._log("SUCCESS — click 'Open Filled Form' to view.", "ok")
                self._show_fields(fields)
            else:
                self._set_status("Error — see log.", ERROR)
                self._log("─" * 55)
                self._log("ERROR: " + result, "err")
                messagebox.showerror("Extraction failed", result)

        self.after(0, finish)

    def _show_preview_window(self):
        if not self._last_fields:
            messagebox.showwarning("No data", "Please extract data first.")
            return

        win = tk.Toplevel(self)
        win.title("Extracted Data Preview")
        win.configure(bg=BG)
        win.geometry("720x520")
        win.resizable(True, True)

        # Header
        hdr = tk.Frame(win, bg=ACCENT, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Extracted Document Data",
                 font=("Segoe UI", 13, "bold"),
                 bg=ACCENT, fg="white").pack(side="left", padx=16, pady=10)

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Photo on left
        photo_b64 = self._last_fields.get("_photo_b64")
        if photo_b64:
            try:
                from PIL import Image as PILImage, ImageTk
                import io, base64 as _b64
                img_data = _b64.b64decode(photo_b64)
                img = PILImage.open(io.BytesIO(img_data))
                img.thumbnail((170, 210))
                photo_img = ImageTk.PhotoImage(img)
                photo_frame = tk.Frame(body, bg=SURFACE)
                photo_frame.pack(side="left", padx=(0, 16), pady=4, anchor="n")
                lbl = tk.Label(photo_frame, image=photo_img, bg=SURFACE)
                lbl.image = photo_img
                lbl.pack(padx=10, pady=(10, 4))
                tk.Label(photo_frame, text="Photo",
                         font=("Segoe UI", 9), bg=SURFACE, fg=FG_DIM).pack(pady=(0, 10))
            except Exception:
                pass

        # Scrollable fields on right
        fields_outer = tk.Frame(body, bg=BG)
        fields_outer.pack(side="left", fill="both", expand=True)

        canvas = tk.Canvas(fields_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(fields_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        fields_frame = tk.Frame(canvas, bg=BG)
        canvas_win = canvas.create_window((0, 0), window=fields_frame, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_resize)
        fields_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        skip = {"_photo_b64"}
        for i, (key, val) in enumerate(self._last_fields.items()):
            if key in skip:
                continue
            row_bg = SURFACE if i % 2 == 0 else "#252538"
            row = tk.Frame(fields_frame, bg=row_bg)
            row.pack(fill="x", pady=1)
            display_key = key.replace("_", " ").title()
            tk.Label(row, text=display_key, width=22, anchor="w",
                     bg=row_bg, fg=FG_DIM,
                     font=("Segoe UI", 10, "bold"),
                     padx=10, pady=7).pack(side="left")
            tk.Label(row, text=str(val), anchor="w",
                     bg=row_bg, fg=FG,
                     font=("Segoe UI", 10),
                     padx=8, pady=7).pack(side="left", fill="x", expand=True)

        tk.Button(win, text="Close", command=win.destroy,
                  bg=SURFACE, fg=FG, relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  padx=24, pady=8).pack(pady=10)

    def _show_fields(self, fields):
        for w in self._fields_frame.winfo_children():
            w.destroy()
        visible = {k: v for k, v in fields.items() if k != "_photo_b64"}
        if not visible:
            tk.Label(self._fields_frame, text="(none)", bg=SURFACE, fg=FG_DIM,
                     font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        for key, val in visible.items():
            row = tk.Frame(self._fields_frame, bg=SURFACE)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{key}:", width=16, anchor="w",
                     bg=SURFACE, fg=FG_DIM,
                     font=("Segoe UI", 8, "bold")).pack(side="left")
            tk.Label(row, text=str(val), anchor="w",
                     bg=SURFACE, fg=FG,
                     font=("Consolas", 9)).pack(side="left", fill="x", expand=True)


# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
