"""Download Qwen2-VL-2B-Instruct GGUF files from HuggingFace."""
import os, sys, time, urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "models_export", "vlm")
os.makedirs(DEST, exist_ok=True)

FILES = [
    (
        "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF"
        "/resolve/main/Qwen2-VL-2B-Instruct-Q4_K_M.gguf",
        "vlm-model.gguf",
        1_340_000_000,   # ~1.27 GB
    ),
    (
        "https://huggingface.co/bartowski/Qwen2-VL-2B-Instruct-GGUF"
        "/resolve/main/mmproj-Qwen2-VL-2B-Instruct-f16.gguf",
        "vlm-mmproj.gguf",
        309_000_000,     # ~295 MB
    ),
]


def _bar(done, total, width=40):
    pct  = done / total if total else 0
    fill = int(width * pct)
    bar  = "█" * fill + "░" * (width - fill)
    mb_d = done  / 1_048_576
    mb_t = total / 1_048_576
    return f"[{bar}] {mb_d:,.0f}/{mb_t:,.0f} MB  {pct*100:.1f}%"


def download(url, dest_path, approx_bytes):
    name  = os.path.basename(dest_path)
    if os.path.exists(dest_path):
        actual = os.path.getsize(dest_path)
        if actual > approx_bytes * 0.95:
            print(f"  SKIP  {name}  (already exists, {actual//1_048_576} MB)")
            return
        print(f"  RESUMING {name} (partial: {actual//1_048_576} MB)")

    headers = {}
    existing = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"

    req  = urllib.request.Request(url, headers={**headers,
        "User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    total = int(resp.headers.get("Content-Length", approx_bytes)) + existing

    mode  = "ab" if existing else "wb"
    start = time.time()
    done  = existing

    print(f"\n  Downloading {name}  ({total//1_048_576} MB)")
    with open(dest_path, mode) as f:
        while True:
            chunk = resp.read(1 << 20)   # 1 MB chunks
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            elapsed = time.time() - start
            speed   = (done - existing) / elapsed if elapsed else 1
            eta     = (total - done) / speed if speed else 0
            print(f"\r  {_bar(done, total)}  ETA {eta/60:.1f} min ", end="", flush=True)

    print(f"\n  Done: {os.path.getsize(dest_path)//1_048_576} MB")


print("=" * 60)
print("  Downloading Qwen2-VL-2B-Instruct model files")
print("=" * 60)
ok = True
for url, fname, approx in FILES:
    dest = os.path.join(DEST, fname)
    try:
        download(url, dest, approx)
    except Exception as e:
        print(f"\n  ERROR downloading {fname}: {e}")
        ok = False

print("\n" + "=" * 60)
if ok:
    print("  ALL FILES DOWNLOADED SUCCESSFULLY")
    print("  Run:  python _build_exe_full.py")
else:
    print("  SOME FILES FAILED — check internet connection and retry")
print("=" * 60)
sys.exit(0 if ok else 1)
