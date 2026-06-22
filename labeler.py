"""
Semi-automatic labeling tool for Pakistani CNIC and DL images.

Folder structure expected:
    dataset/
        cnic/       ← CNIC images here
        dl/         ← Driving License images here

OCR pre-fills every field. You only correct mistakes.
Labels saved as: dataset/cnic/labels/*.json  and  dataset/dl/labels/*.json

Usage:
    python labeler.py                  # opens folder picker
    python labeler.py dataset/         # pass dataset root directly
"""
import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

CNIC_FIELDS = [
    "Full_Name", "Father_Name", "Gender", "Identity_Number",
    "DOB", "Date_of_Issue", "Date_of_Expiry", "Country",
]
DL_FIELDS = [
    "Full_Name", "Father_Name", "Gender", "License_Number",
    "DOB", "Date_of_Issue", "Date_of_Expiry", "Country", "Category", "Province",
]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

FIELD_COLORS = {
    "Full_Name":       "#fff3cd",
    "Father_Name":     "#fff3cd",
    "Identity_Number": "#d4edda",
    "License_Number":  "#d4edda",
    "DOB":             "#d1ecf1",
    "Date_of_Issue":   "#d1ecf1",
    "Date_of_Expiry":  "#d1ecf1",
}


def _collect_images(dataset_root: str) -> list[tuple[str, str]]:
    """
    Returns list of (image_path, doc_type) from dataset/cnic/ and dataset/dl/.
    Skips already-labeled images.
    """
    items = []
    for doc_type, subdir in [("CNIC", "cnic"), ("DL", "dl")]:
        folder = os.path.join(dataset_root, subdir)
        if not os.path.isdir(folder):
            continue
        labels_dir = os.path.join(folder, "labels")
        os.makedirs(labels_dir, exist_ok=True)
        labeled = {
            os.path.splitext(f)[0]
            for f in os.listdir(labels_dir)
            if f.endswith(".json")
        }
        for fname in sorted(os.listdir(folder)):
            if os.path.splitext(fname.lower())[1] not in IMG_EXTS:
                continue
            stem = os.path.splitext(fname)[0]
            if stem in labeled:
                continue
            items.append((os.path.join(folder, fname), doc_type))
    return items


