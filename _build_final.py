"""
Builds the final delivery:
  AI_Document_System_Delivery.html  — client opens this, clicks download
  AI_Document_System_LAUNCH.py      — downloaded by client, double-click to run
"""
import base64, io, json, os, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

REQUIREMENTS = """\
flask>=2.3
werkzeug>=2.3
requests>=2.28
beautifulsoup4>=4.12
opencv-python>=4.8
Pillow>=10.0
numpy>=1.24
PyMuPDF>=1.23
rapidocr-onnxruntime>=1.3
rapidfuzz>=3.0
easyocr>=1.7
selenium>=4.15
sentence-transformers>=2.7
"""

PY_FILES = [
    "main.py","form_filler_ui.py","agent_orchestrator.py",
    "agent_form_inspector.py","agent_form_filler.py","agent_field_mapper.py",
    "slm_client.py","brain_format_cnic.py","brain_format_dl.py","brain_format.py",
    "profile_builder.py","ocr_engine.py","form_mapper.py","preprocess.py","bundle_models.py",
    "semantic_mapper.py",
]

# Collect all source files
files = {}
for fname in PY_FILES:
    p = os.path.join(ROOT, fname)
    if os.path.exists(p):
        files[fname] = open(p, "rb").read()
for tmpl in ["form_filler.html", "review.html"]:
    p = os.path.join(ROOT, "templates", tmpl)
    if os.path.exists(p):
        files[f"templates/{tmpl}"] = open(p, "rb").read()
files["requirements.txt"] = REQUIREMENTS.encode()

files_b64 = {k: base64.b64encode(v).decode() for k, v in files.items()}

# ── Launcher script ───────────────────────────────────────────────────────────
LAUNCHER = '''#!/usr/bin/env python3
"""
AI Document System — Self-Extracting Launcher (llamafile edition)

Place this file in the SAME folder as:
  docextract.exe   (305 MB — llamafile runtime)
  model.gguf       (1.23 GB — fine-tuned LLaMA 3.2 1B)

Then double-click this file OR run:  python AI_Document_System_LAUNCH.py
"""
import base64, json, os, subprocess, sys, time, webbrowser, socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR    = os.path.join(SCRIPT_DIR, "AI_Document_System")
LLAMAFILE  = os.path.join(SCRIPT_DIR, "docextract.exe")
MODEL_GGUF = os.path.join(SCRIPT_DIR, "model.gguf")
LLM_PORT   = 8080
APP_PORT   = 5001

FILES = ''' + json.dumps(files_b64, indent=2) + '''

def extract():
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(os.path.join(APP_DIR, "templates"), exist_ok=True)
    for rel, b64 in FILES.items():
        dest = os.path.join(APP_DIR, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(base64.b64decode(b64))
    print(f"[OK] Files extracted to: {APP_DIR}")

def install_packages():
    req = os.path.join(APP_DIR, "requirements.txt")
    print("[..] Installing Python packages (first run only)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", req, "--quiet"])
    print("[OK] Packages ready.")

def port_open(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False

def start_llamafile():
    if port_open(LLM_PORT):
        print(f"[OK] llamafile already running on port {LLM_PORT}.")
        return None

    if not os.path.exists(LLAMAFILE):
        print(f"[ERR] docextract.exe not found at: {LLAMAFILE}")
        print("      Place docextract.exe in the same folder as this script.")
        sys.exit(1)

    if not os.path.exists(MODEL_GGUF):
        print(f"[ERR] model.gguf not found at: {MODEL_GGUF}")
        print("      Place model.gguf in the same folder as this script.")
        sys.exit(1)

    print(f"[..] Starting llamafile AI engine (port {LLM_PORT})...")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [LLAMAFILE, "-m", MODEL_GGUF, "--server",
         "--host", "127.0.0.1", "--port", str(LLM_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        cwd=SCRIPT_DIR,
    )

    print("[..] Waiting for model to load (up to 60s)...")
    for i in range(60):
        time.sleep(1)
        if port_open(LLM_PORT):
            print(f"[OK] llamafile ready on port {LLM_PORT}.")
            return proc
        if proc.poll() is not None:
            print("[ERR] llamafile crashed. Check docextract.exe and model.gguf.")
            sys.exit(1)

    print("[WARN] llamafile taking long — continuing anyway.")
    return proc

def start_flask():
    main_py = os.path.join(APP_DIR, "main.py")
    print(f"[..] Starting web app...")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, main_py],
        cwd=APP_DIR,
        creationflags=flags,
    )
    for _ in range(30):
        time.sleep(0.5)
        if port_open(APP_PORT):
            print(f"[OK] App running at http://127.0.0.1:{APP_PORT}")
            return proc
    print("[WARN] App slow to start — opening browser anyway.")
    return proc

def main():
    print("=" * 56)
    print("  AI Document System  v11  —  llamafile Edition")
    print("=" * 56)

    first_run = not os.path.exists(os.path.join(APP_DIR, "main.py"))

    print("\\n[1/4] Extracting source files...")
    extract()

    if first_run:
        print("\\n[2/4] Installing packages (first run only)...")
        install_packages()
    else:
        print("\\n[2/4] Packages already installed — skipping.")

    print("\\n[3/4] Starting AI engine (llamafile)...")
    llm_proc = start_llamafile()

    print("\\n[4/4] Launching app...")
    app_proc = start_flask()

    webbrowser.open(f"http://127.0.0.1:{APP_PORT}")

    print("\\n" + "=" * 56)
    print("  App is running at http://127.0.0.1:5001")
    print("  Keep this window open while using the app.")
    print("  Press Ctrl+C to stop everything.")
    print("=" * 56)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\nStopping...")
        if llm_proc: llm_proc.terminate()
        if app_proc: app_proc.terminate()
        print("Stopped.")

if __name__ == "__main__":
    main()
'''

