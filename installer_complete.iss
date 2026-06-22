; ================================================================
;  AI Document System — Complete Self-Contained Installer
;  Bundles:
;    • Python app  (PyInstaller output)
;    • Ollama server binary
;    • docextract:v11 model (GGUF blobs + manifest)
;    • EasyOCR English models
;    • Edge WebDriver
;  User needs ZERO additional downloads.
;
;  Build requirements (on the developer machine):
;    1. run: python bundle_models.py
;    2. run: pyinstaller AIDocumentSystem_Complete.spec --clean
;    3. run: iscc installer_complete.iss
; ================================================================

#define AppName      "AI Document System"
#define AppVersion   "2.0"
#define AppPublisher "IAK NGO"
#define AppExe       "AIDocumentSystem.exe"
#define AppDir       "dist\AIDocumentSystem"
#define BundleDir    "bundle"

[Setup]
AppId={{B3C4D5E6-F7A8-9012-BCDE-F12345678901}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppComments=Fully offline AI document form-filling system
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=AIDocumentSystem_v{#AppVersion}_Setup
; LZMA ultra gives best compression (~40% reduction)
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
ExtraDiskSpaceRequired=524288000
; Auto-install: skip all wizard pages, install silently, then launch app
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Create a &desktop shortcut";    GroupDescription: "Shortcuts:"
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Shortcuts:"

; ── Files ─────────────────────────────────────────────────────────────────────

[Files]
; 1. Python application (PyInstaller output)
Source: "{#AppDir}\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; 2. Ollama server binary
Source: "{#BundleDir}\ollama\ollama.exe"; \
  DestDir: "{app}\ollama"; \
  Flags: ignoreversion

; 3. Ollama model — manifests (small JSON metadata)
Source: "{#BundleDir}\ollama_models\manifests\*"; \
  DestDir: "{app}\ollama_models\manifests"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; 4. Ollama model — GGUF blobs (the actual model weights, ~800 MB)
Source: "{#BundleDir}\ollama_models\blobs\*"; \
  DestDir: "{app}\ollama_models\blobs"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; 5. EasyOCR English models
Source: "{#BundleDir}\models\easyocr\*"; \
  DestDir: "{app}\models\easyocr"; \
  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; ── Shortcuts ─────────────────────────────────────────────────────────────────

[Icons]
; Desktop shortcut
Name: "{autodesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExe}"; \
  WorkingDir: "{app}"; \
  Tasks: desktopicon

; Start Menu
Name: "{group}\{#AppName}"; \
  Filename: "{app}\{#AppExe}"; \
  WorkingDir: "{app}"; \
  Tasks: startmenuicon

Name: "{group}\Uninstall {#AppName}"; \
  Filename: "{uninstallexe}"; \
  Tasks: startmenuicon

; ── Post-install launch ────────────────────────────────────────────────────────

[Run]
Filename: "{app}\{#AppExe}"; \
  Description: "Launch {#AppName} now"; \
  Flags: nowait postinstall skipifsilent

; ── Wizard customization ──────────────────────────────────────────────────────

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'This will install ' + ExpandConstant('{#AppName}') + ' on your computer.' + #13#10 + #13#10 +

    'WHAT IS INCLUDED:' + #13#10 +
    '  • AI Document System application' + #13#10 +
    '  • Ollama AI engine (local, fully offline)' + #13#10 +
    '  • docextract:v11 language model (~800 MB)' + #13#10 +
    '  • RapidOCR + EasyOCR text recognition models' + #13#10 +
    '  • Edge WebDriver for web form automation' + #13#10 + #13#10 +

    'REQUIREMENTS:' + #13#10 +
    '  • Windows 10 / 11  (64-bit)' + #13#10 +
    '  • Microsoft Edge browser (pre-installed on Windows 10/11)' + #13#10 +
    '  • 4 GB RAM minimum (8 GB recommended)' + #13#10 + #13#10 +

    'No Python, no Ollama, no additional downloads required.' + #13#10 +
    'Everything runs completely offline after installation.';
end;

function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if Version.Major < 10 then
  begin
    MsgBox('Windows 10 or later is required.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Create writable working directories next to the EXE
    ForceDirectories(ExpandConstant('{app}\uploads'));
    ForceDirectories(ExpandConstant('{app}\filled_forms'));
    ForceDirectories(ExpandConstant('{app}\pending_review'));
  end;
end;
