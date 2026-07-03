# AI OCR System

> AI-powered document data extraction platform for Pakistani identity documents — fully offline, no GPU required.

[![Version](https://img.shields.io/badge/version-4.0-blue)](https://github.com/mudassirriaz-beep/OCR_offline)
[![Accuracy](https://img.shields.io/badge/accuracy-90.5%25-brightgreen)](https://github.com/mudassirriaz-beep/OCR_offline)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)](https://github.com/mudassirriaz-beep/OCR_offline)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Private-red)](https://github.com/mudassirriaz-beep/OCR_offline)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Model](#model)
- [Project Structure](#project-structure)
- [Installation](#installation)
  - [End User Desktop App](#end-user-desktop-app)
  - [Developer Setup](#developer-setup)
- [Usage](#usage)
- [Build Installer](#build-installer)
- [Tech Stack](#tech-stack)
- [Team](#team)

---

## Overview

The **AI OCR System** automates extraction of personal data from Pakistani **CNIC** (National Identity Card) and **Driving License** images using a fine-tuned [Donut](https://github.com/clovaai/donut) transformer model.

Extracted data is intelligently mapped to any HTML form regardless of input field names or types using fuzzy matching.

**Delivered as a standalone Windows desktop application: no internet, no GPU, no external installations required.**

---

## Features

| Feature | Detail |
|---|---|
| **90.5% field accuracy** | Tested on CNIC and Driving License documents |
| **Extracted fields** | Full Name, Father Name, Gender, Identity/License Number, DOB, Date of Issue, Date of Expiry, Country, Province, Vehicle Category |
| **Photo extraction** | Automatic face detection and crop from document image via OpenCV |
| **Universal form filling** | Fills text, date, number, email, select, radio, checkbox, textarea inputs |
| **Smart date conversion** | Auto-converts DD-MM-YYYY to YYYY-MM-DD for HTML date fields |
| **Fuzzy field matching** | Works even when form field names differ from standard labels |
| **Multi-format input** | JPEG, PNG, WebP, BMP, TIFF, HEIC, GIF, PDF |
| **Fully offline** | No internet required on client machine |
| **Single installer** | 871 MB EXE — double-click to install, nothing else needed |

---

## Model

The system uses a fine-tuned **Donut** (Document Understanding Transformer) — an end-to-end vision-encoder-decoder that reads document images and outputs structured JSON **without a traditional OCR engine**.

### Training History

| Round | Accuracy | Notes |
|---|---|---|
| V1 | 0% | Task token format incorrect |
| V2 | 81.5% | Format fixed — model learned document structure |
| V3 | 89.4% | Expanded dataset, improved date accuracy |
| **V4 (current)** | **90.5%** | Stable release — 1,177 reviewed images |

**Dataset:** 1,177 human-reviewed CNIC + Driving License images (1,001 train / 176 validation)

### Download Model

The fine-tuned model (~777 MB) is **not included** in this repository due to GitHub file size limits.

> **[Download Model from Google Drive](https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE)**

After downloading, place the folder at:

```
models/
└── donut_round5/
    ├── config.json
    ├── generation_config.json
    ├── model.safetensors
    ├── preprocessor_config.json
    ├── sentencepiece.bpe.model
    ├── special_tokens_map.json
    ├── tokenizer.json
    └── tokenizer_config.json
```

---

## Project Structure

```
OCR_offline/
├── desktop_app.py          # Main desktop application (Tkinter UI)
├── integrate_donut.py      # Donut model inference engine
├── brain_format_cnic.py    # CNIC extraction pipeline
├── brain_format_dl.py      # Driving License extraction pipeline
├── profile_builder.py      # Regex-based field extraction rules
├── ocr_engine.py           # RapidOCR / EasyOCR with spatial layout
├── photo_extractor.py      # OpenCV face detection and photo crop
├── form_mapper.py          # RapidFuzz form field matching
├── form_filler_ui.py       # HTML form filling logic
├── slm_client.py           # SLM gap-fill fallback
├── vlm_extractor.py        # VLM fallback (Qwen2-VL)
├── preprocess.py           # Image preprocessing utilities
├── extraction_engine.py    # Extraction pipeline orchestrator
├── app.py                  # Flask web API
├── main.py                 # CLI entry point
├── build_installer.py      # One-click build script
├── build_app.spec          # PyInstaller build config
├── installer_v4.iss        # Inno Setup installer script
├── requirements.txt        # Python dependencies
├── models/                 # Model files — download separately
│   └── donut_round5/       # Fine-tuned Donut checkpoint V4
└── README.md
```

---

## Installation

### End User Desktop App

1. Download **AIDocumentSystem_v4.0_Setup.exe** from the releases page
2. Double-click to install
3. Launch from the desktop shortcut

No Python, no GPU, no internet connection required.

---

### Developer Setup

Requirements: Python 3.11, Windows 10/11 64-bit

```bash
# 1. Clone the repository
git clone https://github.com/mudassirriaz-beep/OCR_offline.git
cd OCR_offline

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install PyTorch (CPU build)
pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu

# 4. Install remaining dependencies
pip install -r requirements.txt

# 5. Download model from Google Drive (link above)
#    Place it at:  models/donut_round5/

# 6. Run the desktop app
python desktop_app.py
```

---

## Usage

### Desktop Application

1. Launch the app
2. Click **Browse** and select a CNIC or Driving License image
3. Click **Extract** — the app processes the document and shows all extracted fields and photo
4. Open any web form in the browser, then click **Fill Form** to auto-populate

### Web API

```bash
python app.py
# API available at http://localhost:5000
```

| Method | Endpoint | Description |
|---|---|---|
| POST | /extract | Upload image, returns extracted fields as JSON |
| POST | /fill | Upload image + form URL, fills and returns form data |

---

## Build Installer

Requires PyInstaller, Inno Setup 6, and D drive with 5 GB+ free space.

```bash
python build_installer.py
```

Output: `D:\AIDocumentSystem_Build\AIDocumentSystem_v4.0_Setup.exe`

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Donut (naver-clova-ix/donut-base) fine-tuned on Pakistani documents |
| Deep Learning | PyTorch 2.2.2 CPU + HuggingFace Transformers 4.46.3 |
| OCR Fallback | RapidOCR (primary) + EasyOCR (fallback) with spatial layout |
| SLM Fallback | llama-cpp-python 0.3.28 for low-confidence gap-fill |
| Image Processing | OpenCV, Pillow, PyMuPDF |
| Form Parsing | BeautifulSoup4, RapidFuzz fuzzy field matching |
| Desktop UI | Tkinter Python 3.11 |
| Web API | Flask, Werkzeug |
| Packaging | PyInstaller, Inno Setup 6 |
| Platform | Windows 10/11 64-bit |

---

## Team

**Al-Khair Institute of Technology (AIT)**

| Name | Role |
|---|---|
| Muhammad Khurram Aimad | Team Lead |
| Syed Mudassir Ali | Main Developer |
| Nehal Ansari | Assistant Developer |

---

*Fine-tuned Donut transformer · 90.5% field accuracy · Fully offline Windows desktop application*
