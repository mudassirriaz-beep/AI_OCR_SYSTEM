"""
One-click build script for AI Document System installer.

What it does:
  1. Creates a CPU-only Python venv (build_venv/)
  2. Installs all required packages (CPU torch, transformers, etc.)
  3. Builds the app with PyInstaller
  4. Downloads + installs Inno Setup if needed
  5. Creates the final installer EXE

Usage:
    python build_installer.py

Output:
    dist/AIDocumentSystem_v3.0_Setup.exe   ← send this to the client
"""
import os, sys, subprocess, urllib.request, shutil
from pathlib import Path

BASE     = Path(__file__).parent
BUILD_D  = Path("D:/AIDocumentSystem_Build")   # build on D: — C: has no space
BUILD_D.mkdir(parents=True, exist_ok=True)
VENV     = BUILD_D / "build_venv"
VENV_PY  = VENV / "Scripts" / "python.exe"
VENV_PIP = VENV / "Scripts" / "pip.exe"
INNO_URL = "https://jrsoftware.org/download.php/is.exe"
INNO_EXE_PATHS = [
    Path("C:/Program Files (x86)/Inno Setup 6/iscc.exe"),
    Path("C:/Program Files/Inno Setup 6/iscc.exe"),
]


def run(cmd, **kwargs):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def find_inno():
    for p in INNO_EXE_PATHS:
        if p.exists():
            return p
    return None


def install_inno():
    print("\n[STEP] Downloading Inno Setup...")
    installer = BASE / "dist" / "_inno_setup_installer.exe"
    installer.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(INNO_URL, installer)
    print("[STEP] Installing Inno Setup silently...")
    subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                    "/NORESTART", "/SP-"], check=True)
    installer.unlink(missing_ok=True)
    inno = find_inno()
    if not inno:
        print("[ERROR] Inno Setup install failed. Install manually from https://jrsoftware.org/isdl.php")
        sys.exit(1)
    return inno


def main():
    print("=" * 60)
    print(" AI Document System — Build Script")
    print("=" * 60)

    # ── Step 1: Create CPU venv (reuse if packages already installed) ─
    torch_installed = (VENV / "Lib" / "site-packages" / "torch").exists()
    if VENV.exists() and not torch_installed:
        print(f"\n[STEP 1] Removing incomplete build venv...")
        shutil.rmtree(VENV)
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    # ── Step 2: Install packages (skip if already installed) ──────
    if not torch_installed:
        print("\n[STEP 2] Installing packages into build venv...")
        print("  Installing CPU-only torch (~800MB, this takes a few minutes)...")
        run([str(VENV_PY), "-m", "pip", "install",
             "torch", "torchvision",
             "--index-url", "https://download.pytorch.org/whl/cpu",
             "--timeout", "300", "--retries", "5"])
        packages = [
            "transformers==4.46.3", "sentencepiece", "Pillow",
            "opencv-python-headless",
            "beautifulsoup4", "requests", "rapidfuzz", "numpy",
            "safetensors", "huggingface-hub", "filelock", "packaging",
            "regex", "tqdm", "pyinstaller",
        ]
        print(f"  Installing {len(packages)} packages...")
        run([str(VENV_PY), "-m", "pip", "install"] + packages + ["--timeout", "300", "--retries", "5"])
    else:
        print("\n[STEP 2] Packages already installed — skipping")

    # ── Step 3: Build with PyInstaller ────────────────────────────
    print("\n[STEP 3] Building app with PyInstaller...")
    print("  (This will take 5–15 minutes — model is 777MB)")

    dist_out = BUILD_D / "dist"
    work_out = BUILD_D / "build"
    dist_dir = dist_out / "AIDocumentSystem"
    if dist_dir.exists():
        print(f"  Removing old dist: {dist_dir}")
        shutil.rmtree(dist_dir)

    run([
        str(VENV_PY), "-m", "PyInstaller",
        "build_app.spec",
        "--clean",
        "--noconfirm",
        f"--distpath={dist_out}",
        f"--workpath={work_out}",
    ], cwd=str(BASE))

    # Verify build succeeded
    exe = dist_dir / "AIDocumentSystem.exe"
    if not exe.exists():
        print(f"[ERROR] Build failed — {exe} not found")
        sys.exit(1)
    print(f"  Build OK → {exe}")

    # ── Step 4: Find / install Inno Setup ────────────────────────
    print("\n[STEP 4] Checking for Inno Setup...")
    inno = find_inno()
    if not inno:
        print("  Inno Setup not found — downloading and installing...")
        inno = install_inno()
    print(f"  Inno Setup found: {inno}")

    # ── Step 5: Create installer ──────────────────────────────────
    print("\n[STEP 5] Creating installer with Inno Setup...")
    run([str(inno), f"/DDistPath={dist_out}", str(BASE / "installer_v4.iss")], cwd=str(BASE))

    installer = BUILD_D / "AIDocumentSystem_v4.0_Setup.exe"
    if installer.exists():
        size_mb = installer.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"  SUCCESS!")
        print(f"  Installer: {installer}")
        print(f"  Size: {size_mb:.0f} MB")
        print(f"{'='*60}")
        print(f"\n  Send this file to your client:")
        print(f"  {installer}")
    else:
        print("[ERROR] Installer not created — check Inno Setup output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
