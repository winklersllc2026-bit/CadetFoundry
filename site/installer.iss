; Cadet Foundry — Windows installer, compiled by site/build.py with Inno Setup 6 or 7 (ISCC.exe).
; One step: Python is inside (python\, added by build.py), Cadet Foundry starts with pythonw.exe so there is no console
; window, and there's no setup script. Optional extras (offline AI, voice) install from inside Cadet Foundry (Me tab).
; Per-user (no admin): %LOCALAPPDATA%\Programs\Cadet Foundry. Instructor and Cadet data lives in %USERPROFILE%\.vanguard
; and is never touched by installing, updating or uninstalling. @NAMES@ are filled in by build.py.

#define AppName "Cadet Foundry"
#define AppVer  "@VERSION@"

[Setup]
AppId={{CCA61B30-FC01-4C21-82E5-13E09D1E9C40}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=The Cadet Foundry Project
AppPublisherURL=https://vanguard.winklers-llc.com
AppComments=Learning and leadership platform designed to support JROTC instructors and Cadets. Runs on the instructor's laptop.
VersionInfoVersion=@VIVERSION@
VersionInfoCompany=The Cadet Foundry Project
VersionInfoDescription=Cadet Foundry setup
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
; Shortcuts from before the rename (0.2.5): the new "Cadet Foundry" ones replace them. Same program ID, same folder, same data.
Type: files; Name: "{autoprograms}\Vanguard.lnk"
Type: files; Name: "{autoprograms}\Vanguard Classroom.lnk"
Type: files; Name: "{autodesktop}\Vanguard.lnk"

[Files]
Source: "@STAGE@\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Add-ons downloaded later (voice model, voice package) live in the program folder too.
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"
; The whole class: opens the Join screen (a QR code Cadets scan on the same Wi-Fi). End class there to stop.
Name: "{autoprograms}\{#AppName} Classroom"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"" --lan"; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; Description: "Start Cadet Foundry"; Flags: postinstall nowait skipifsilent

[Code]
// A running Cadet Foundry (pythonw.exe run.py) writes its process id here; close it before files are replaced or removed.
procedure StopVanguard();
var
  Pid: AnsiString;
  Code: Integer;
begin
  if LoadStringFromFile(ExpandConstant('{%USERPROFILE}\.vanguard\vanguard.pid'), Pid) and (Trim(Pid) <> '') then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /FI "IMAGENAME eq pythonw.exe" /PID ' + Trim(Pid), '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

// Vanguard 0.1.0-0.1.3 (this app's name before 0.2.5) were installed under an older program ID (shared by mistake with
// another product). Remove such an old copy first -- only when that entry's name is exactly "Vanguard" -- so its uninstaller can never later delete
// this installation's folder.
procedure RemoveOldVanguard();
var
  Key, Name, Cmd: String;
  Code: Integer;
begin
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0E2F3C-8C1D-4E57-9A3B-2D7F4C1E9A60}_is1';
  if RegQueryStringValue(HKCU, Key, 'DisplayName', Name) and (Name = 'Vanguard') and
     RegQueryStringValue(HKCU, Key, 'UninstallString', Cmd) then
    Exec(RemoveQuotes(Cmd), '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopVanguard();
  RemoveOldVanguard();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopVanguard();
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('Cadet Foundry was removed. Profiles, logbooks and letters are kept in ' +
           ExpandConstant('{%USERPROFILE}') + '\.vanguard - delete that folder too if you want them gone.',
           mbInformation, MB_OK);
end;
