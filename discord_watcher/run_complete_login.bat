@echo off
REM Finishes the login bootstrap when run_login.bat couldn't auto-detect
REM the server URL. Pass the URL you saw in Chromium's address bar.
REM
REM Example:
REM   run_complete_login.bat https://discord.com/channels/1493037912751734878/1493037913322033237
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"

if "%~1"=="" (
    echo Usage: run_complete_login.bat ^<channel_url^>
    echo Example: run_complete_login.bat https://discord.com/channels/1493037912751734878/1493037913322033237
    pause
    exit /b 1
)

python complete_login.py "%~1"
pause
endlocal
