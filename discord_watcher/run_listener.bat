@echo off
REM Background notification listener. Set this to run at user logon.
REM pythonw = no console window. start /B = background.
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"
start "" /B pythonw notif_listener.py
endlocal
