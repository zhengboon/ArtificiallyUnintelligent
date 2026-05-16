@echo off
REM Launches the local control panel for the Discord watcher.
REM Opens at http://localhost:5050/
REM
REM This stays running. Close the terminal window (or Ctrl+C) to stop.
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"
echo Starting control panel at http://localhost:5050/
echo (Ctrl+C in this window to stop.)
echo.
python server.py
endlocal
