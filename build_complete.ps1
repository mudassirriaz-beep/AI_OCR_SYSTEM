# ================================================================
#  AI Document System — Zero-Prerequisite Auto Build Script
#  PowerShell 5.1+  (built into every Windows 10/11 machine)
#
#  What this downloads automatically:
#    - Python 3.11  (if not already installed)
#    - Inno Setup 6 (if not already installed)
#    - All pip packages
#    - Ollama portable exe
#    - docextract:v11 AI model
#    - EasyOCR English models
#    - RapidOCR (via pip)
#
#  User just double-clicks  build_complete.bat  — nothing else needed.
# ================================================================

$ErrorActionPreference = "Continue"
try {
    $ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
    if (-not $ROOT -or $ROOT -eq "") { $ROOT = (Get-Location).Path }
    Set-Location $ROOT
    Write-Host "  Working directory: $ROOT" -ForegroundColor Gray
} catch {
    $ROOT = (Get-Location).Path
    Write-Host "  Working directory: $ROOT" -ForegroundColor Gray
}

# ── Colours ───────────────────────────────────────────────────────────────────
function Info  ($m) { Write-Host "  $m" -ForegroundColor Cyan }
function OK    ($m) { Write-Host "  OK  $m" -ForegroundColor Green }
function Step  ($m) { Write-Host "`n$m" -ForegroundColor Yellow }
function Err   ($m) { Write-Host "`n  ERROR: $m" -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }

function Download ($url, $dest, $label) {
    Info "Downloading $label ..."
    $parent = Split-Path $dest
    if ($parent -and !(Test-Path $parent)) { New-Item -ItemType Directory $parent -Force | Out-Null }
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($url, $dest)
    } catch {
        Err "Failed to download $label : $_"
    }
    OK "$label  ($('{0:N0}' -f ((Get-Item $dest).Length / 1MB)) MB)"
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  AI Document System — One-Click Complete Build" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Everything is downloaded automatically." -ForegroundColor White
Write-Host "  No manual installs required." -ForegroundColor White
Write-Host ""

# ── Step 1: Python ────────────────────────────────────────────────────────────
Step "[1/6] Python"

$PYTHON = $null
foreach ($cmd in @("python","py","python3")) {
    try {
        $v = & $cmd --version 2>&1
        if ($v -match "Python 3\.(1[01]\d*|[89])") { $PYTHON = $cmd; break }
    } catch {}
}

