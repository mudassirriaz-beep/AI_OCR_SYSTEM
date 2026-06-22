"""
bundle_models.py
Fully automatic — downloads everything needed, no manual prerequisites.

Downloads:
  1. Ollama portable exe  (from GitHub releases)
  2. llama3.2:1b model   (via downloaded ollama.exe, stored in bundle/)
  3. EasyOCR models      (craft_mlt_25k.pth + english_g2.pth)

Output layout:
  bundle/
    ollama/ollama.exe
    ollama_models/manifests/...
    ollama_models/blobs/...
    models/easyocr/*.pth
"""

import json, os, subprocess, sys, shutil, time, urllib.request, zipfile
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_MODEL     = "docextract:v11"
CUSTOM_GGUF_PATH = r"C:\Users\ZAH\Pictures\Dataset_Images (1)\finetune\model_output_v11\gguf\docextract-v11-llama3.2-1b.Q8_0.gguf"
BUNDLE_DIR       = Path(__file__).parent / "bundle"
OLLAMA_DIR       = BUNDLE_DIR / "ollama"
OLLAMA_EXE       = OLLAMA_DIR / "ollama.exe"
OLLAMA_MODELS    = BUNDLE_DIR / "ollama_models"
EASYOCR_DIR      = BUNDLE_DIR / "models" / "easyocr"

# GitHub latest release download URL for portable Ollama (Windows x64)
OLLAMA_ZIP_URL = (
    "https://github.com/ollama/ollama/releases/latest/download/"
    "ollama-windows-amd64.zip"
)

EASYOCR_MODELS = ["craft_mlt_25k.pth", "english_g2.pth"]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _mb(path: Path) -> int:
    return path.stat().st_size // 1_048_576 if path.exists() else 0

