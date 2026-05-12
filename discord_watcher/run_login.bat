@echo off
REM First-run bootstrap. Opens visible Chromium so you can log in.
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"
python watcher.py login
pause
endlocal
