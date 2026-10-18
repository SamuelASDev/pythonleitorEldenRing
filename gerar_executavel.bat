@echo off
setlocal
cd /d "%~dp0"
venv_eldenring\Scripts\python.exe -m pip install "pyinstaller>=6,<7"
if errorlevel 1 exit /b 1
venv_eldenring\Scripts\python.exe -m PyInstaller --noconfirm EntreTerras.spec
if errorlevel 1 exit /b 1
echo Executavel gerado em dist\EntreTerras\EntreTerras.exe
