# -*- mode: python ; coding: utf-8 -*-
"""
AIDocumentSystem_Complete.spec
Complete PyInstaller spec — bundles every Python dependency, all project
source files, OpenCV cascade data, and Selenium for the multi-agent pipeline.

Ollama binary + model blobs are NOT embedded here; they live in separate
folders next to the .exe (placed there by the Inno Setup installer).
This keeps the PyInstaller archive at a reasonable size (~800 MB) while
the full installer contains everything.

Build:
    python bundle_models.py          # gather Ollama + EasyOCR models first
    pyinstaller AIDocumentSystem_Complete.spec --clean --noconfirm
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
import os, sys

datas         = []
binaries      = []
hiddenimports = []


# ── RapidOCR + ONNX Runtime ───────────────────────────────────────────────────
for pkg in ("rapidocr_onnxruntime", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h


# ── OpenCV (includes haarcascade XML files) ───────────────────────────────────
d, b, h = collect_all("cv2")
datas += d; binaries += b; hiddenimports += h


# ── Flask & web stack ─────────────────────────────────────────────────────────
for pkg in ("flask", "werkzeug", "jinja2", "markupsafe", "click",
            "itsdangerous", "bs4", "beautifulsoup4", "soupsieve"):
    hiddenimports += collect_submodules(pkg)


# ── Requests / urllib3 ────────────────────────────────────────────────────────
for pkg in ("requests", "urllib3", "certifi", "charset_normalizer", "idna"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h


# ── rapidfuzz ─────────────────────────────────────────────────────────────────
d, b, h = collect_all("rapidfuzz")
datas += d; binaries += b; hiddenimports += h


# ── Pillow / numpy ────────────────────────────────────────────────────────────
for pkg in ("PIL", "numpy"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h


# ── PyMuPDF (fitz) ────────────────────────────────────────────────────────────
d, b, h = collect_all("fitz")
datas += d; binaries += b; hiddenimports += h


# ── Selenium ──────────────────────────────────────────────────────────────────
d, b, h = collect_all("selenium")
datas += d; binaries += b; hiddenimports += h

hiddenimports += [
    "selenium.webdriver",
    "selenium.webdriver.edge.webdriver",
    "selenium.webdriver.edge.options",
    "selenium.webdriver.edge.service",
    "selenium.webdriver.chrome.webdriver",
    "selenium.webdriver.chrome.options",
    "selenium.webdriver.chrome.service",
    "selenium.webdriver.common.by",
    "selenium.webdriver.common.keys",
    "selenium.webdriver.common.action_chains",
    "selenium.webdriver.support.ui",
    "selenium.webdriver.support.expected_conditions",
    "selenium.webdriver.support.select",
    "selenium.webdriver.remote.webdriver",
    "selenium.webdriver.remote.webelement",
    "selenium.common.exceptions",
]


# ── EasyOCR (optional fallback — import may fail gracefully) ──────────────────
try:
    d, b, h = collect_all("easyocr")
    datas += d; binaries += b; hiddenimports += h
    hiddenimports += collect_submodules("easyocr")
except Exception:
    pass

try:
    d, b, h = collect_all("torch")
    datas += d; binaries += b; hiddenimports += h
except Exception:
    pass


# ── Misc hidden imports ───────────────────────────────────────────────────────
hiddenimports += [
    "yaml", "six", "tqdm", "packaging",
    "PIL.Image", "PIL.ImageOps",
    # Project modules
    "brain_format_cnic", "brain_format_dl",
    "ocr_engine", "profile_builder", "slm_client", "form_mapper",
    "preprocess",
    "agent_form_inspector", "agent_field_mapper",
    "agent_form_filler", "agent_orchestrator",
    "form_filler_ui",
]


# ── Project source files ──────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(SPEC))   # SPEC is set by PyInstaller

_py_files = [
    "preprocess.py", "ocr_engine.py", "profile_builder.py",
    "slm_client.py", "form_mapper.py",
    "brain_format_cnic.py", "brain_format_dl.py",
    "form_filler_ui.py",
    "agent_form_inspector.py", "agent_field_mapper.py",
    "agent_form_filler.py", "agent_orchestrator.py",
]

datas += [("templates",  "templates")]          # Flask HTML templates

for f in _py_files:
    p = os.path.join(_HERE, f)
    if os.path.isfile(p):
        datas.append((p, "."))

# Edge WebDriver (already in project root)
_driver = os.path.join(_HERE, "msedgedriver.exe")
if os.path.isfile(_driver):
    datas.append((_driver, "."))

# EasyOCR bundled models (placed by bundle_models.py)
_easyocr_models = os.path.join(_HERE, "bundle", "models", "easyocr")
if os.path.isdir(_easyocr_models):
    datas.append((_easyocr_models, os.path.join("models", "easyocr")))


# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[_HERE],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "notebook", "ipython", "IPython",
        "paddlepaddle", "paddleocr",
        "pytest", "test", "tests",
        "tkinter.test",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIDocumentSystem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,    # no black CMD window
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["*.onnx", "*.pth", "*.dll"],   # skip compressing model files
    name="AIDocumentSystem",
)
