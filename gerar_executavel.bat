@echo off
setlocal
cd /d "%~dp0"
if not exist "venv_eldenring\Scripts\python.exe" (
    python -m venv venv_eldenring
    if errorlevel 1 exit /b 1
)
venv_eldenring\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
venv_eldenring\Scripts\python.exe -m PyInstaller --noconfirm EntreTerras.spec
if errorlevel 1 exit /b 1
echo Executavel gerado em dist\EntreTerras\EntreTerras.exe
