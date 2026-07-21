@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python 3 and make sure "py" is available.
    pause
    exit /b 1
)

start "" /B py -3 -m http.server 8000 --directory "%~dp0site" >nul 2>&1
ping 127.0.0.1 -n 2 >nul
start "" http://127.0.0.1:8000/

start "" /min py -3 organizer.py --drives E F

echo Organizer started in the background.
echo The website is open in your browser.
pause
