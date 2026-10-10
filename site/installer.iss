; Vanguard — Windows installer, compiled by site/build.py with Inno Setup 6 or 7 (ISCC.exe).
; One step: Python is inside (python\, added by build.py), Vanguard starts with pythonw.exe so there is no console
; window, and there's no setup script. Optional extras (offline AI, voice) install from inside Vanguard (Me tab).
; Per-user (no admin): %LOCALAPPDATA%\Programs\Vanguard. Instructor and Cadet data lives in %USERPROFILE%\.vanguard
; and is never touched by installing, updating or uninstalling. @NAMES@ are filled in by build.py.

#define AppName "Vanguard"
#define AppVer  "@VERSION@"

[Setup]
AppId={{CCA61B30-FC01-4C21-82E5-13E09D1E9C40}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=Winklers LLC
AppPublisherURL=https://vanguard.winklers-llc.com
AppComments=Learning and leadership platform designed to support JROTC instructors and Cadets. Runs on the instructor's laptop.
VersionInfoVersion=@VIVERSION@
VersionInfoCompany=Winklers LLC
VersionInfoDescription=Vanguard setup
VersionInfoProductName={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=@OUTDIR@
OutputBaseFilename=@OUTNAME@
SetupIconFile=@ICON@
UninstallDisplayIcon={app}\web\icon.ico
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Program folders are replaced on update so files removed in a new version don't linger (data lives elsewhere).
Type: filesandordirs; Name: "{app}\vanguard"
Type: filesandordirs; Name: "{app}\web"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\tests"
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "@STAGE@\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Add-ons downloaded later (voice model, voice package) live in the program folder too.
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"
; The whole class: a window shows the address Cadets type on their own devices (same Wi-Fi). Close it to stop.
Name: "{autoprograms}\{#AppName} (classroom)"; Filename: "{app}\python\python.exe"; Parameters: """{app}\run.py"" --lan"; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; Description: "Start Vanguard"; Flags: postinstall nowait skipifsilent

[Code]
// A running Vanguard (pythonw.exe run.py) writes its process id here; close it before files are replaced or removed.
procedure StopVanguard();
var
  Pid: AnsiString;
  Code: Integer;
begin
  if LoadStringFromFile(ExpandConstant('{%USERPROFILE}\.vanguard\vanguard.pid'), Pid) and (Trim(Pid) <> '') then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /FI "IMAGENAME eq pythonw.exe" /PID ' + Trim(Pid), '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopVanguard();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopVanguard();
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('Vanguard was removed. Profiles, logbooks and letters are kept in ' +
           ExpandConstant('{%USERPROFILE}') + '\.vanguard - delete that folder too if you want them gone.',
           mbInformation, MB_OK);
end;
