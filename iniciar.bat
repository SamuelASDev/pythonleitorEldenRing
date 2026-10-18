@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" if exist "dist\EntreTerras\EntreTerras.exe" (
    start "" "%~dp0dist\EntreTerras\EntreTerras.exe" --data-dir "%~dp0data"
    exit /b 0
)
if not exist "venv_eldenring\Scripts\python.exe" (
    python -m venv venv_eldenring
    if errorlevel 1 goto erro
)
venv_eldenring\Scripts\python.exe -c "import dxcam, cv2, numpy, atomics, pystray, PIL, psutil" >nul 2>&1
if errorlevel 1 (
    venv_eldenring\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto erro
)
if "%~1"=="" (
    start "" "%~dp0venv_eldenring\Scripts\pythonw.exe" "%~dp0elden_ring_tracker.py"
    exit /b 0
)
venv_eldenring\Scripts\python.exe elden_ring_tracker.py %*
if errorlevel 1 goto erro
exit /b 0
:erro
echo.
echo Nao foi possivel iniciar. Confira a mensagem de erro acima.
pause
exit /b 1
