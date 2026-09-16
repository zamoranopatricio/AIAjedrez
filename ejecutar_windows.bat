@echo off
title AI Ajedrez - Windows
echo ===================================================
echo           Iniciando AI Ajedrez para Windows
echo ===================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3 no se encuentra en el PATH del sistema.
    echo Descargalo e instalalo desde https://www.python.org/
    pause
    exit /b 1
)

echo Verificando dependencias...
python -m pip install -r requirements.txt

echo.
echo Iniciando el juego...
python main.py

pause
