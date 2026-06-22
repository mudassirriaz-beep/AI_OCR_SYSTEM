# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AI Document System (DONUT edition).
CPU-only build — no CUDA required on client machine.
Run from the build venv:
    pyinstaller build_app.spec --clean
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

datas     = []
binaries  = []
hiddenimports = []

# ── transformers / DONUT ──────────────────────────────────────────────────────
t_d, t_b, t_h = collect_all('transformers')
datas     += t_d
binaries  += t_b
hiddenimports += t_h

# sentencepiece (DONUT tokenizer)
hiddenimports += collect_submodules('sentencepiece')
datas += collect_data_files('sentencepiece')

# ── torch (CPU) ───────────────────────────────────────────────────────────────
t2_d, t2_b, t2_h = collect_all('torch')
datas     += t2_d
binaries  += t2_b
hiddenimports += t2_h

# ── PIL / Pillow ──────────────────────────────────────────────────────────────
p_d, p_b, p_h = collect_all('PIL')
datas     += p_d
binaries  += p_b
hiddenimports += p_h

# ── OpenCV ────────────────────────────────────────────────────────────────────
cv_d, cv_b, cv_h = collect_all('cv2')
datas     += cv_d
binaries  += cv_b
hiddenimports += cv_h

# ── numpy ────────────────────────────────────────────────────────────────────
hiddenimports += collect_submodules('numpy')

# ── Other packages ────────────────────────────────────────────────────────────
hiddenimports += [
    'bs4', 'beautifulsoup4',
    'requests', 'urllib3', 'charset_normalizer', 'certifi',
    'rapidfuzz',
    'tqdm', 'filelock', 'packaging', 'regex',
    'huggingface_hub', 'safetensors',
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
    'integrate_donut', 'photo_extractor',
    'form_mapper',
]

# ── Data files ────────────────────────────────────────────────────────────────
# DONUT fine-tuned model
datas += [(str(ROOT / 'models' / 'donut_round5'), 'models/donut_round5')]

# Templates (HTML form templates)
datas += [(str(ROOT / 'templates'), 'templates')]

# photo_extractor (pure Python, no OCR)
datas += [(str(ROOT / 'photo_extractor.py'), '.')]

a = Analysis(
    [str(ROOT / 'desktop_app.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'notebook', 'ipython', 'IPython',
        'test', 'tests', 'pytest',
        'paddle', 'paddleocr', 'easyocr',
        'rapidocr_onnxruntime', 'onnxruntime',
        'selenium', 'llama_cpp',
        'torch.distributed', 'torch.testing',
        'torch.cuda',
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
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['model.safetensors'],
    name='AIDocumentSystem',
)