class LabelingTool:
    def __init__(self, root: tk.Tk, dataset_root: str = ""):
        self.root = root
        self.root.title("Pakistani ID Card Labeling Tool")
        self.root.geometry("1440x840")
        self.root.configure(bg="#f0f0f0")

        self.dataset_root = dataset_root
        self.items: list[tuple[str, str]] = []   # (img_path, doc_type)
        self.current_idx = 0
        self.field_vars: dict[str, tk.StringVar] = {}
        self.doc_type_var = tk.StringVar(value="CNIC")

        self._build_ui()

        if dataset_root:
            self._load_dataset(dataset_root)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg="#2c3e50", height=52)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Button(top, text="  Open Dataset Folder  ",
                  command=self._pick_folder,
                  bg="#3498db", fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=6, pady=6).pack(side="left", padx=12, pady=8)

        self.progress_lbl = tk.Label(
            top, text="Select your dataset/ folder to begin",
            bg="#2c3e50", fg="white", font=("Arial", 11))
        self.progress_lbl.pack(side="left", padx=16)

        self.status_lbl = tk.Label(top, text="", bg="#2c3e50",
                                   fg="#2ecc71", font=("Arial", 11, "bold"))
        self.status_lbl.pack(side="right", padx=16)

        # Progress bar
        self.prog_bar = ttk.Progressbar(self.root, mode="determinate")
        self.prog_bar.pack(fill="x")

        # Main area
        main = tk.Frame(self.root, bg="#f0f0f0")
        main.pack(fill="both", expand=True)

        # ── Left: image ───────────────────────────────────────────────────────
        left = tk.Frame(main, bg="#1a1a2e", width=700)
        left.pack(side="left", fill="both", expand=True)
        left.pack_propagate(False)

        self.img_label = tk.Label(left, bg="#1a1a2e")
        self.img_label.pack(expand=True)

        self.img_name_lbl = tk.Label(left, text="", bg="#1a1a2e",
                                     fg="#888", font=("Consolas", 9))
        self.img_name_lbl.pack(pady=4)

        # ── Right: fields ─────────────────────────────────────────────────────
        right = tk.Frame(main, bg="#fafafa", width=740)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        canvas = tk.Canvas(right, bg="#fafafa", highlightthickness=0)
        scroll = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        self.fields_frame = tk.Frame(canvas, bg="#fafafa")
        self.fields_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.fields_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        # Doc type display (read-only — set from subfolder)
        type_frm = tk.Frame(self.fields_frame, bg="#fafafa")
        type_frm.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(type_frm, text="Document type:",
                 bg="#fafafa", font=("Arial", 11, "bold")).pack(side="left")
        self.type_display = tk.Label(type_frm, text="—",
                                     bg="#3498db", fg="white",
                                     font=("Arial", 11, "bold"), padx=10)
        self.type_display.pack(side="left", padx=10)

        # OCR button
        self.ocr_btn = tk.Button(
            self.fields_frame, text="  Auto-Fill with OCR  ",
            command=self._run_ocr,
            bg="#27ae60", fg="white", font=("Arial", 11, "bold"),
            relief="flat", pady=7)
        self.ocr_btn.pack(fill="x", padx=14, pady=8)

        self.ocr_status = tk.Label(
            self.fields_frame, text="",
            bg="#fafafa", fg="#666", font=("Arial", 9),
            wraplength=700, justify="left")
        self.ocr_status.pack(padx=14, anchor="w")

        ttk.Separator(self.fields_frame).pack(fill="x", padx=14, pady=8)

        self.fields_container = tk.Frame(self.fields_frame, bg="#fafafa")
        self.fields_container.pack(fill="x", padx=14, expand=True)
        self._rebuild_fields("CNIC")

        # Bottom nav
        nav = tk.Frame(self.root, bg="#dfe6e9", height=62)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        tk.Button(nav, text="← Previous", command=self.prev_image,
                  font=("Arial", 11), padx=14, pady=6).pack(
                      side="left", padx=10, pady=12)

        tk.Button(nav, text="Skip →", command=self.skip_image,
                  bg="#e74c3c", fg="white", font=("Arial", 11),
                  padx=14, pady=6, relief="flat").pack(side="left", padx=6)

        tk.Button(nav, text="Clear Fields", command=self._clear_fields,
                  font=("Arial", 11), padx=10, pady=6).pack(side="left", padx=6)

        # Keyboard shortcut: Enter = Save & Next
        self.root.bind("<Return>", lambda e: self.save_and_next())
        self.root.bind("<Right>",  lambda e: self.save_and_next())
        self.root.bind("<Left>",   lambda e: self.prev_image())

        tk.Button(nav, text="  Save & Next  [Enter]  ",
                  command=self.save_and_next,
                  bg="#2980b9", fg="white", font=("Arial", 12, "bold"),
                  padx=18, pady=6, relief="flat").pack(
                      side="right", padx=12, pady=12)

    def _rebuild_fields(self, doc_type: str):
        for w in self.fields_container.winfo_children():
            w.destroy()
        self.field_vars.clear()

        fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS
        for field in fields:
            row = tk.Frame(self.fields_container, bg="#fafafa")
            row.pack(fill="x", pady=5)
            tk.Label(row, text=field.replace("_", " "),
                     bg="#fafafa", font=("Arial", 10, "bold"),
                     width=17, anchor="w", fg="#2c3e50").pack(side="left")
            var = tk.StringVar()
            entry = tk.Entry(row, textvariable=var, font=("Arial", 11),
                             width=36, relief="solid", bd=1,
                             bg=FIELD_COLORS.get(field, "white"))
            entry.pack(side="left", padx=6, ipady=3)
            self.field_vars[field] = var

    def _clear_fields(self):
        for var in self.field_vars.values():
            var.set("")
        self.ocr_status.config(text="")

    # ── Dataset loading ───────────────────────────────────────────────────────

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select dataset/ folder")
        if folder:
            self._load_dataset(folder)

    def _load_dataset(self, root: str):
        self.dataset_root = root
        self.items = _collect_images(root)

        if not self.items:
            messagebox.showinfo("All Done",
                                "All images are already labeled!\n"
                                "Ready for fine-tuning.")
            return

        self.current_idx = 0
        self._load_current()

    # ── Image display ─────────────────────────────────────────────────────────

    def _load_current(self):
        if self.current_idx >= len(self.items):
            total = self._count_labeled()
            messagebox.showinfo(
                "Labeling Complete!",
                f"All images processed.\n"
                f"Total labeled: {total}\n\n"
                f"Now run:  python finetune_donut.py  to train the model.")
            return

        img_path, doc_type = self.items[self.current_idx]
        img_file = os.path.basename(img_path)

        # Counts
        labeled  = self._count_labeled()
        total    = labeled + len(self.items)
        remain   = len(self.items) - self.current_idx
        self.progress_lbl.config(
            text=f"{img_file}  |  "
                 f"{self.current_idx + 1}/{len(self.items)} remaining  |  "
                 f"{labeled} labeled")
        self.prog_bar["value"] = (labeled / total * 100) if total else 0

        # Doc type badge
        self.type_display.config(text=doc_type,
                                 bg="#3498db" if doc_type == "CNIC" else "#8e44ad")

        self.img_name_lbl.config(text=img_path)
        self.status_lbl.config(text="")
        self.ocr_status.config(text="")
        self._rebuild_fields(doc_type)

        # Display image
        try:
            img = Image.open(img_path)
            img.thumbnail((680, 700), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.img_label.config(image=photo, text="")
            self.img_label.image = photo
        except Exception as e:
            self.img_label.config(image="", text=f"Cannot load:\n{e}",
                                  fg="red", font=("Arial", 12))

        # Auto-run OCR immediately on load
        self._run_ocr()

    def _count_labeled(self) -> int:
        total = 0
        if not self.dataset_root:
            return 0
        for subdir in ("cnic", "dl"):
            ldir = os.path.join(self.dataset_root, subdir, "labels")
            if os.path.isdir(ldir):
                total += sum(1 for f in os.listdir(ldir) if f.endswith(".json"))
        return total

    # ── OCR ───────────────────────────────────────────────────────────────────

    def _run_ocr(self):
        if self.current_idx >= len(self.items):
            return
        img_path, doc_type = self.items[self.current_idx]
        self.ocr_btn.config(state="disabled", text="Running OCR…")
        self.ocr_status.config(text="Auto-extracting fields…", fg="#e67e22")

        def _worker():
            try:
                if doc_type == "CNIC":
                    import brain_format_cnic
                    result = brain_format_cnic.extract_cnic_info(img_path)
                else:
                    import brain_format_dl
                    result = brain_format_dl.extract_dl_info(img_path)
                self.root.after(0, lambda: self._apply_ocr(result, doc_type))
            except Exception as e:
                self.root.after(0, lambda: self.ocr_status.config(
                    text=f"OCR error: {e}", fg="red"))
                self.root.after(0, lambda: self.ocr_btn.config(
                    state="normal", text="  Auto-Fill with OCR  "))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_ocr(self, result: dict, doc_type: str):
        fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS
        filled = 0
        for field in fields:
            val = str(result.get(field, "") or "").strip()
            if val:
                self.field_vars.get(field, tk.StringVar()).set(val)
                filled += 1
        conf = result.get("_confidence", 0)
        color = "#27ae60" if conf >= 0.80 else ("#e67e22" if conf >= 0.60 else "#e74c3c")
        self.ocr_status.config(
            text=f"OCR filled {filled}/{len(fields)} fields  "
                 f"(confidence {conf:.0%}).  "
                 f"Correct mistakes → press Enter to save.",
            fg=color)
        self.ocr_btn.config(state="normal", text="  Re-run OCR  ")

    # ── Save / navigate ───────────────────────────────────────────────────────

    def save_and_next(self):
        if self.current_idx >= len(self.items):
            return

        img_path, doc_type = self.items[self.current_idx]
        img_stem  = os.path.splitext(os.path.basename(img_path))[0]
        subdir    = "cnic" if doc_type == "CNIC" else "dl"
        labels_dir = os.path.join(self.dataset_root, subdir, "labels")
        os.makedirs(labels_dir, exist_ok=True)

        fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS
        gt = {"doc_type": doc_type}
        for field in fields:
            gt[field] = self.field_vars.get(field, tk.StringVar()).get().strip()

        # Basic check
        has_id   = bool(gt.get("Identity_Number") or gt.get("License_Number"))
        has_name = bool(gt.get("Full_Name"))
        if not has_id and not has_name:
            if not messagebox.askyesno(
                    "Empty Label",
                    "No name or ID number filled. Save anyway?"):
                return

        label_path = os.path.join(labels_dir, img_stem + ".json")
        with open(label_path, "w", encoding="utf-8") as f:
            json.dump({"gt_parse": gt}, f, ensure_ascii=False, indent=2)

        self.status_lbl.config(text=f"✓ Saved")
        self.current_idx += 1
        self._load_current()

    def skip_image(self):
        self.current_idx += 1
        self._load_current()

    def prev_image(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._load_current()


def main():
    root = tk.Tk()
    dataset_root = sys.argv[1] if len(sys.argv) > 1 else ""
    LabelingTool(root, dataset_root)
    root.mainloop()


if __name__ == "__main__":
    main()
