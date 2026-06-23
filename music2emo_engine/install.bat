@echo off
REM ============================================================
REM  music2emo engine setup
REM  Creates an isolated venv (Python 3.12), installs torch CPU +
REM  music2emo inference deps, and clones the music2emo repo.
REM  Run once:  music2emo_engine\install.bat
REM ============================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto :nopy

echo [1/4] Creating venv (.venv) with Python 3.12...
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if not exist ".venv\Scripts\python.exe" goto :nopy

set "PIP=.venv\Scripts\pip.exe"

echo [2/4] Installing torch 2.3.1 CPU build...
"%PIP%" install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :torchretry
goto :torchdone

:torchretry
echo [WARN] CPU index failed. Retrying from PyPI...
"%PIP%" install torch==2.3.1 torchaudio==2.3.1
if errorlevel 1 goto :depfail

:torchdone
echo [3/4] Installing music2emo inference deps...
"%PIP%" install -r requirements-engine.txt
if errorlevel 1 goto :depfail

echo [4/4] Cloning music2emo repo...
if exist "music2emo_repo\music2emo.py" goto :done
git clone --depth 1 https://github.com/AMAAI-Lab/Music2Emotion music2emo_repo
if errorlevel 1 goto :gitfail

:done
echo.
echo Setup complete.
echo The MERT model downloads automatically on first run.
echo If HuggingFace is blocked in your region, set:
echo   set HF_ENDPOINT=https://hf-mirror.com
echo before launching the app.
endlocal
exit /b 0

:nopy
echo [ERROR] Python 3.12 not found via 'py' launcher.
echo Install Python 3.12 and ensure the py launcher is on PATH.
endlocal
exit /b 1

:depfail
echo [ERROR] dependency install failed. See messages above.
endlocal
exit /b 1

:gitfail
echo [ERROR] git clone failed. Check network or git installation.
endlocal
exit /b 1
