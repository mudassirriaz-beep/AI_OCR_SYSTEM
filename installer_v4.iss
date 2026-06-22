; ============================================================
;  AI Document System v4.0 - Donut Edition
;  No Python, no Ollama, no GPU required on client machine.
;  Build: Inno Setup 6
; ============================================================

#ifndef DistPath
  #define DistPath "D:\AIDocumentSystem_Build\dist"
#endif

#define AppName      "AI Document System"
#define AppVersion   "4.0"
#define AppPublisher "IAK NGO"
#define AppExe       "AIDocumentSystem.exe"
#define AppDir       DistPath + "\AIDocumentSystem"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=D:\AIDocumentSystem_Build
OutputBaseFilename=AIDocumentSystem_v4.0_Setup
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
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#AppName}";  Filename: "{uninstallexe}";                       Tasks: startmenuicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'This will install AI Document System on your computer.' + #13#10 + #13#10 +
    'Powered by DONUT AI — extracts data from CNIC and Driving License images.' + #13#10 + #13#10 +
    'No Python, no internet, no GPU required.' + #13#10 +
    'Everything is included in this installer.';
end;
