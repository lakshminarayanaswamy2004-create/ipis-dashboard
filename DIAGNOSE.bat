@echo off
title IPIS Diagnostics
color 0E

echo.
echo  ============================================================
echo    IPIS DIAGNOSTICS - Run this if START_IPIS.bat fails
echo  ============================================================
echo.

echo  --- Python Check ---
where python
python --version
echo.

echo  --- pip Check ---
python -m pip --version
echo.

echo  --- Package Check ---
python -c "import flask; print('flask OK:', flask.__version__)"
python -c "import edge_tts; print('edge_tts OK')"
python -c "import pydub; print('pydub OK')"
python -c "import requests; print('requests OK')"
echo.

echo  --- File Check ---
cd /d "%~dp0"
if exist "backend\app.py" (echo backend\app.py OK) else (echo MISSING: backend\app.py)
if exist "backend\train_lookup.json" (echo train_lookup.json OK) else (echo MISSING: train_lookup.json)
if exist "static\index.html" (echo static\index.html OK) else (echo MISSING: static\index.html)
echo.

echo  --- Starting app (errors will show here) ---
python backend\app.py

echo.
pause
