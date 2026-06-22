"""
AI Document System — EXE launcher.

When running as a PyInstaller bundle:
  1. Locate bundled ollama.exe and model files
  2. Set OLLAMA_MODELS env-var so Ollama finds the bundled model
  3. Start ollama serve as a subprocess
  4. Wait until Ollama is responsive (polls /api/tags)
  5. Start Flask (form_filler_ui.py) in a background thread
  6. Wait until Flask is responsive
  7. Open the browser
  8. Show a Tkinter control window (keep-alive + stop button)

When running as plain .py (development):
  Steps 1-4 are skipped — developer must have Ollama running manually.
"""

import os
import sys
import socket
import subprocess
import threading
import time
import webbrowser
import tkinter as tk

# ── Path resolution ────────────────────────────────────────────────────────────

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BUNDLE_DIR = sys._MEIPASS
    INSTALL_DIR = os.path.dirname(os.path.abspath(sys.executable))
    # All user writes go to %APPDATA%\AI Document System (always writable)
    WORK_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "AI Document System")
else:
    BUNDLE_DIR  = os.path.dirname(os.path.abspath(__file__))
    INSTALL_DIR = BUNDLE_DIR
    WORK_DIR    = BUNDLE_DIR

os.makedirs(WORK_DIR, exist_ok=True)
os.chdir(WORK_DIR)
sys.path.insert(0, BUNDLE_DIR)

# ── Constants ──────────────────────────────────────────────────────────────────

PORT         = 5001
OLLAMA_PORT  = 11434
APP_URL      = f"http://127.0.0.1:{PORT}"
OLLAMA_URL   = f"http://127.0.0.1:{OLLAMA_PORT}"
OLLAMA_MODEL = "docextract:v11"          # model bundled in the installer

# Read-only assets live in the install dir; user data goes to WORK_DIR
_OLLAMA_EXE    = os.path.join(INSTALL_DIR, "ollama", "ollama.exe")
_OLLAMA_MODELS = os.path.join(INSTALL_DIR, "ollama_models")
_DRIVER_PATH   = os.path.join(INSTALL_DIR, "msedgedriver.exe")

# ── Ollama management ──────────────────────────────────────────────────────────

_ollama_proc = None

def _ollama_ready(timeout: int = 60) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def start_ollama():
    """Start the bundled Ollama server if we're running as a frozen EXE."""
    global _ollama_proc

    if not FROZEN:
        return   # developer must start Ollama manually

    if not os.path.isfile(_OLLAMA_EXE):
        _show_error("ollama.exe not found inside the installation directory.\n"
                    "Please reinstall the application.")
        sys.exit(1)

    # Tell Ollama where to find the bundled model
    env = os.environ.copy()
    env["OLLAMA_MODELS"]    = _OLLAMA_MODELS
    env["OLLAMA_HOME"]      = _OLLAMA_MODELS
    # Use the bundled model name for all LLM calls
    env["AI_DOC_MODEL"]     = OLLAMA_MODEL

    _ollama_proc = subprocess.Popen(
        [_OLLAMA_EXE, "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    # Also propagate to this process so slm_client picks it up
    os.environ["AI_DOC_MODEL"]  = OLLAMA_MODEL
    os.environ["OLLAMA_MODELS"] = _OLLAMA_MODELS
    os.environ["OLLAMA_HOME"]   = _OLLAMA_MODELS


def stop_ollama():
    global _ollama_proc
    if _ollama_proc and _ollama_proc.poll() is None:
        _ollama_proc.terminate()
        try:
            _ollama_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _ollama_proc.kill()


# ── Flask ──────────────────────────────────────────────────────────────────────

def _run_flask():
    from form_filler_ui import app
    if FROZEN:
        app.template_folder = os.path.join(BUNDLE_DIR, "templates")
    app.run(host="127.0.0.1", port=PORT, debug=False,
            use_reloader=False, threaded=True)


def _wait_port(port: int, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.3)
    return False


# ── Error dialog (before Tkinter main-loop) ────────────────────────────────────

def _show_error(msg: str):
    import tkinter.messagebox as mb
    root = tk.Tk(); root.withdraw()
    mb.showerror("AI Document System — Error", msg)
    root.destroy()


# ── Startup sequence ───────────────────────────────────────────────────────────

status_var: tk.StringVar = None    # updated from threads


def _set_status(msg: str):
    if status_var:
        try:
            status_var.set(msg)
        except Exception:
            pass
    print(f"[STATUS] {msg}")


def _startup():
    """Run in a background thread so the Tkinter loop can start immediately."""
    _set_status("Starting Ollama AI engine…")
    start_ollama()

    if FROZEN:
        _set_status("Waiting for Ollama to load model…")
        if not _ollama_ready(timeout=120):
            _show_error("Ollama did not start within 2 minutes.\n"
                        "The AI engine may not work correctly.")
        else:
            _set_status("Ollama ready  ✓")

    _set_status("Starting web server…")
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    _wait_port(PORT, timeout=30)

    _set_status(f"Running at  {APP_URL}")
    webbrowser.open(APP_URL)


# ── Tkinter UI ─────────────────────────────────────────────────────────────────

BG      = "#1e1e2e"
ACCENT  = "#7c3aed"
FG      = "#e2e8f0"
FG_DIM  = "#94a3b8"

root = tk.Tk()
root.title("AI Document System")
root.geometry("360x200")
root.resizable(False, False)
root.configure(bg=BG)

# Header
hdr = tk.Frame(root, bg=ACCENT, height=46)
hdr.pack(fill="x")
hdr.pack_propagate(False)
tk.Label(hdr, text="AI Document System",
         font=("Segoe UI", 12, "bold"), bg=ACCENT, fg="white"
         ).pack(padx=16, pady=10, side="left")

# Status area
status_var = tk.StringVar(value="Initialising…")
tk.Label(root, textvariable=status_var,
         font=("Segoe UI", 9), bg=BG, fg=FG_DIM, wraplength=320
         ).pack(pady=(16, 2), padx=16)

tk.Label(root, text="Keep this window open while using the app.",
         font=("Segoe UI", 8), bg=BG, fg="#475569"
         ).pack()

# Ollama model label (shown only in bundled EXE)
if FROZEN:
    tk.Label(root, text=f"AI model: {OLLAMA_MODEL}  •  Port {PORT}",
             font=("Segoe UI", 8), bg=BG, fg="#334155"
             ).pack(pady=(4, 0))

# Buttons
btn_frame = tk.Frame(root, bg=BG)
btn_frame.pack(pady=16)


def _on_open():
    webbrowser.open(APP_URL)


def _on_stop():
    stop_ollama()
    root.destroy()


tk.Button(btn_frame, text="Open Browser",
          command=_on_open,
          bg=ACCENT, fg="white", relief="flat",
          font=("Segoe UI", 9, "bold"),
          padx=16, pady=8, cursor="hand2",
          activebackground="#6d28d9", activeforeground="white"
          ).pack(side="left", padx=6)

tk.Button(btn_frame, text="Stop App",
          command=_on_stop,
          bg="#374151", fg=FG, relief="flat",
          font=("Segoe UI", 9),
          padx=16, pady=8, cursor="hand2",
          activebackground="#4b5563", activeforeground=FG
          ).pack(side="left", padx=6)

root.protocol("WM_DELETE_WINDOW", _on_stop)

# Start the startup sequence in background
threading.Thread(target=_startup, daemon=True).start()

root.mainloop()
