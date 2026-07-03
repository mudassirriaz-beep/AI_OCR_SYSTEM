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
  - [Docker](#docker)
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

> **[⬇️ Download Model from Google Drive](https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE)**

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
│
├── Core Application
│   ├── desktop_app.py              # Main desktop application (Tkinter UI)
│   ├── app.py                      # Flask web API
│   ├── main.py                     # CLI entry point
│   └── AI_Document_System_LAUNCH.py
│
├── Extraction Pipeline
│   ├── integrate_donut.py          # Donut model inference engine
│   ├── brain_format_cnic.py        # CNIC extraction pipeline
│   ├── brain_format_dl.py          # Driving License extraction pipeline
│   ├── brain_format.py             # Base extraction logic
│   ├── profile_builder.py          # Regex-based field extraction rules
│   ├── ocr_engine.py               # RapidOCR / EasyOCR with spatial layout
│   ├── extraction_engine.py        # Pipeline orchestrator
│   ├── vision_engine.py            # Vision preprocessing
│   ├── preprocess.py               # Image preprocessing utilities
│   ├── photo_extractor.py          # OpenCV face detection and photo crop
│   ├── slm_client.py               # SLM gap-fill fallback (llama-cpp-python)
│   └── vlm_extractor.py            # VLM fallback (Qwen2-VL)
│
├── Form Automation
│   ├── form_mapper.py              # RapidFuzz form field matching
│   ├── form_filler_ui.py           # HTML form filling logic
│   ├── form_agent.py               # Automated form agent
│   ├── agent_orchestrator.py       # Multi-agent orchestration
│   ├── agent_field_mapper.py       # Agent-based field mapping
│   ├── agent_form_filler.py        # Agent-based form filling
│   ├── agent_form_inspector.py     # Form structure inspection
│   ├── semantic_mapper.py          # Semantic field name matching
│   ├── dynamic_form_mapper.py      # Dynamic form detection
│   ├── dynamic_mapper_final.py     # Production form mapper
│   ├── dynamic_form_filler_v3.py   # Dynamic form auto-fill
│   ├── extract_form_fields_llm.py  # LLM-based field extraction
│   └── generate_prefilled_link_fixed.py
│
├── Build & Packaging
│   ├── build_installer.py          # One-click build script
│   ├── build_app.spec              # PyInstaller build config
│   ├── installer_v4.iss            # Inno Setup installer script
│   ├── setup_env.bat               # Environment setup
│   ├── run_app.bat                 # Quick launch script
│   ├── start_slm.bat               # SLM server launcher
│   └── build_tools/                # Additional build utilities
│
├── Training (for developers)
│   ├── finetune_donut_v5.py        # Model fine-tuning script
│   ├── batch_label_final.py        # Batch data labeling
│   ├── labeler.py                  # Annotation tool
│   └── review_labels.py            # Label quality review
│
├── Web Templates
│   └── templates/
│
├── Sample
│   └── CNIC_form.html              # Sample form for testing
│
├── models/                         # Model files — download separately
│   └── donut_round5/
│
├── Dockerfile                      # Docker container config
├── requirements.txt                # Python dependencies
├── .gitignore
└── README.md
```

---

## Installation

### End User Desktop App

1. Download **AIDocumentSystem_v4.0_Setup.exe** from the releases page
2. Double-click to install
3. Launch from the desktop shortcut

> No Python, no GPU, no internet connection required.

---

### Developer Setup

**Requirements:** Python 3.11 · Windows 10/11 64-bit

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

# 5. Download the model from Google Drive (link above)
#    Place it at:  models/donut_round5/

# 6. Run the desktop app
python desktop_app.py
```

---

### Docker

```bash
# Build the image
docker build -t ai-ocr-system .

# Run with model mounted from host
docker run -p 5000:5000 \
  -v /path/to/your/models:/app/models \
  ai-ocr-system
```

> The model folder is **not baked into the image**. Always mount it at runtime with `-v`.

---

## Usage

### Desktop Application

1. Launch the app
2. Click **Browse** — select a CNIC or Driving License image
3. Click **Extract** — app shows all extracted fields and photo
4. Open any web form in the browser, click **Fill Form** to auto-populate

### Web API

```bash
python app.py
# Runs at http://localhost:5000
```

| Method | Endpoint | Description |
|---|---|---|
| POST | /extract | Upload image → returns extracted fields as JSON |
| GET | / | Web interface for manual testing |

**Example request:**

```bash
curl -X POST http://localhost:5000/extract \
  -F "file=@cnic_image.jpg"
```

**Example response:**

```json
{
  "Full_Name": "Muhammad Ali",
  "Father_Name": "Muhammad Aslam",
  "Gender": "M",
  "Identity_Number": "42101-1234567-1",
  "DOB": "01.01.1990",
  "Date_of_Issue": "15.06.2018",
  "Date_of_Expiry": "15.06.2028",
  "Country": "Pakistan",
  "_confidence": 0.905,
  "_needs_review": false
}
```

---

## Build Installer

Requires PyInstaller, Inno Setup 6, and D: drive with 5 GB+ free space.

```bash
# Builds EXE + installer in one step
python build_installer.py
```

Output: `D:\AIDocumentSystem_Build\AIDocumentSystem_v4.0_Setup.exe`

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Donut (`naver-clova-ix/donut-base`) fine-tuned on Pakistani documents |
| Deep Learning | PyTorch 2.2.2 CPU + HuggingFace Transformers 4.46.3 |
| OCR Fallback | RapidOCR (primary) + EasyOCR (fallback) with spatial layout reconstruction |
| SLM Fallback | llama-cpp-python 0.3.28 — gap-fill for low-confidence fields |
| Image Processing | OpenCV, Pillow, PyMuPDF |
| Form Parsing | BeautifulSoup4, RapidFuzz fuzzy field matching |
| Desktop UI | Tkinter Python 3.11 |
| Web API | Flask, Werkzeug |
| Containerisation | Docker (Python 3.11-slim, CPU only) |
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
