"""
Builds AI_Document_System_Setup.exe — fully self-contained (~1.7 GB).
Client needs nothing else. No internet required after install.

Bundles:
  msedgedriver.exe         20 MB  Selenium Edge driver
  all-MiniLM-L6-v2        ~87 MB  semantic field matching model
  EasyOCR models          ~93 MB  OCR fallback models
  vlm-model.gguf       ~1,270 MB  Qwen2-VL-2B-Instruct-Q4_K_M  (vision LM)
  vlm-mmproj.gguf        ~295 MB  Qwen2-VL-2B vision projector
  Python source files      ~1 MB  all app code + templates

NOTE: Download VLM model files first from HuggingFace:
  https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF
  → Qwen2-VL-2B-Instruct-Q4_K_M.gguf  →  rename to  vlm-model.gguf
  → mmproj-Qwen2-VL-2B-Instruct-f16.gguf  →  rename to  vlm-mmproj.gguf
  → place both in:  models_export/vlm/
"""
import os, sys, shutil, subprocess

ROOT     = os.path.dirname(os.path.abspath(__file__))
WINRAR   = r"C:\Program Files\WinRAR\WinRAR.exe"
STAGING  = os.path.join(ROOT, "_staging")
OUTPUT   = os.path.join(ROOT, "AI_Document_System_Setup.exe")
COMMENT  = os.path.join(ROOT, "_sfx_comment.txt")

# Source locations
MSEDGE       = os.path.join(ROOT, "msedgedriver.exe")
MODEL_EXPORT = os.path.join(ROOT, "models_export", "all-MiniLM-L6-v2")
VLM_EXPORT   = os.path.join(ROOT, "models_export", "vlm")   # vlm-model.gguf + vlm-mmproj.gguf
EASYOCR_SRC  = os.path.join(os.path.expanduser("~"), ".EasyOCR", "model")

PY_FILES = [
    "main.py", "form_filler_ui.py", "agent_orchestrator.py",
    "agent_form_inspector.py", "agent_form_filler.py", "agent_field_mapper.py",
    "slm_client.py", "semantic_mapper.py", "vlm_extractor.py",
    "brain_format_cnic.py", "brain_format_dl.py", "brain_format.py",
    "profile_builder.py", "ocr_engine.py", "form_mapper.py", "preprocess.py",
    "requirements.txt",
]

SFX_COMMENT = """;The comment below contains SFX script commands

Title=AI Document System - Full Setup
Text
This installs the complete AI Document System.

Everything is included - no internet required.
Python 3.9 or later must be installed (python.org).
EndText
BeginPrompt=Install AI Document System?
Path=%LOCALAPPDATA%\\AI_Document_System_Package
Setup=python AI_Document_System_LAUNCH.py
Silent=1
Overwrite=2
"""

LAUNCHER_SCRIPT = '''#!/usr/bin/env python3
"""
AI Document System — Launcher
VLM edition: Qwen2-VL-2B-Instruct
No separate AI server required — model loads on first document scan.
"""
import os, sys, subprocess, time, socket, webbrowser

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
SRC_DIR        = os.path.join(SCRIPT_DIR, "src")
ST_MODELS_DIR  = os.path.join(SRC_DIR, "models", "all-MiniLM-L6-v2")
EASYOCR_DIR    = os.path.join(SRC_DIR, "models", "easyocr")
VLM_MODEL_DIR  = os.path.join(SRC_DIR, "models", "vlm")
REQ_FILE       = os.path.join(SRC_DIR, "requirements.txt")
FLAG_FILE      = os.path.join(SRC_DIR, ".packages_ok")
APP_PORT       = 5001


def port_open(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False


def install_packages():
    if os.path.exists(FLAG_FILE):
        print("[2/3] Packages already installed — skipping.")
        return
    print("[2/3] Installing Python packages (first run only)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQ_FILE,
                    "--quiet", "--no-warn-script-location"])
    open(FLAG_FILE, "w").close()
    print("[OK] Packages installed.")


def start_flask():
    env = os.environ.copy()
    env["ST_MODELS_DIR"]      = ST_MODELS_DIR
    env["EASYOCR_MODELS_DIR"] = EASYOCR_DIR
    env["VLM_MODEL_DIR"]      = VLM_MODEL_DIR
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc  = subprocess.Popen(
        [sys.executable, os.path.join(SRC_DIR, "main.py")],
        cwd=SRC_DIR, env=env, creationflags=flags,
    )
    for _ in range(30):
        time.sleep(0.5)
        if port_open(APP_PORT):
            print(f"[OK] App running at http://127.0.0.1:{APP_PORT}")
            return proc
    print("[WARN] App slow to start — opening browser anyway.")
    return proc


def main():
    print("=" * 52)
    print("  AI Document System  (VLM Edition)")
    print("=" * 52)
    print("\\n[1/3] Files ready.")
    install_packages()
    print("\\n[3/3] Launching app...")
    app_proc = start_flask()
    webbrowser.open(f"http://127.0.0.1:{APP_PORT}")
    print("\\n" + "=" * 52)
    print(f"  App:   http://127.0.0.1:{APP_PORT}")
    print("  Note:  First document scan loads the VLM (~30 sec).")
    print("  Keep this window open.  Ctrl+C to stop.")
    print("=" * 52 + "\\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\nStopping...")
        app_proc.terminate()
        print("Done.")


if __name__ == "__main__":
    main()
'''

