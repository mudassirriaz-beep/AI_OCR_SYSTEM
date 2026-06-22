# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AI Document System (Flask + RapidOCR + llama3 via Ollama).
Entry point: main.py  →  launches Flask, opens browser, shows Tkinter window.

Build:
    pyinstaller AIDocumentSystem.spec --clean
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
import os

datas        = []
binaries     = []
hiddenimports = []

# ── RapidOCR ────────────────────────────────────────────────────────────────
for pkg in ('rapidocr_onnxruntime', 'onnxruntime'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# ── OpenCV ───────────────────────────────────────────────────────────────────
cv_d, cv_b, cv_h = collect_all('cv2')
datas += cv_d; binaries += cv_b; hiddenimports += cv_h

# ── Flask & web libs ─────────────────────────────────────────────────────────
for pkg in ('flask', 'werkzeug', 'jinja2', 'markupsafe', 'click',
            'itsdangerous', 'bs4', 'beautifulsoup4'):
    h = collect_submodules(pkg)
    hiddenimports += h

# ── rapidfuzz ────────────────────────────────────────────────────────────────
rf_d, rf_b, rf_h = collect_all('rapidfuzz')
datas += rf_d; binaries += rf_b; hiddenimports += rf_h

# ── Pillow / numpy ───────────────────────────────────────────────────────────
for pkg in ('PIL', 'numpy'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# ── PyMuPDF ──────────────────────────────────────────────────────────────────
fitz_d, fitz_b, fitz_h = collect_all('fitz')
datas += fitz_d; binaries += fitz_b; hiddenimports += fitz_h

# ── Explicit hidden imports ───────────────────────────────────────────────────
hiddenimports += [
    'requests', 'urllib3', 'charset_normalizer', 'certifi', 'idna',
    'yaml', 'six', 'tqdm',
    'PIL.Image', 'PIL.ImageOps',
    'brain_format_cnic', 'brain_format_dl',
    'ocr_engine', 'profile_builder', 'slm_client', 'form_mapper',
    'preprocess',
]

# ── Project files ─────────────────────────────────────────────────────────────
datas += [
    ('templates',        'templates'),        # Flask HTML templates
    ('preprocess.py',    '.'),
    ('ocr_engine.py',    '.'),
    ('profile_builder.py', '.'),
    ('slm_client.py',    '.'),
    ('form_mapper.py',   '.'),
    ('brain_format_cnic.py', '.'),
    ('brain_format_dl.py',   '.'),
    ('form_filler_ui.py',    '.'),
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'notebook', 'ipython', 'IPython',
        'paddlepaddle', 'paddleocr', 'easyocr',
        'test', 'tests', 'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AIDocumentSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # no black CMD window
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIDocumentSystem',
)