launcher_path = os.path.join(ROOT, "AI_Document_System_LAUNCH.py")
with open(launcher_path, "w", encoding="utf-8") as f:
    f.write(LAUNCHER)
kb = os.path.getsize(launcher_path) // 1024
print(f"[1] Launcher: AI_Document_System_LAUNCH.py  ({kb} KB)")

# ── HTML delivery ─────────────────────────────────────────────────────────────
launcher_b64 = base64.b64encode(open(launcher_path,"rb").read()).decode()

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Document System &mdash; Client Delivery</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:"Segoe UI",system-ui,sans-serif;min-height:100vh}
.hdr{background:linear-gradient(135deg,#7c3aed,#4f46e5);padding:26px 40px}
.hdr h1{font-size:1.45rem;font-weight:800;color:#fff}
.hdr .sub{font-size:.88rem;color:#ddd6fe;margin-top:4px}
.v{background:rgba(255,255,255,.18);color:#fff;font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:99px;margin-left:10px;vertical-align:middle}
.wrap{max-width:900px;margin:0 auto;padding:40px 24px}
.hero{text-align:center;background:#1e293b;border:1px solid #334155;border-radius:18px;padding:48px 32px;margin-bottom:28px}
.hero h2{font-size:1.7rem;font-weight:800;margin-bottom:10px;background:linear-gradient(90deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero p{color:#94a3b8;font-size:.95rem;line-height:1.7;max-width:520px;margin:0 auto 26px}
.btn{display:inline-flex;align-items:center;gap:10px;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;border:none;border-radius:12px;padding:14px 32px;font-size:.98rem;font-weight:700;cursor:pointer;transition:opacity .2s,transform .15s}
.btn:hover{opacity:.88;transform:translateY(-2px)}
.btn svg{width:18px;height:18px}
.note{font-size:.76rem;color:#64748b;margin-top:10px}
.card{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:24px 28px;margin-bottom:22px}
.sec{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#64748b;margin-bottom:16px}
.step{display:flex;gap:14px;align-items:flex-start;margin-bottom:13px}
.step:last-child{margin-bottom:0}
.num{color:#fff;font-size:.7rem;font-weight:800;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}
.sb strong{display:block;color:#e2e8f0;font-size:.88rem;margin-bottom:2px}
.sb span{color:#64748b;font-size:.8rem;line-height:1.5}
code{background:#0f172a;border:1px solid #334155;border-radius:5px;padding:2px 7px;font-size:.79rem;color:#a78bfa;font-family:Consolas,monospace}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:22px}
@media(max-width:620px){.grid{grid-template-columns:1fr}}
.fcard{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:18px 20px}
.fcard h3{font-size:.85rem;font-weight:700;color:#e2e8f0;margin-bottom:6px;display:flex;align-items:center;gap:8px}
.fcard p{font-size:.78rem;color:#64748b;line-height:1.5}
.fcard .sz{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:2px 8px;font-size:.7rem;color:#a78bfa;margin-top:6px;font-family:Consolas,monospace}
.warn{background:#1c1a0f;border:1px solid #713f12;border-radius:12px;padding:16px 20px;margin-bottom:22px;font-size:.82rem;color:#fbbf24;line-height:1.6}
.warn strong{color:#f59e0b}
.tbl{width:100%;border-collapse:collapse}
.tbl th,.tbl td{text-align:left;padding:8px 14px;font-size:.78rem;border-bottom:1px solid #0f172a}
.tbl th{color:#64748b;font-weight:600;background:#0f172a}
.tbl td{color:#e2e8f0}
.tbl tr:last-child td{border-bottom:none}
.tag{display:inline-block;padding:2px 7px;border-radius:5px;font-size:.67rem;font-weight:700}
.t1{background:#1d1b4b;color:#a5b4fc}.t2{background:#1a2e1a;color:#86efac}
.t3{background:#2d1f00;color:#fbbf24}.t4{background:#1a2030;color:#93c5fd}
.t5{background:#1f1a2e;color:#c4b5fd}.t6{background:#1a1a1a;color:#94a3b8}
</style>
</head>
<body>
<div class="hdr">
  <h1>AI Document System <span class="v">v11</span></h1>
  <div class="sub">CNIC &amp; Driving License &rarr; Intelligent Form Auto-Fill &nbsp;&bull;&nbsp; llamafile Edition &nbsp;&bull;&nbsp; No Ollama Required</div>
</div>
<div class="wrap">

  <div class="hero">
    <h2>Download Launcher</h2>
    <p>One Python file that extracts all source code, installs packages, starts the AI engine and opens the app automatically.</p>
    <button class="btn" onclick="dl()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Download AI_Document_System_LAUNCH.py
    </button>
    <div class="note">Self-extracting &bull; Auto-installs packages &bull; Auto-launches app</div>
  </div>

  <div class="warn">
    <strong>Before running the launcher, you need 2 files from Google Drive:</strong><br>
    &bull; <code>docextract.exe</code> &nbsp;(305 MB &mdash; llamafile AI runtime)<br>
    &bull; <code>model.gguf</code> &nbsp;(1.23 GB &mdash; fine-tuned LLaMA 3.2 1B model)<br>
    Place both files in the <strong>same folder</strong> as the launcher.
  </div>

  <div class="grid">
    <div class="fcard">
      <h3>&#128190; docextract.exe</h3>
      <p>llamafile AI runtime — starts the local model server. No Ollama, no Python needed for the AI engine.</p>
      <span class="sz">305 MB &nbsp;&bull;&nbsp; Google Drive</span>
    </div>
    <div class="fcard">
      <h3>&#129302; model.gguf</h3>
      <p>Fine-tuned LLaMA 3.2 1B (Q8_0). Custom trained for Pakistani CNIC &amp; Driving License extraction.</p>
      <span class="sz">1.23 GB &nbsp;&bull;&nbsp; Google Drive</span>
    </div>
  </div>

  <div class="card">
    <div class="sec">How to Run</div>
    <div class="step"><div class="num" style="background:#7c3aed">1</div><div class="sb"><strong>Download from Google Drive</strong><span>Get <code>docextract.exe</code> and <code>model.gguf</code> from the shared link</span></div></div>
    <div class="step"><div class="num" style="background:#7c3aed">2</div><div class="sb"><strong>Download the launcher</strong><span>Click the button above &mdash; saves <code>AI_Document_System_LAUNCH.py</code></span></div></div>
    <div class="step"><div class="num" style="background:#7c3aed">3</div><div class="sb"><strong>Put all 3 files in one folder</strong><span><code>docextract.exe</code> &nbsp;+&nbsp; <code>model.gguf</code> &nbsp;+&nbsp; <code>AI_Document_System_LAUNCH.py</code></span></div></div>
    <div class="step"><div class="num" style="background:#16a34a">&#10003;</div><div class="sb"><strong>Double-click the launcher</strong><span>Right-click <code>AI_Document_System_LAUNCH.py</code> &rarr; <em>Open with Python</em><br>Browser opens at <code>http://127.0.0.1:5001</code> automatically</span></div></div>
  </div>

  <div class="card">
    <div class="sec">What the launcher does automatically</div>
    <div class="step"><div class="num" style="background:#0369a1">1</div><div class="sb"><strong>Extracts all source files</strong><span>Creates <code>AI_Document_System/</code> folder with all Python files + templates</span></div></div>
    <div class="step"><div class="num" style="background:#0369a1">2</div><div class="sb"><strong>Installs Python packages</strong><span>flask, opencv, easyocr, rapidfuzz, selenium &mdash; first run only, auto-skipped after</span></div></div>
    <div class="step"><div class="num" style="background:#0369a1">3</div><div class="sb"><strong>Starts llamafile AI engine</strong><span>Runs <code>docextract.exe -m model.gguf --server --port 8080</code> in background</span></div></div>
    <div class="step"><div class="num" style="background:#0369a1">4</div><div class="sb"><strong>Opens the app</strong><span>Starts Flask server and opens browser at <code>http://127.0.0.1:5001</code></span></div></div>
  </div>

  <div class="card" style="padding:0;overflow:hidden">
    <table class="tbl">
      <thead><tr><th>File (extracted automatically)</th><th>Purpose</th><th>Type</th></tr></thead>
      <tbody>
        <tr><td>main.py</td><td>App launcher — Flask + browser + Tkinter window</td><td><span class="tag t1">CORE</span></td></tr>
        <tr><td>form_filler_ui.py</td><td>Flask web server &amp; all routes</td><td><span class="tag t1">CORE</span></td></tr>
        <tr><td>agent_orchestrator.py</td><td>4-agent pipeline coordinator</td><td><span class="tag t2">AGENT</span></td></tr>
        <tr><td>agent_form_inspector.py</td><td>Selenium HTML/PDF form inspector</td><td><span class="tag t2">AGENT</span></td></tr>
        <tr><td>agent_field_mapper.py</td><td>LLM field mapper &rarr; port 8080</td><td><span class="tag t2">AGENT</span></td></tr>
        <tr><td>agent_form_filler.py</td><td>Selenium fills all field types</td><td><span class="tag t2">AGENT</span></td></tr>
        <tr><td>slm_client.py</td><td>llamafile client &rarr; port 8080</td><td><span class="tag t3">BRAIN</span></td></tr>
        <tr><td>brain_format_cnic.py</td><td>CNIC extraction pipeline</td><td><span class="tag t3">BRAIN</span></td></tr>
        <tr><td>brain_format_dl.py</td><td>Driving License pipeline</td><td><span class="tag t3">BRAIN</span></td></tr>
        <tr><td>profile_builder.py</td><td>Regex rules + confidence scoring</td><td><span class="tag t4">UTIL</span></td></tr>
        <tr><td>ocr_engine.py</td><td>RapidOCR + EasyOCR</td><td><span class="tag t4">UTIL</span></td></tr>
        <tr><td>form_mapper.py</td><td>HTML form filler</td><td><span class="tag t4">UTIL</span></td></tr>
        <tr><td>preprocess.py</td><td>Image preprocessing</td><td><span class="tag t4">UTIL</span></td></tr>
        <tr><td>templates/form_filler.html</td><td>Main web UI</td><td><span class="tag t5">TMPL</span></td></tr>
        <tr><td>templates/review.html</td><td>Human review screen</td><td><span class="tag t5">TMPL</span></td></tr>
      </tbody>
    </table>
  </div>

</div>
<script>
const F="__B64__";
function dl(){
  const b=atob(F),u=new Uint8Array(b.length);
  for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([u],{type:"text/x-python"}));
  a.download="AI_Document_System_LAUNCH.py";
  document.body.appendChild(a);a.click();
  document.body.removeChild(a);URL.revokeObjectURL(a.href);
}
</script>
</body>
</html>
"""

html = HTML.replace("__B64__", launcher_b64)
out  = os.path.join(ROOT, "AI_Document_System_Delivery.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"[2] HTML: AI_Document_System_Delivery.html  ({os.path.getsize(out)//1024} KB)")
print("\nDone!")
print("\nSend to client:")
print("  Google Drive  ->  docextract.exe  (305 MB)")
print("  Google Drive  ->  model.gguf      (1.23 GB)  [rename from your GGUF file]")
print("  Email/Chat    ->  AI_Document_System_Delivery.html  (HTML page)")
