@echo off

:: Appelle directement le python du venv (pas d'activate : il garde en dur
:: le chemin de creation, ce qui casse des que le dossier est deplace).
set "VPY=%~dp0venv\Scripts\python.exe"

:: 1. Cree le venv s'il manque ou s'il est inutilisable
"%VPY%" -c "import playwright, paramiko" >nul 2>&1
if errorlevel 1 (
    echo [INFO] venv absent ou incomplet. Recreation en cours...
    if exist "%~dp0venv" rmdir /s /q "%~dp0venv"
    python -m venv "%~dp0venv"
    "%VPY%" -m pip install --upgrade pip
    "%VPY%" -m pip install playwright paramiko
    "%VPY%" -m playwright install chromium
) else (
    echo [INFO] venv OK.
)

:: 2. Lance le script
echo [INFO] Lancement du pipeline...
"%VPY%" "%~dp0screenshot_pipeline.py"

pause
