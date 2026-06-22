"""
Builds AI_Document_System_Setup.exe — WinRAR self-extracting archive.
Bundles: docextract.exe + model.gguf + AI_Document_System_LAUNCH.py
Client just double-clicks the exe. No Ollama, no separate downloads.
"""
import os, subprocess, shutil, sys

ROOT        = os.path.dirname(os.path.abspath(__file__))
WINRAR      = r"C:\Program Files\WinRAR\WinRAR.exe"
MODEL_SRC   = r"C:\Users\ZAH\Pictures\Dataset_Images (1)\finetune\model_output_v11\gguf\docextract-v11-llama3.2-1b.Q8_0.gguf"
DOCEXTRACT  = os.path.join(ROOT, "docextract.exe")
LAUNCHER    = os.path.join(ROOT, "AI_Document_System_LAUNCH.py")
MODEL_DEST  = os.path.join(ROOT, "model.gguf")          # renamed copy in project root
OUTPUT      = os.path.join(ROOT, "AI_Document_System_Setup.exe")
COMMENT_TXT = os.path.join(ROOT, "_sfx_comment.txt")

# ── SFX configuration ─────────────────────────────────────────────────────────
SFX_COMMENT = """;The comment below contains SFX script commands

Title=AI Document System v11 - Setup
Text
This package installs the AI Document System v11.

Requirements:
  - Python 3.9 or later  (python.org)
  - Internet on first run (for pip packages)

Everything else is included.
EndText
BeginPrompt=Install AI Document System v11?
Path=%LOCALAPPDATA%\\AI_Document_System_Package
Setup=python AI_Document_System_LAUNCH.py
Silent=1
Overwrite=2
"""

# ── Pre-flight checks ─────────────────────────────────────────────────────────
def check(path, label):
    if not os.path.exists(path):
        print(f"[ERR] {label} not found:\n      {path}")
        sys.exit(1)
    mb = os.path.getsize(path) // 1_048_576
    print(f"[OK]  {label:20s}  {mb:6d} MB")

print("=" * 56)
print("  AI Document System — EXE Builder")
print("=" * 56)
check(WINRAR,      "WinRAR")
check(MODEL_SRC,   "model (source)")
check(DOCEXTRACT,  "docextract.exe")
check(LAUNCHER,    "LAUNCH.py")

# ── Copy model to project root (renamed to model.gguf) ────────────────────────
if not os.path.exists(MODEL_DEST):
    gb = os.path.getsize(MODEL_SRC) / 1_073_741_824
    print(f"\n[..] Copying model ({gb:.2f} GB) → model.gguf  (takes ~1 min)...")
    shutil.copy2(MODEL_SRC, MODEL_DEST)
    print("[OK] model.gguf ready.")
else:
    print(f"[OK] model.gguf already present.")

# ── Write SFX comment file ─────────────────────────────────────────────────────
with open(COMMENT_TXT, "w", encoding="utf-8") as f:
    f.write(SFX_COMMENT)
print("[OK] SFX config written.")

# ── Remove old output ─────────────────────────────────────────────────────────
if os.path.exists(OUTPUT):
    os.remove(OUTPUT)
    print("[OK] Old EXE removed.")

# ── Build SFX ─────────────────────────────────────────────────────────────────
print("\n[..] Building SFX EXE (this takes a few minutes for 1.5 GB)...")
cmd = [
    WINRAR, "a",
    "-sfx",              # self-extracting
    f"-z{COMMENT_TXT}",  # SFX config / autorun
    "-ep",               # strip folder paths — files land flat in extraction dir
    "-m0",               # store without compression (binary files won't shrink)
    "-ibck",             # run in background (no WinRAR window)
    OUTPUT,
    DOCEXTRACT,          # docextract.exe
    MODEL_DEST,          # model.gguf
    LAUNCHER,            # AI_Document_System_LAUNCH.py
]

print(f"     {' '.join(cmd[:6])} ...")
result = subprocess.run(cmd)

# ── Cleanup ───────────────────────────────────────────────────────────────────
try:
    os.remove(COMMENT_TXT)
except Exception:
    pass

if result.returncode != 0:
    print(f"\n[ERR] WinRAR exited with code {result.returncode}")
    sys.exit(1)

if not os.path.exists(OUTPUT):
    print("[ERR] Output EXE not created.")
    sys.exit(1)

mb = os.path.getsize(OUTPUT) // 1_048_576
print(f"\n{'='*56}")
print(f"  DONE:  AI_Document_System_Setup.exe  ({mb:,} MB)")
print(f"  Path:  {OUTPUT}")
print(f"{'='*56}")
print("""
How to deliver:
  Upload to Google Drive / WeTransfer
  Send the link to client

Client does ONE thing:
  Double-click AI_Document_System_Setup.exe
  (Python must be installed — python.org)
""")
