@echo off
rem Double-click to start class: Cadets join from phones on the same Wi-Fi (a Join screen with a QR code opens).
rem Needs Python 3.10+ (python.org).
cd /d "%~dp0"
where py >nul 2>nul && (py -3 run.py --lan %* & goto :eof)
where python >nul 2>nul && (python run.py --lan %* & goto :eof)
echo Python isn't installed. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run this again.
pause
