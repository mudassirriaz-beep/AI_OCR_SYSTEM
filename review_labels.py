"""
Label review tool — shows each image with OCR-extracted fields.
Press Enter = correct.  Edit any field then press Enter = save corrected.
All labels saved for fine-tuning.

Usage:  python review_labels.py
"""
import os, json, threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(__file__)

# All dataset roots and their subfolders — add new datasets here
DATASET_SOURCES = [
    {
        "root": os.path.join(BASE_DIR, "Dataset_Images", "Dataset_Images"),
        "subfolders": [
            ("CNIC_Images",            "CNIC"),
            ("Driving_License_images", "DL"),
        ],
    },
    {
        "root": os.path.join(BASE_DIR, "New_data", "New_data"),
        "subfolders": [
            ("cnic_images",    "CNIC"),
            ("driving_license","DL"),
        ],
    },
    {
        "root": os.path.join(BASE_DIR, "Final_images"),
        "subfolders": [
            ("Cnic_images",    "CNIC"),
            ("Driving_license","DL"),
        ],
    },
]

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

CNIC_FIELDS = ["Full_Name","Father_Name","Gender","Identity_Number",
               "DOB","Date_of_Issue","Date_of_Expiry","Country"]
DL_FIELDS   = ["Full_Name","Father_Name","Gender","License_Number",
               "DOB","Date_of_Issue","Date_of_Expiry","Country","Category","Province"]

FIELD_COLORS = {
    "Full_Name":"#fff9c4","Father_Name":"#fff9c4",
    "Identity_Number":"#c8e6c9","License_Number":"#c8e6c9",
    "DOB":"#b3e5fc","Date_of_Issue":"#b3e5fc","Date_of_Expiry":"#b3e5fc",
}


