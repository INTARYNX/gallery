@echo off

:: 1. Vérifie si le dossier venv existe dans le répertoire courant
if not exist "venv" (
    echo [INFO] Le venv n'existe pas. Creation en cours...
    python -m venv venv
    
    echo [INFO] Activation du venv et installation des paquets...
    call venv\Scripts\activate
    
    python -m pip install --upgrade pip
    pip install playwright paramiko
    playwright install chromium
) else (
    echo [INFO] venv detecte. Activation...
)

:: 2. Active le venv et lance le script
call venv\Scripts\activate
echo [INFO] Lancement du pipeline...
python screenshot_pipeline.py

pause