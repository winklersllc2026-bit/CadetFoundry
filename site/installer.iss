; Cadet Foundry — Windows installer, compiled by site/build.py with Inno Setup 6 or 7 (ISCC.exe).
; One step: Python is inside (python\, added by build.py), Cadet Foundry starts with pythonw.exe so there is no console
; window, and there's no setup script. Optional extras (offline AI, voice) install from inside Cadet Foundry (Me tab).
; Per-user (no admin): %LOCALAPPDATA%\Programs\Cadet Foundry. Instructor and Cadet data lives in %USERPROFILE%\.cadetfoundry
; and is never touched by installing, updating or uninstalling. @NAMES@ are filled in by build.py.

#define AppName "Cadet Foundry"
#define AppVer  "@VERSION@"

[Setup]
AppId={{CCA61B30-FC01-4C21-82E5-13E09D1E9C40}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=The Cadet Foundry Project
AppPublisherURL=https://cadetfoundry.org
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
Type: filesandordirs; Name: "{app}\cadetfoundry"
Type: filesandordirs; Name: "{app}\web"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\tests"
Type: filesandordirs; Name: "{app}\python"
; From before the rename (0.2.5 and older): the old code folder and start files, and the old shortcuts -- the new
; "Cadet Foundry" ones replace them. Same program ID and folder; the data folder moves when the app first starts.
Type: filesandordirs; Name: "{app}\vanguard"
Type: files; Name: "{app}\start-vanguard.bat"
Type: files; Name: "{app}\start-vanguard.sh"
Type: files; Name: "{app}\install-vanguard.bat"
Type: files; Name: "{app}\install-vanguard.sh"
Type: files; Name: "{autoprograms}\Vanguard.lnk"
Type: files; Name: "{autoprograms}\Vanguard Classroom.lnk"
Type: files; Name: "{autodesktop}\Vanguard.lnk"
; The classroom opens from the app now (Home -> Open class to phones), so the separate Classroom shortcut and start files go.
Type: files; Name: "{autoprograms}\{#AppName} Classroom.lnk"
Type: files; Name: "{app}\start-classroom.bat"
Type: files; Name: "{app}\start-classroom.sh"

[Files]
Source: "@STAGE@\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Add-ons downloaded later (voice model, voice package) live in the program folder too.
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\web\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; Description: "Start Cadet Foundry"; Flags: postinstall nowait skipifsilent

[Code]
// A running copy (pythonw.exe run.py) writes its process id in its data folder; close it before files are replaced or
// removed. Copies from before the rename (0.2.5 and older) wrote it in the old folder.
procedure StopPid(const PidFile: String);
var
  Pid: AnsiString;
  Code: Integer;
begin
  if LoadStringFromFile(ExpandConstant(PidFile), Pid) and (Trim(Pid) <> '') then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /FI "IMAGENAME eq pythonw.exe" /PID ' + Trim(Pid), '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

procedure StopRunningCopies();
begin
  StopPid('{%USERPROFILE}\.cadetfoundry\cadetfoundry.pid');
  StopPid('{%USERPROFILE}\.vanguard\vanguard.pid');
end;

// Vanguard 0.1.0-0.1.3 (this app's name before 0.2.5) were installed under an older program ID (shared by mistake with
// another product). Remove such an old copy first -- only when that entry's name is exactly "Vanguard" -- so its uninstaller can never later delete
// this installation's folder.
procedure RemoveOldestInstall();
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
  StopRunningCopies();
  RemoveOldestInstall();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopRunningCopies();
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('Cadet Foundry was removed. Profiles, logbooks and letters are kept in ' +
           ExpandConstant('{%USERPROFILE}') + '\.cadetfoundry - delete that folder too if you want them gone.',
           mbInformation, MB_OK);
end;
