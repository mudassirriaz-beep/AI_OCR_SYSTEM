; ============================================================
;  AI Document System - Inno Setup Installer Script
;  Packages the PyInstaller output (no Python required)
;  Build: Inno Setup 6 - https://jrsoftware.org/isinfo.php
; ============================================================

#define AppName      "AI Document System"
#define AppVersion   "1.0"
#define AppPublisher "IAK NGO"
#define AppExe       "AIDocumentSystem.exe"
#define AppDir       "dist\AIDocumentSystem"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=AIDocumentSystem_Setup_v{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Create a &desktop shortcut";    GroupDescription: "Shortcuts:"
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Shortcuts:"

[Files]
; Bundle entire PyInstaller output folder
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Desktop
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
  WorkingDir: "{app}"; Tasks: desktopicon

; Start Menu
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#AppName}";  Filename: "{uninstallexe}";                       Tasks: startmenuicon

[Run]
Filename: "{app}\{#AppExe}"; \
  Description: "Launch {#AppName} now"; \
  Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'This will install AI Document System on your computer.' + #13#10 + #13#10 +
    'NOTE: This app uses Ollama (local AI) to extract data from documents.' + #13#10 +
    'After installation, make sure Ollama is running:' + #13#10 +
    '  1. Download Ollama from https://ollama.com' + #13#10 +
    '  2. Run: ollama pull llama3' + #13#10 +
    '  3. Keep Ollama running while using the app.' + #13#10 + #13#10 +
    'No Python installation is required.';
end;
