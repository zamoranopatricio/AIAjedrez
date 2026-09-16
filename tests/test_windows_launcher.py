from pathlib import Path


def _launcher_text() -> str:
    return Path("ejecutar_windows.bat").read_text(encoding="utf-8")


def test_launcher_explains_a_game_startup_failure_before_waiting():
    launcher = _launcher_text()

    assert "[ERROR] AI Ajedrez no pudo iniciarse" in launcher
    assert "Codigo de salida: !APP_EXIT!" in launcher
    assert launcher.index("[ERROR] AI Ajedrez no pudo iniciarse") < launcher.rindex("pause")


def test_launcher_keeps_successful_and_failed_startup_exit_codes():
    launcher = _launcher_text()

    assert 'set "APP_EXIT=!errorlevel!"' in launcher
    assert 'exit /b !APP_EXIT!' in launcher
