@echo off
setlocal EnableExtensions EnableDelayedExpansion
title AI Ajedrez - Windows
cd /d "%~dp0"

echo ===================================================
echo           Iniciando AI Ajedrez para Windows
echo ===================================================
echo.

set "BOOTSTRAP_PY="

rem Pygame distributes Windows wheels for the supported Python releases below.
rem Prefer 3.13 (installed by the project setup), then 3.12, rather than a
rem newer interpreter which would make pip attempt an unsupported source build.
py -3.13 --version >nul 2>&1
if !errorlevel! equ 0 set "BOOTSTRAP_PY=py -3.13"

if not defined BOOTSTRAP_PY (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set BOOTSTRAP_PY="%LocalAppData%\Programs\Python\Python313\python.exe"
)

if not defined BOOTSTRAP_PY (
    py -3.12 --version >nul 2>&1
    if !errorlevel! equ 0 set "BOOTSTRAP_PY=py -3.12"
)

if not defined BOOTSTRAP_PY (
    py -3 -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 10), (3, 11), (3, 12), (3, 13)) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "BOOTSTRAP_PY=py -3"
)

if not defined BOOTSTRAP_PY (
    python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 10), (3, 11), (3, 12), (3, 13)) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "BOOTSTRAP_PY=python"
)

if not defined BOOTSTRAP_PY (
    echo [ERROR] No se encontro una version compatible de Python (3.10 a 3.13).
    echo Instala Python 3.13 desde https://www.python.org/downloads/
    echo Durante la instalacion, marca "Add Python to PATH".
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 10), (3, 11), (3, 12), (3, 13)) else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo El entorno .venv usa una version incompatible de Python. Recreandolo...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno local .venv...
    %BOOTSTRAP_PY% -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

set "PYTHON_CMD=.venv\Scripts\python.exe"
echo Instalando o verificando dependencias...
%PYTHON_CMD% -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] No se pudieron instalar las dependencias de Python.
    pause
    exit /b 1
)

if exist "bin\stockfish.exe" goto stockfish_ready
where stockfish.exe >nul 2>&1
if !errorlevel! equ 0 goto stockfish_ready

echo.
echo [AVISO] Stockfish no esta instalado. El juego se abrira igualmente.
echo         Selecciona "Humano vs Humano" en el menu para jugar sin motor.
echo         Para habilitar la IA, coloca stockfish.exe dentro de bin\.
echo.
goto launch_game

:stockfish_ready
echo Stockfish detectado: IA y analisis disponibles.

:launch_game
echo.
echo Iniciando el juego...
%PYTHON_CMD% main.py
set "APP_EXIT=!errorlevel!"

if not "!APP_EXIT!"=="0" (
    echo.
    echo [ERROR] AI Ajedrez no pudo iniciarse.
    echo Codigo de salida: !APP_EXIT!
    echo Revisa el detalle mostrado arriba. Esta ventana permanecera abierta.
)

pause
exit /b !APP_EXIT!