def _collect_items():
    items = []
    for source in DATASET_SOURCES:
        root = source["root"]
        for subfolder, doc_type in source["subfolders"]:
            folder     = os.path.join(root, subfolder)
            labels_dir = os.path.join(folder, "labels")
            if not os.path.isdir(labels_dir):
                continue
            for fname in sorted(os.listdir(folder)):
                if os.path.splitext(fname.lower())[1] not in IMG_EXTS:
                    continue
                stem       = os.path.splitext(fname)[0]
                label_path = os.path.join(labels_dir, stem + ".json")
                if not os.path.exists(label_path):
                    continue
                try:
                    with open(label_path, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue
                gt = data.get("gt_parse", {})
                if gt.get("_reviewed", False):
                    continue   # already confirmed by user
                items.append({
                    "img_path":   os.path.join(folder, fname),
                    "label_path": label_path,
                    "doc_type":   doc_type,
                    "gt":         gt,
                })
    return items


class ReviewTool:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Label Review Tool")
        self.root.geometry("1440x860")
        self.root.configure(bg="#f0f2f5")

        self.items = _collect_items()
        self.idx   = 0
        self.field_vars: dict[str, tk.StringVar] = {}

        if not self.items:
            messagebox.showinfo("Info",
                "No labels to review.\n"
                "Run batch_label.py first, or all labels are already reviewed.")
            root.destroy()
            return

        self._build_ui()
        self._load()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg="#1a237e", height=54)
        top.pack(fill="x")
        top.pack_propagate(False)

        self.title_lbl = tk.Label(top, text="", bg="#1a237e", fg="white",
                                  font=("Arial", 12, "bold"))
        self.title_lbl.pack(side="left", padx=16, pady=14)

        self.status_lbl = tk.Label(top, text="", bg="#1a237e",
                                   fg="#a5d6a7", font=("Arial", 11, "bold"))
        self.status_lbl.pack(side="right", padx=16)

        # Progress bar
        self.prog = ttk.Progressbar(self.root, mode="determinate")
        self.prog.pack(fill="x")

        # Main
        main = tk.Frame(self.root, bg="#f0f2f5")
        main.pack(fill="both", expand=True)

        # Image side
        left = tk.Frame(main, bg="#263238", width=700)
        left.pack(side="left", fill="both", expand=True)
        left.pack_propagate(False)

        self.img_lbl = tk.Label(left, bg="#263238")
        self.img_lbl.pack(expand=True)

        self.fname_lbl = tk.Label(left, text="", bg="#263238",
                                  fg="#607d8b", font=("Consolas", 9))
        self.fname_lbl.pack(pady=4)

        # Fields side
        right = tk.Frame(main, bg="#fafafa", width=740)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        # Scrollable
        cv = tk.Canvas(right, bg="#fafafa", highlightthickness=0)
        sb = ttk.Scrollbar(right, orient="vertical", command=cv.yview)
        self.ff = tk.Frame(cv, bg="#fafafa")
        self.ff.bind("<Configure>",
                     lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.ff, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)

        # Doc type badge
        hdr = tk.Frame(self.ff, bg="#fafafa")
        hdr.pack(fill="x", padx=14, pady=(14,4))
        tk.Label(hdr, text="Document type:", bg="#fafafa",
                 font=("Arial", 11, "bold")).pack(side="left")
        self.type_badge = tk.Label(hdr, text="", bg="#1565c0", fg="white",
                                   font=("Arial", 11, "bold"), padx=10, pady=2)
        self.type_badge.pack(side="left", padx=10)

        self.conf_lbl = tk.Label(self.ff, text="", bg="#fafafa",
                                 font=("Arial", 10), fg="#555")
        self.conf_lbl.pack(padx=14, anchor="w")

        ttk.Separator(self.ff).pack(fill="x", padx=14, pady=8)

        self.fields_frame = tk.Frame(self.ff, bg="#fafafa")
        self.fields_frame.pack(fill="x", padx=14, expand=True)

        # Bottom buttons
        nav = tk.Frame(self.root, bg="#e8eaf6", height=64)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        tk.Button(nav, text="← Back", command=self.go_prev,
                  font=("Arial", 11), padx=12, pady=6).pack(
                      side="left", padx=10, pady=12)

        tk.Button(nav, text="Skip (unsure)", command=self.go_skip,
                  bg="#ef5350", fg="white", font=("Arial", 11),
                  padx=12, pady=6, relief="flat").pack(side="left", padx=8)

        tk.Label(nav, text="Enter = Correct & Next",
                 bg="#e8eaf6", fg="#555", font=("Arial", 10)).pack(side="left", padx=16)

        tk.Button(nav, text="  ✓ Correct — Save & Next  [Enter]  ",
                  command=self.save_next,
                  bg="#2e7d32", fg="white", font=("Arial", 12, "bold"),
                  padx=18, pady=6, relief="flat").pack(
                      side="right", padx=12, pady=12)

        self.root.bind("<Return>", lambda e: self.save_next())
        self.root.bind("<Right>",  lambda e: self.save_next())
        self.root.bind("<Left>",   lambda e: self.go_prev())

    def _build_fields(self, doc_type, gt):
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self.field_vars.clear()

        fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS
        for field in fields:
            row = tk.Frame(self.fields_frame, bg="#fafafa")
            row.pack(fill="x", pady=5)

            tk.Label(row, text=field.replace("_"," "),
                     bg="#fafafa", font=("Arial", 10, "bold"),
                     width=17, anchor="w", fg="#1a237e").pack(side="left")

            val = gt.get(field, "")
            var = tk.StringVar(value=str(val) if val else "")
            entry = tk.Entry(row, textvariable=var, font=("Arial", 11),
                             width=36, relief="solid", bd=1,
                             bg=FIELD_COLORS.get(field, "white"))
            entry.pack(side="left", padx=6, ipady=3)
            self.field_vars[field] = var

    # ── Navigation ────────────────────────────────────────────────────────────

    def _load(self):
        if self.idx >= len(self.items):
            reviewed = 0
            for source in DATASET_SOURCES:
                for sf, _ in source["subfolders"]:
                    ldir = os.path.join(source["root"], sf, "labels")
                    if not os.path.isdir(ldir):
                        continue
                    for f in os.listdir(ldir):
                        if not f.endswith(".json"):
                            continue
                        try:
                            d = json.load(open(os.path.join(ldir, f), encoding="utf-8"))
                            if d.get("gt_parse", {}).get("_reviewed"):
                                reviewed += 1
                        except Exception:
                            pass
            messagebox.showinfo("Complete!",
                f"All labels reviewed!\n"
                f"Reviewed: {reviewed}\n\n"
                f"Now run:  python finetune_donut.py")
            return

        item     = self.items[self.idx]
        doc_type = item["doc_type"]
        # Always reload from disk so edits are shown when going back
        with open(item["label_path"], encoding="utf-8") as f:
            gt = json.load(f).get("gt_parse", {})
        item["gt"] = gt   # keep cache in sync
        remaining = len(self.items) - self.idx
        total     = len(self.items)

        self.prog["value"] = (self.idx / total * 100)
        self.title_lbl.config(
            text=f"Review {self.idx+1} / {total}  |  {remaining} remaining")
        self.status_lbl.config(text="")

        # Badge color
        self.type_badge.config(
            text=doc_type,
            bg="#1565c0" if doc_type == "CNIC" else "#6a1b9a")

        self.fname_lbl.config(text=os.path.basename(item["img_path"]))

        # Confidence hint
        conf = gt.get("_confidence", "")
        if conf:
            try:
                c = float(conf)
                color = "#2e7d32" if c >= 0.80 else ("#e65100" if c >= 0.60 else "#b71c1c")
                self.conf_lbl.config(
                    text=f"OCR confidence: {c:.0%}  —  "
                         f"{'High — likely correct' if c>=0.80 else 'Medium — check carefully' if c>=0.60 else 'Low — check all fields'}",
                    fg=color)
            except Exception:
                self.conf_lbl.config(text="")
        else:
            self.conf_lbl.config(text="")

        self._build_fields(doc_type, gt)

        # Image
        try:
            img = Image.open(item["img_path"])
            img.thumbnail((680, 700), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self.img_lbl.config(image=ph, text="")
            self.img_lbl.image = ph
        except Exception as e:
            self.img_lbl.config(image="", text=f"Cannot load image:\n{e}",
                                fg="red", font=("Arial", 12))

    def save_next(self):
        item     = self.items[self.idx]
        doc_type = item["doc_type"]
        fields   = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS

        gt = {"doc_type": doc_type, "_reviewed": True}
        for field in fields:
            gt[field] = self.field_vars.get(field, tk.StringVar()).get().strip()

        with open(item["label_path"], "w", encoding="utf-8") as f:
            json.dump({"gt_parse": gt}, f, ensure_ascii=False, indent=2)

        self.status_lbl.config(text="✓ Saved")
        self.idx += 1
        self._load()

    def go_prev(self):
        if self.idx > 0:
            self.idx -= 1
            self._load()

    def go_skip(self):
        self.idx += 1
        self._load()


def main():
    root = tk.Tk()
    ReviewTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