if (-not $PYTHON) {
    Info "Python 3.10+ not found — downloading installer..."
    $pyInstaller = "$env:TEMP\python_installer.exe"
    Download "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" `
             $pyInstaller "Python 3.11.9"

    Info "Installing Python silently (current user, no admin needed)..."
    $args = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0"
    Start-Process $pyInstaller -ArgumentList $args -Wait -NoNewWindow

    # Refresh PATH in this session
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH","User") + ";" +
                [Environment]::GetEnvironmentVariable("PATH","Machine")

    foreach ($cmd in @("python","py")) {
        try { $v = & $cmd --version 2>&1; if ($v -match "Python 3") { $PYTHON = $cmd; break } } catch {}
    }
    if (-not $PYTHON) { Err "Python installation succeeded but python.exe not found in PATH. Restart this script." }
}

$pyVer = & $PYTHON --version 2>&1
OK "Using: $pyVer  ($PYTHON)"

# ── Step 2: pip packages ──────────────────────────────────────────────────────
Step "[2/6] Python packages"
Info "Installing all required packages..."

$packages = @(
    "pyinstaller",
    "selenium",
    "rapidfuzz",
    "rapidocr-onnxruntime",
    "onnxruntime",
    "easyocr",
    "pillow",
    "numpy<2",
    "opencv-python",
    "pymupdf",
    "flask",
    "werkzeug",
    "beautifulsoup4",
    "requests",
    "urllib3"
)

foreach ($pkg in $packages) {
    Info "Installing $pkg ..."
    $result = & $PYTHON -m pip install --upgrade $pkg 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    $pkg - OK" -ForegroundColor Green
    } else {
        Write-Host "    $pkg - FAILED" -ForegroundColor Red
        Write-Host $result
        Err "Failed to install $pkg. Check internet connection and try again."
    }
}
OK "All packages installed"

# ── Step 3: Bundle Ollama + model + EasyOCR ───────────────────────────────────
Step "[3/6] AI models (Ollama + docextract:v11 + EasyOCR)"
Info "Running bundle_models.py ..."
& $PYTHON "$ROOT\bundle_models.py"
if ($LASTEXITCODE -ne 0) { Err "bundle_models.py failed. See output above." }

# ── Step 4: PyInstaller ───────────────────────────────────────────────────────
Step "[4/6] Building app EXE (PyInstaller)"
Info "This takes 5-15 minutes..."
& $PYTHON -m PyInstaller "$ROOT\AIDocumentSystem_Complete.spec" --clean --noconfirm 2>&1 |
    ForEach-Object { Write-Host "    $_" }

if ($LASTEXITCODE -ne 0) { Err "PyInstaller failed." }
$appExe = "$ROOT\dist\AIDocumentSystem\AIDocumentSystem.exe"
if (!(Test-Path $appExe)) { Err "Expected EXE not found: $appExe" }
OK "PyInstaller complete"

# ── Step 5: Inno Setup ────────────────────────────────────────────────────────
Step "[5/6] Inno Setup"

$ISCC = $null
foreach ($p in @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)) { if (Test-Path $p) { $ISCC = $p; break } }

if (-not $ISCC) {
    Info "Inno Setup not found — downloading and installing silently..."
    $innoUrl  = "https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe"
    $innoExe  = "$env:TEMP\innosetup_installer.exe"
    Download $innoUrl $innoExe "Inno Setup 6.3.3"

    Info "Installing Inno Setup (silent, current user)..."
    Start-Process $innoExe -ArgumentList "/VERYSILENT /NORESTART /CURRENTUSER" -Wait -NoNewWindow

    foreach ($p in @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )) { if (Test-Path $p) { $ISCC = $p; break } }

    if (-not $ISCC) { Err "Inno Setup installed but ISCC.exe not found. Try rerunning this script." }
}
OK "Inno Setup: $ISCC"

# ── Step 6: Create final installer ───────────────────────────────────────────
Step "[6/6] Creating final installer"
Info "Running Inno Setup compiler..."
& $ISCC "$ROOT\installer_complete.iss" 2>&1 | ForEach-Object { Write-Host "    $_" }
if ($LASTEXITCODE -ne 0) { Err "Inno Setup compilation failed." }

# ── Done ─────────────────────────────────────────────────────────────────────
$outExe = Get-ChildItem "$ROOT\dist\AIDocumentSystem_v*_Setup.exe" |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
if ($outExe) {
    $sizeMB = [math]::Round($outExe.Length / 1MB, 0)
    Write-Host "  Installer : $($outExe.FullName)" -ForegroundColor White
    Write-Host "  Size      : $sizeMB MB" -ForegroundColor White
}
Write-Host ""
Write-Host "  Contents of installer:" -ForegroundColor White
Write-Host "    - Full AI Document System application" -ForegroundColor Gray
Write-Host "    - Ollama AI server (starts automatically)" -ForegroundColor Gray
Write-Host "    - docextract:v11 language model (100% offline)" -ForegroundColor Gray
Write-Host "    - RapidOCR + EasyOCR models" -ForegroundColor Gray
Write-Host "    - Edge WebDriver for web form filling" -ForegroundColor Gray
Write-Host ""

# ── Auto-launch the installer ─────────────────────────────────────────────────
if ($outExe -and (Test-Path $outExe.FullName)) {
    Write-Host "  Launching installer now..." -ForegroundColor Yellow
    Write-Host ""
    Start-Process $outExe.FullName
    Write-Host "  Installer is running. Follow the on-screen steps to install." -ForegroundColor Green
    Write-Host "  After installation the app will open automatically." -ForegroundColor Green
} else {
    Write-Host "  WARNING: Installer file not found — run build_complete.bat again." -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to close this window"
