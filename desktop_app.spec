# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Collect everything needed for paddleocr, easyocr, cv2
datas = []
binaries = []
hiddenimports = []

# PaddleOCR
paddle_datas, paddle_binaries, paddle_hidden = collect_all('paddleocr')
datas     += paddle_datas
binaries  += paddle_binaries
hiddenimports += paddle_hidden

# PaddlePaddle
pp_datas, pp_binaries, pp_hidden = collect_all('paddle')
datas     += pp_datas
binaries  += pp_binaries
hiddenimports += pp_hidden

# EasyOCR
easy_datas, easy_binaries, easy_hidden = collect_all('easyocr')
datas     += easy_datas
binaries  += easy_binaries
hiddenimports += easy_hidden

# OpenCV
cv_datas, cv_binaries, cv_hidden = collect_all('cv2')
datas     += cv_datas
binaries  += cv_binaries
hiddenimports += cv_hidden

# Other hidden imports
hiddenimports += [
    'PIL', 'PIL.Image', 'PIL.ImageOps',
    'bs4', 'werkzeug',
    'requests', 'urllib3', 'charset_normalizer',
    'skimage', 'scipy', 'shapely',
    'pyclipper', 'imgaug',
    'yaml', 'six', 'tqdm',
]

# Include templates folder
datas += [('templates', 'templates')]

a = Analysis(
    ['desktop_app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'notebook', 'ipython', 'IPython', 'test', 'tests'],
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
    console=False,   # no black CMD window
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
