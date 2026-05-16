@echo off
title MacroEverything
cd /d "%~dp0"

:: Rafraichir le PATH pour trouver Python apres installation winget
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYSPATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%b"
set "PATH=%SYSPATH%;%USERPATH%"

python main.py 2>nul
if %errorlevel% neq 0 (
    py main.py 2>nul
)
if %errorlevel% neq 0 (
    echo Python not found. Run install_and_run.bat
    pause
)
