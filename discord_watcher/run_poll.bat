@echo off
REM ---------------------------------------------------------------------------
REM RoboVerse Discord watcher — what Task Scheduler invokes every 10 min.
REM ---------------------------------------------------------------------------
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"
python watcher.py poll
endlocal
