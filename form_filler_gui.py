import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
import urllib.parse
import webbrowser
import threading
import re
from brain_format import extract_cnic_info

LINK_FILE = "form_link.txt"
MAPPING_FILE = "form_fields_final.json"

class SimpleDarkUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Form Filler")
        self.root.geometry("600x350")
        self.root.minsize(550, 300)
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(True, True)

        # Load saved form link
        self.form_link = tk.StringVar()
        if os.path.exists(LINK_FILE):
            with open(LINK_FILE, "r") as f:
                self.form_link.set(f.read().strip())

        # Load field mapping
        self.mapping = self.load_mapping()
        self.doc_to_label = {
            "Full_Name": "Name",
            "Father_Name": "F.name",
            "Gender": "Gender",
            "Identity_Number": "Identity no",
            "DOB": "Date of birth",
            "Date_of_Issue": "Date of issue",
            "Date_of_Expiry": "Date  expiry"
        }

        self.create_widgets()

    def load_mapping(self):
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, "r") as f:
                return json.load(f)
        return {}

    def create_widgets(self):
        main = tk.Frame(self.root, bg="#2E2E2E")
        main.pack(fill="both", expand=True, padx=20, pady=15)

        # Title
        tk.Label(main, text="AI Document to Google Form", font=("Segoe UI", 14, "bold"), bg="#2E2E2E", fg="white").pack(pady=(0,15))

        # Form link
        row1 = tk.Frame(main, bg="#2E2E2E")
        row1.pack(fill="x", pady=5)
        tk.Label(row1, text="Form Link:", bg="#2E2E2E", fg="white", width=10, anchor="w").pack(side="left")
        self.entry_link = tk.Entry(row1, textvariable=self.form_link, bg="#3E3E3E", fg="white", insertbackground="white", relief="flat")
        self.entry_link.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(row1, text="Save", command=self.save_link, bg="#555", fg="white", relief="flat", width=6).pack(side="right")

        # Image
        row2 = tk.Frame(main, bg="#2E2E2E")
        row2.pack(fill="x", pady=10)
        tk.Label(row2, text="Image:", bg="#2E2E2E", fg="white", width=10, anchor="w").pack(side="left")
        self.img_path = tk.StringVar()
        self.entry_img = tk.Entry(row2, textvariable=self.img_path, bg="#3E3E3E", fg="white", insertbackground="white", relief="flat")
        self.entry_img.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(row2, text="Browse", command=self.browse_image, bg="#555", fg="white", relief="flat", width=6).pack(side="right")

        # Process button
        self.btn_process = tk.Button(main, text="Extract & Open Form", command=self.process, bg="#1E88E5", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", height=2)
        self.btn_process.pack(fill="x", pady=20)

        # Status
        self.status = tk.Label(main, text="Ready", bg="#2E2E2E", fg="#aaa", font=("Segoe UI", 9))
        self.status.pack(pady=5)

        # Footer
        tk.Label(main, text="After processing, the form will open in browser with extracted data.", bg="#2E2E2E", fg="#888", font=("Segoe UI", 8)).pack(side="bottom", pady=10)

    def save_link(self):
        link = self.form_link.get().strip()
        if link:
            with open(LINK_FILE, "w") as f:
                f.write(link)
            self.status.config(text="Form link saved.", fg="#8f8")
        else:
            messagebox.showwarning("Warning", "Enter valid link.")

    def browse_image(self):
        f = filedialog.askopenfilename(title="Select document image", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if f:
            self.img_path.set(f)

    def process(self):
        if not self.form_link.get():
            messagebox.showerror("Error", "Form link missing.")
            return
        if not self.img_path.get():
            messagebox.showerror("Error", "No image selected.")
            return
        if not self.mapping:
            messagebox.showerror("Error", f"Mapping file '{MAPPING_FILE}' not found.")
            return

        self.btn_process.config(state="disabled", text="Processing...")
        self.status.config(text="Extracting data (10-15 sec)...", fg="#fa0")
        self.root.update()

        threading.Thread(target=self.run).start()

    def run(self):
        try:
            extracted = extract_cnic_info(self.img_path.get())
            if "error" in extracted:
                self.root.after(0, self.show_error, extracted["error"])
                return

            # Build payload exactly like working terminal version
            params = {}
            for doc_key, doc_val in extracted.items():
                if doc_key in self.doc_to_label:
                    label = self.doc_to_label[doc_key]
                    if label in self.mapping:
                        val = doc_val
                        if "Date" in label:
                            # Convert to YYYY-MM-DD
                            parts = re.findall(r'\d+', val)
                            if len(parts) >= 3:
                                d, m, y = parts[0], parts[1], parts[2]
                                if len(d) == 1: d = '0' + d
                                if len(m) == 1: m = '0' + m
                                if len(y) == 2: y = '20' + y
                                val = f"{y}-{m}-{d}"
                        params[self.mapping[label]] = val

            # Add default country if field exists
            if "Country" in self.mapping and self.mapping["Country"] not in params:
                params[self.mapping["Country"]] = "Pakistan"

            if not params:
                self.root.after(0, self.show_error, "No fields to fill. Check mapping.")
                return

            # Build URL
            base = self.form_link.get().strip()
            if '?' in base:
                base = base.split('?')[0]
            query = urllib.parse.urlencode(params)
            url = f"{base}?{query}"

            self.root.after(0, webbrowser.open, url)
            self.root.after(0, self.status.config, text="Form opened in browser. Submit manually.", fg="#8f8")
            self.root.after(0, self.btn_process.config, state="normal", text="Extract & Open Form")
        except Exception as e:
            self.root.after(0, self.show_error, str(e))

    def show_error(self, msg):
        messagebox.showerror("Error", msg)
        self.status.config(text="Error", fg="#f88")
        self.btn_process.config(state="normal", text="Extract & Open Form")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleDarkUI(root)
    root.mainloop()