# ── Helpers ───────────────────────────────────────────────────────────────────
def mb(path):
    if os.path.isfile(path):
        return os.path.getsize(path) // 1_048_576
    if os.path.isdir(path):
        return sum(f.stat().st_size
                   for f in __import__('pathlib').Path(path).rglob('*')
                   if f.is_file()) // 1_048_576
    return 0

def check(path, label):
    if not os.path.exists(path):
        print(f"[ERR] {label} not found: {path}")
        sys.exit(1)
    print(f"[OK]  {label:35s} {mb(path):6d} MB")

# ── Pre-flight ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("  AI Document System — VLM EXE Builder")
print("=" * 60)
check(WINRAR,        "WinRAR")
check(MSEDGE,        "msedgedriver.exe")
check(MODEL_EXPORT,  "all-MiniLM-L6-v2 export")
check(VLM_EXPORT,    "VLM models (vlm/ dir)")
check(os.path.join(VLM_EXPORT, "vlm-model.gguf"),  "vlm-model.gguf")
check(os.path.join(VLM_EXPORT, "vlm-mmproj.gguf"), "vlm-mmproj.gguf")
check(EASYOCR_SRC,   "EasyOCR fallback models")

# ── Build staging directory ────────────────────────────────────────────────────
print("\n[..] Building staging directory...")
if os.path.exists(STAGING):
    shutil.rmtree(STAGING)
os.makedirs(STAGING)

src_dir = os.path.join(STAGING, "src")
os.makedirs(src_dir)

# Edge driver → staging root
print(f"  Copying msedgedriver.exe ({mb(MSEDGE)} MB)...")
shutil.copy2(MSEDGE, os.path.join(STAGING, "msedgedriver.exe"))

# Launcher → staging root
with open(os.path.join(STAGING, "AI_Document_System_LAUNCH.py"),
          "w", encoding="utf-8") as f:
    f.write(LAUNCHER_SCRIPT)
print("  Written AI_Document_System_LAUNCH.py")

# Python source files → staging/src/
for fname in PY_FILES:
    p = os.path.join(ROOT, fname)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(src_dir, fname))
print(f"  Copied {len(PY_FILES)} source files → src/")

# Templates → staging/src/templates/
tmpl_src = os.path.join(ROOT, "templates")
tmpl_dst = os.path.join(src_dir, "templates")
if os.path.exists(tmpl_src):
    shutil.copytree(tmpl_src, tmpl_dst)
    print("  Copied templates/")

# all-MiniLM-L6-v2 → staging/src/models/all-MiniLM-L6-v2/
st_dst = os.path.join(src_dir, "models", "all-MiniLM-L6-v2")
shutil.copytree(MODEL_EXPORT, st_dst)
print(f"  Copied all-MiniLM-L6-v2 ({mb(st_dst)} MB) → src/models/all-MiniLM-L6-v2/")

# VLM models → staging/src/models/vlm/
vlm_dst = os.path.join(src_dir, "models", "vlm")
shutil.copytree(VLM_EXPORT, vlm_dst)
print(f"  Copied VLM models ({mb(vlm_dst)} MB) → src/models/vlm/")

# EasyOCR fallback models → staging/src/models/easyocr/
eocr_dst = os.path.join(src_dir, "models", "easyocr")
shutil.copytree(EASYOCR_SRC, eocr_dst)
print(f"  Copied EasyOCR models ({mb(eocr_dst)} MB) → src/models/easyocr/")

total_staging = mb(STAGING)
print(f"\n  Staging total: {total_staging} MB")

# ── Write SFX comment ──────────────────────────────────────────────────────────
with open(COMMENT, "w", encoding="utf-8") as f:
    f.write(SFX_COMMENT)

# ── Remove old output ─────────────────────────────────────────────────────────
if os.path.exists(OUTPUT):
    os.remove(OUTPUT)
    print("[OK] Old EXE removed.")

# ── Build SFX ─────────────────────────────────────────────────────────────────
print(f"\n[..] Building SFX EXE from {total_staging} MB of files...")
print("     (This will take several minutes)")
result = subprocess.run(
    [WINRAR, "a", "-sfx", f"-z{COMMENT}", "-r", "-m0", "-ibck", OUTPUT, "*"],
    cwd=STAGING,
)

# ── Cleanup ───────────────────────────────────────────────────────────────────
try:
    os.remove(COMMENT)
    shutil.rmtree(STAGING)
except Exception:
    pass

if result.returncode != 0 or not os.path.exists(OUTPUT):
    print(f"\n[ERR] Build failed (exit code {result.returncode})")
    sys.exit(1)

final_mb = os.path.getsize(OUTPUT) // 1_048_576
print(f"\n{'='*60}")
print(f"  DONE:  AI_Document_System_Setup.exe  ({final_mb:,} MB)")
print(f"  Path:  {OUTPUT}")
print(f"{'='*60}")
print("""
Client does ONE thing:
  Double-click AI_Document_System_Setup.exe
  (Python 3.9+ must be installed — python.org)

VLM loads on first document scan (~30 sec one-time wait).
No internet needed after installation.
""")
