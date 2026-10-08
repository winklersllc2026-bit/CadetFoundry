@echo off
rem Double-click to start Cursiv Recruit on Windows. Needs Python 3.10+ (python.org).
cd /d "%~dp0"
where py >nul 2>nul && (py -3 run.py %* & goto :eof)
where python >nul 2>nul && (python run.py %* & goto :eof)
echo Python isn't installed. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run this again.
pause
