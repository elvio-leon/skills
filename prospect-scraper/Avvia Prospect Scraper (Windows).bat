@echo off
rem Avvio di Prospect Scraper con doppio clic (Windows)
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
%PY% launcher.py
if errorlevel 1 pause
exit /b
:nopython
echo Python 3.11 o superiore non trovato.
echo Installalo da https://www.python.org/downloads/ spuntando "Add python.exe to PATH",
echo poi fai di nuovo doppio clic su questo file.
start "" https://www.python.org/downloads/
pause
