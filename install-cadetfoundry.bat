@echo off
rem One-click setup for Cadet Foundry on Windows 10/11. Needs internet once.
rem Installs Python (if missing), then the faith library, the official library, offline voice,
rem the offline AI and a desktop shortcut. Safe to run again.
cd /d "%~dp0"
set "PY="
set "CHECK=import sys; sys.exit(sys.version_info < (3, 10))"
rem "python" may be the Microsoft Store placeholder, so test that it really runs (3.10+), not just that it exists.
py -3 -c "%CHECK%" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "%CHECK%" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python 3.10+ isn't installed. Installing Python 3.12 with winget ...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo Couldn't install Python automatically. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
%PY% tools\setup.py %*
echo.
pause
