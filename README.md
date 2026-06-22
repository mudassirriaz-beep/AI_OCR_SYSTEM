# AI OCR System

> AI-powered document data extraction platform for Pakistani identity documents.

![Version](https://img.shields.io/badge/version-4.0-blue)
![Accuracy](https://img.shields.io/badge/accuracy-90.5%25-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-Private-red)

---

## Overview

The **AI OCR System** automates extraction of personal data from Pakistani **CNIC** (National Identity Card) and **Driving License** images using a fine-tuned [Donut](https://github.com/clovaai/donut) transformer model. Extracted data is intelligently mapped to any HTML form — regardless of input type.

Delivered as a standalone Windows desktop application: **no internet, no GPU, no external installations required**.

---

## Features

- **90.5% field-level accuracy** on CNIC and Driving License documents
- Extracts: Full Name, Father Name, Gender, Identity/License Number, DOB, Date of Issue, Date of Expiry, Country, Province, Vehicle Category
- Automatic **photo extraction** from document image (face detection via OpenCV)
- Fills any HTML form — `text`, `date`, `number`, `email`, `select`, `radio`, `checkbox`, `textarea`
- Auto date conversion: `DD-MM-YYYY` → `YYYY-MM-DD` for `type="date"` fields
- Fuzzy field-name matching (RapidFuzz) — works even if field names differ
- In-app **"View Extracted Data"** panel — shows photo + all fields
- Fully offline — no internet required on client machine
- Single **871 MB installer EXE** — double-click to install, nothing else needed
- Supports: JPEG, PNG, WebP, BMP, TIFF, HEIC, GIF, PDF input formats

---

## Model

The system uses a fine-tuned **Donut** (Document Understanding Transformer) model — an end-to-end transformer that reads document images and outputs structured JSON without a traditional OCR engine.

### Training History

| Round | Version | Accuracy | Notes |
|-------|---------|----------|-------|
| 1 | V1 | 0% | Initial attempt — task token format incorrect |
| 2 | V2 | 81.5% | Format fixed — model learned document structure |
| 3 | V3 | 89.4% | Expanded dataset, improved date accuracy |
| 4 | V4 | **90.5%** | Current stable release |

**Dataset:** 1,177 human-reviewed CNIC and Driving License images (1,001 train / 176 validation)

### Download Model

The fine-tuned model (~777 MB) is not included in this repository due to GitHub file size limits.

> **[Download Model from Google Drive](#)** ← *(link will be added)*

After downloading, place the contents in:
```
models/donut_finetuned/
```

---

## Project Structure

```
AI_OCR_System/
├── desktop_app.py          # Main desktop application (Tkinter UI)
├── integrate_donut.py      # Donut model inference engine
├── photo_extractor.py      # OpenCV photo extraction
├── form_mapper.py          # RapidFuzz form field matching
├── form_filler_ui.py       # Form filling logic
├── build_app.spec          # PyInstaller build spec
├── build_installer.py      # One-click build script
├── installer_v4.iss        # Inno Setup installer script
├── models/                 # ← Model files (download separately)
│   └── donut_finetuned/    # Fine-tuned Donut checkpoint (V4)
└── README.md
```

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| AI Model | Donut (naver-clova-ix/donut-base) — fine-tuned |
| Framework | PyTorch (CPU) + HuggingFace Transformers 4.46.3 |
| Image Processing | OpenCV, Pillow, PyMuPDF |
| Form Parsing | BeautifulSoup4 + RapidFuzz |
| UI | Tkinter (Python 3.11) |
| Packaging | PyInstaller + Inno Setup 6 |
| Platform | Windows 10 / 11 (64-bit) |

---

## Installation (Client)

1. Download `AIDocumentSystem_v4.0_Setup.exe`
2. Double-click to install
3. Launch from desktop shortcut

No Python, no Ollama, no GPU, no internet required.

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/mudassirriaz-beep/AI_OCR_System.git
cd AI_OCR_System

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.46.3 sentencepiece Pillow opencv-python-headless
pip install beautifulsoup4 requests rapidfuzz numpy safetensors huggingface-hub

# Download model (see link above) and place in models/donut_finetuned/

# Run the app
python desktop_app.py
```

---

## Build Installer

```bash
# Builds EXE + installer (requires D: drive with 5GB+ free space)
python build_installer.py
```

Output: `D:\AIDocumentSystem_Build\AIDocumentSystem_v4.0_Setup.exe`

---

## Team

**Al-Khair Institute of Technology (AIT)**

| Name | Role |
|------|------|
| Muhammad Khurram Aimad | Team Lead |
| Syed Mudassir Ali | Main Developer |
| Nehal Ansari | Assistant Developer |

---

## Organization

**Al-Khair Institute of Technology (AIT)**
Internal project — Confidential

---

*Built with fine-tuned Donut transformer model • 90.5% field accuracy • Windows desktop application*
