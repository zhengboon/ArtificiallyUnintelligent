@echo off
REM Full-history scrape of all configured Discord channels.
REM Output: D:\hackerverse\info_YYYY-MM-DD_scrape\<channel>.md (one file per channel)
REM
REM Use this when Claude needs to cross-check the repo docs against the
REM source-of-truth Discord content. Slower than `poll` (it scrolls all
REM the way up through each channel), but gives complete coverage.
setlocal
set "PYDIR=C:\Users\zheng\AppData\Local\Programs\Python\Python312"
set "PATH=%PYDIR%;%PYDIR%\Scripts;C:\Users\zheng\AppData\Roaming\Python\Python312\Scripts;%PATH%"
cd /d "%~dp0"
python watcher.py scrape
pause
endlocal
