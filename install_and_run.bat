@echo off
title MacroEverything - Installation
echo ============================================
echo   MacroEverything - Installation automatique
echo ============================================
echo.

:: Verifier si Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python n'est pas installe.
    echo [*] Telechargement de Python 3.12...
    echo.
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    echo [*] Installation de Python (suivez les instructions)...
    echo     IMPORTANT: Cochez "Add Python to PATH" !
    start /wait %TEMP%\python_installer.exe /quiet InstallAllUsers=0 PrependPath=1
    echo [*] Python installe. Relancez ce script.
    pause
    exit
)

echo [OK] Python detecte.
echo.
echo [*] Installation des dependances...
python -m pip install pillow --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [!] Erreur pip. Tentative avec py...
    py -m pip install pillow --quiet
)

echo [OK] Dependances installees.
echo.
echo [*] Lancement de MacroEverything...
python "%~dp0macro_everything.py"
if %errorlevel% neq 0 (
    py "%~dp0macro_everything.py"
)
pause
