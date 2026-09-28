@echo off
chcp 65001 >nul
setlocal
echo ==============================================
echo   YouTube Kit per DaVinci Resolve - Installer
echo ==============================================
echo.
echo Chiudi DaVinci Resolve prima di continuare.
pause

set "SRC=%~dp0Templates\Edit"
set "DST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit"

echo.
echo [1/2] Copio titoli, transizioni, effetti e generatori in:
echo       %DST%
xcopy "%SRC%" "%DST%" /E /I /Y >nul
if errorlevel 1 (
  echo ERRORE durante la copia dei template.
) else (
  echo       OK
)

set "LUTDST=%ProgramData%\Blackmagic Design\DaVinci Resolve\Support\LUT\YouTube Kit"
echo.
echo [2/2] Copio le LUT colore in:
echo       %LUTDST%
xcopy "%~dp0LUT" "%LUTDST%" /E /I /Y >nul 2>nul
if errorlevel 1 (
  echo       Non ho i permessi per questa cartella.
  echo       Copia a mano la cartella LUT: in Resolve vai su
  echo       Impostazioni progetto ^> Color Management ^> "Open LUT Folder".
) else (
  echo       OK
)

echo.
echo Fatto! Riapri DaVinci Resolve: trovi tutto nella Effects Library
echo (Titles, Video Transitions, Effects, Generators) cercando "YTK".
echo Gli effetti sonori sono nella cartella SFX: importali nel Media Pool.
pause
