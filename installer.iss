; DynoAI Installer Script for Inno Setup
; Creates a professional Windows installer

#define MyAppName "DynoAI"
#define MyAppVersion "1.2.1"
#define MyAppPublisher "DynoAI"
#define MyAppURL "https://github.com/rob9206/DynoAI_3"
#define MyAppExeName "DynoAI.exe"

[Setup]
; Installer metadata
AppId={{05FFC011-AFBC-9D29-6337-4F57F5001CC4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=installer_output
OutputBaseFilename=DynoAI_Setup_{#MyAppVersion}
; SetupIconFile=assets\dynoai.ico  ; Uncomment if you have an icon
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Privileges (install for current user by default)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Include any additional files if needed
; Source: "config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to run app after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Create data directories on install
procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := ExpandConstant('{userappdata}\DynoAI');
    if not DirExists(DataDir) then
      CreateDir(DataDir);
    if not DirExists(DataDir + '\uploads') then
      CreateDir(DataDir + '\uploads');
    if not DirExists(DataDir + '\outputs') then
      CreateDir(DataDir + '\outputs');
    if not DirExists(DataDir + '\runs') then
      CreateDir(DataDir + '\runs');
  end;
end;