def _makedirs(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _download(url: str, dest: Path, label: str):
    _makedirs(dest.parent)
    print(f"  Downloading {label}…")
    try:
        def _progress(count, block, total):
            pct = min(100, int(count * block * 100 / total)) if total > 0 else 0
            print(f"\r  {pct}%  ", end="", flush=True)
        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print(f"\r  Done  ({_mb(dest)} MB)        ")
    except Exception as e:
        print(f"\n  ERROR downloading {label}: {e}")
        sys.exit(1)

# ── Step 1: Ollama binary ──────────────────────────────────────────────────────

def get_ollama():
    print("\n[1/3] Ollama portable binary")

    # Check system PATH
    system_ollama = shutil.which("ollama")
    system_lib = None
    if system_ollama:
        sys_p = Path(system_ollama)
        candidate_lib = sys_p.parent / "lib"
        if candidate_lib.exists():
            system_lib = candidate_lib

    # If already present, check if we need to copy lib
    if OLLAMA_EXE.exists():
        print(f"  Already present  ({_mb(OLLAMA_EXE)} MB)")
        # Copy lib if missing from bundle but present on system
        dest_lib = OLLAMA_DIR / "lib"
        if system_lib and not dest_lib.exists():
            print(f"  Copying system Ollama 'lib' folder to {dest_lib}...")
            try:
                shutil.copytree(system_lib, dest_lib)
                print("  Copied 'lib' folder.")
            except Exception as e:
                print(f"  Warning: failed to copy 'lib': {e}")
        return

    if system_ollama:
        print(f"  Found system Ollama at {system_ollama} — copying")
        _makedirs(OLLAMA_DIR)
        shutil.copy2(system_ollama, OLLAMA_EXE)
        print(f"  Copied  ({_mb(OLLAMA_EXE)} MB)")
        if system_lib:
            dest_lib = OLLAMA_DIR / "lib"
            print(f"  Copying system Ollama 'lib' folder to {dest_lib}...")
            try:
                shutil.copytree(system_lib, dest_lib)
                print("  Copied 'lib' folder.")
            except Exception as e:
                print(f"  Warning: failed to copy 'lib': {e}")
        return

    # Download portable zip from GitHub
    zip_path = OLLAMA_DIR / "ollama.zip"
    _makedirs(OLLAMA_DIR)
    _download(OLLAMA_ZIP_URL, zip_path, "ollama-windows-amd64.zip")

    print("  Extracting…")
    with zipfile.ZipFile(zip_path, "r") as zf:
        # The zip may contain ollama.exe at the root or in a sub-folder
        for member in zf.namelist():
            if member.lower().endswith("ollama.exe"):
                with zf.open(member) as src, open(OLLAMA_EXE, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                break
        else:
            # Some releases ship the exe at root level
            zf.extractall(OLLAMA_DIR)

    zip_path.unlink(missing_ok=True)

    if not OLLAMA_EXE.exists():
        # Rename if extracted with different name
        exes = list(OLLAMA_DIR.glob("*.exe"))
        if exes:
            exes[0].rename(OLLAMA_EXE)

    if not OLLAMA_EXE.exists():
        print("  ERROR: ollama.exe not found after extraction")
        sys.exit(1)

    print(f"  OK  ({_mb(OLLAMA_EXE)} MB)")

# ── Step 2: Pull the LLM model into bundle/ ────────────────────────────────────

def get_model():
    print(f"\n[2/3] LLM model: {OLLAMA_MODEL}")

    _makedirs(OLLAMA_MODELS)

    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(OLLAMA_MODELS)
    env["OLLAMA_HOST"]   = "127.0.0.1:11435"   # use non-standard port to avoid conflicts

    print("  Starting temporary Ollama server…")
    server = subprocess.Popen(
        [str(OLLAMA_EXE), "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    # Wait for server to be ready
    import urllib.request
    import urllib.error
    for _ in range(60):
        try:
            urllib.request.urlopen("http://127.0.0.1:11435/api/tags", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        server.terminate()
        print("  ERROR: Ollama server did not start in 60 s")
        sys.exit(1)

    # Check if model is already registered in this private OLLAMA_MODELS
    already_registered = False
    try:
        req = urllib.request.urlopen("http://127.0.0.1:11435/api/tags", timeout=5)
        if req.status == 200:
            tags_data = json.loads(req.read().decode())
            tag_names = [m["name"] for m in tags_data.get("models", [])]
            if OLLAMA_MODEL in tag_names or f"{OLLAMA_MODEL}:latest" in tag_names:
                already_registered = True
    except Exception as e:
        print(f"  Warning: failed to check tags: {e}")

    if already_registered:
        print("  Model already registered in bundle — skipping creation")
        server.terminate()
        try: server.wait(timeout=5)
        except Exception: server.kill()
        return

    # Check if local GGUF file exists
    if not os.path.exists(CUSTOM_GGUF_PATH):
        server.terminate()
        try: server.wait(timeout=5)
        except Exception: server.kill()
        print(f"  ERROR: Custom GGUF file not found at: {CUSTOM_GGUF_PATH}")
        sys.exit(1)

    print(f"  Creating model {OLLAMA_MODEL} from local GGUF…")
    modelfile_content = f'FROM "{CUSTOM_GGUF_PATH}"\n'
    modelfile_path = BUNDLE_DIR / "Modelfile_temp"
    try:
        with open(modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)
        
        # Run ollama.exe create OLLAMA_MODEL -f Modelfile_temp
        rc = subprocess.call(
            [str(OLLAMA_EXE), "create", OLLAMA_MODEL, "-f", str(modelfile_path)],
            env=env,
        )
    finally:
        if modelfile_path.exists():
            modelfile_path.unlink()

    server.terminate()
    try: server.wait(timeout=5)
    except Exception: server.kill()

    if rc != 0:
        print("  ERROR: ollama create failed")
        sys.exit(1)

    # Count total blob size
    blobs = list((OLLAMA_MODELS / "blobs").glob("*"))
    total = sum(b.stat().st_size for b in blobs) // 1_048_576
    print(f"  OK  {len(blobs)} blobs  ({total} MB)")

# ── Step 3: EasyOCR models ─────────────────────────────────────────────────────

def get_easyocr():
    print("\n[3/3] EasyOCR English models")
    _makedirs(EASYOCR_DIR)

    # Check if already downloaded
    already = all((EASYOCR_DIR / m).exists() for m in EASYOCR_MODELS)
    if already:
        print("  Already present — skipping download")
        return

    # Ensure numpy<2 (EasyOCR/PyTorch compiled against NumPy 1.x)
    try:
        import numpy as _np
        if tuple(int(x) for x in _np.__version__.split(".")[:2]) >= (2, 0):
            print("  Downgrading numpy to <2 for EasyOCR/PyTorch compatibility...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", "numpy<2"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # Reload numpy
            import importlib
            import numpy
            importlib.reload(numpy)
    except Exception:
        pass

    print("  Using EasyOCR built-in downloader...")
    try:
        import easyocr
        # EasyOCR downloads models automatically to the specified directory
        _reader = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=True,
            model_storage_directory=str(EASYOCR_DIR),
            download_enabled=True,
        )
        del _reader
        print("  OK  EasyOCR models downloaded")
    except Exception as e:
        print(f"  WARNING: EasyOCR download failed: {e}")
        print("  EasyOCR will download models on first use (requires internet on first run)")
        print("  Continuing build without EasyOCR models bundled...")

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(" AI Document System — Auto Model Bundler")
    print("=" * 60)

    get_ollama()
    get_model()
    get_easyocr()

    total = sum(
        f.stat().st_size
        for f in BUNDLE_DIR.rglob("*") if f.is_file()
    ) // 1_048_576

    print("\n" + "=" * 60)
    print(f"BUNDLE READY  —  {total} MB total in bundle/")
    print("=" * 60)
    print("\nNext: pyinstaller AIDocumentSystem_Complete.spec --clean")
    print("Then: iscc installer_complete.iss\n")
