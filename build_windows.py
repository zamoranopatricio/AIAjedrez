"""
build_windows.py
Script de automatización para generar la versión portable autónoma (.exe) para Windows mediante PyInstaller.
"""
import sys
import subprocess
from pathlib import Path

def main():
    print("=" * 60)
    print("       Compilando AI Ajedrez para Windows (PyInstaller)")
    print("=" * 60)

    base_dir = Path(__file__).resolve().parent
    main_py = base_dir / "main.py"
    
    # Comprobar PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller no está instalado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Comando PyInstaller
    # --noconsole: Sin ventana de terminal emergente
    # --onedir / --onefile: Generar ejecutable autónomo
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AIAjedrez",
        "--noconsole",
        "--onedir",
        "--clean",
        f"--add-data=assets{';' if sys.platform == 'win32' else ':'}assets",
        f"--add-data=bin{';' if sys.platform == 'win32' else ':'}bin",
        str(main_py)
    ]

    print(f"Ejecutando comando: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print(" [✓] COMPILACIÓN EXITOSA")
        print(" El ejecutable se encuentra en: dist/AIAjedrez/AIAjedrez.exe")
        print("=" * 60)
    else:
        print("\n [X] Ocurrió un error durante la compilación.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
