@echo off
title IPIS Train Announcement Dashboard
color 0A

:: Keep window open even if something fails
echo.
echo  ============================================================
echo    IPIS - Train Announcement Dashboard
echo  ============================================================
echo.

:: ── Step 1: Find Python ──────────────────────────────────────────────────────
echo  [1/4] Checking Python...

where python >nul 2>&1
if errorlevel 1 (
    goto :no_python
)

python --version
echo  [OK] Python found.
echo.

:: ── Step 2: Install packages ─────────────────────────────────────────────────
echo  [2/4] Installing required packages (only needed first time)...
echo        This may take 1-2 minutes on first run...
echo.

python -m pip install flask edge-tts pydub requests --quiet --no-warn-script-location
if errorlevel 1 (
    echo.
    echo  [!] pip install had issues. Trying with --user flag...
    python -m pip install flask edge-tts pydub requests --quiet --user --no-warn-script-location
)

echo  [OK] Packages ready.
echo.

:: ── Step 3: Open browser ────────────────────────────────────────────────────
echo  [3/4] Opening browser in 2 seconds...
start "" timeout /t 2 /nobreak >nul 2>&1
start "" "http://127.0.0.1:5000"

:: ── Step 4: Start server ─────────────────────────────────────────────────────
echo  [4/4] Starting server...
echo.
echo  ============================================================
echo    App is running at:  http://127.0.0.1:5000
echo    DO NOT close this window while using the app!
echo    Close this window to STOP the app.
echo  ============================================================
echo.

cd /d "%~dp0"
python backend\app.py
if errorlevel 1 (
    echo.
    echo  [ERROR] Server stopped with an error.
    echo  See error message above.
    echo.
    pause
    exit /b 1
)

echo.
echo  Server stopped. Press any key to close.
pause
exit /b 0


:: ── Python not found ─────────────────────────────────────────────────────────
:no_python
echo.
echo  ============================================================
echo   [ERROR] Python is NOT installed on this computer.
echo  ============================================================
echo.
echo   Please install Python:
echo.
echo   1. Open your browser and go to:
echo         https://www.python.org/downloads/
echo.
echo   2. Download the latest version (Python 3.x)
echo.
echo   3. Run the installer
echo      IMPORTANT: Tick the checkbox that says
echo                 "Add Python to PATH"
echo.
echo   4. After installing, run START_IPIS.bat again
echo.
echo  ============================================================
pause
exit /b 1
