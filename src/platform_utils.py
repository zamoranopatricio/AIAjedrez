"""
src/platform_utils.py
Detección de sistema operativo, resolución de rutas de binarios (Stockfish)
y localización de assets en modo desarrollo o ejecutable compilado (PyInstaller).
"""
import os
import sys
import shutil
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"


def get_base_dir() -> Path:
    """
    Devuelve el directorio raíz del proyecto.
    Soporta ejecución normal en Python y ejecutable compilado con PyInstaller (sys._MEIPASS).
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def find_stockfish_binary(base_dir: Path) -> str:
    """
    Busca inteligentemente el ejecutable de Stockfish según el sistema operativo.
    Devuelve la ruta al ejecutable encontrado o el nombre por defecto.
    """
    env_path = os.getenv("STOCKFISH_PATH", "")
    if env_path and Path(env_path).is_file():
        return env_path

    bin_dir = base_dir / "bin"

    if IS_WINDOWS:
        candidates = [
            shutil.which("stockfish.exe"),
            shutil.which("stockfish"),
            str(bin_dir / "stockfish.exe"),
            str(bin_dir / "stockfish-windows-x86-64-avx2.exe"),
            str(bin_dir / "stockfish-windows-x86-64.exe"),
            str(base_dir / "stockfish.exe"),
        ]
    else:
        candidates = [
            shutil.which("stockfish"),
            str(bin_dir / "stockfish"),
            str(base_dir / "stockfish"),
            "/usr/games/stockfish",
            "/usr/bin/stockfish",
            "/usr/local/bin/stockfish",
        ]

    for cand in candidates:
        if cand and Path(cand).is_file():
            return str(cand)

    return "stockfish.exe" if IS_WINDOWS else "stockfish"
