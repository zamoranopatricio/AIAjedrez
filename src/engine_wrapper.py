"""
src/engine_wrapper.py
Envuelve Stockfish con un hilo secundario para no bloquear la GUI.
Usa python-chess.engine (protocolo UCI).
"""
import logging
import queue
import threading

import chess
import chess.engine

log = logging.getLogger(__name__)


class EngineWrapper:
    """
    Interfaz no bloqueante con Stockfish.

    Uso:
        engine = EngineWrapper("/usr/games/stockfish")
        engine.start()
        engine.set_skill_level(10)
        engine.request_analysis(board)
        # … más tarde en el loop principal …
        move  = engine.best_move
        score = engine.score          # chess.engine.PovScore relativo a blancas
        engine.shutdown()
    """

    def __init__(self, stockfish_path: str):
        self._path = stockfish_path
        self._engine: chess.engine.SimpleEngine | None = None
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._running = False
        self._available = False

        # Resultados compartidos (protegidos por _lock)
        self._best_move: chess.Move | None = None
        self._score: chess.engine.Score | None = None
        self._is_analysing = False
        self._analysis_time = 0.15

    # ── Ciclo de vida ──────────────────────────────────────────────────────

    def start(self) -> bool:
        """Inicia el proceso de Stockfish. Devuelve True si tuvo éxito."""
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self._path)
            self._available = True
            self._running = True
            self._thread = threading.Thread(
                target=self._worker, daemon=True, name="StockfishWorker"
            )
            self._thread.start()
            log.info("Stockfish iniciado (%s)", self._path)
            return True
        except FileNotFoundError:
            log.error(
                "Stockfish no encontrado en '%s'. "
                "Instálalo con: sudo apt install stockfish",
                self._path,
            )
            return False
        except Exception as exc:
            log.error("Error al iniciar Stockfish: %s", exc)
            return False

    def shutdown(self):
        """Detiene el hilo y cierra Stockfish ordenadamente."""
        self._running = False
        try:
            self._queue.put_nowait(None)  # sentinel para desbloquear el hilo
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3)
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
        log.info("Stockfish detenido.")

    # ── Configuración ──────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def set_skill_level(self, level: int):
        """Nivel 0 (más débil) a 20 (máximo)."""
        if self._engine and self._available:
            try:
                self._engine.configure({"Skill Level": max(0, min(20, level))})
            except Exception as exc:
                log.warning("No se pudo configurar Skill Level: %s", exc)

    def set_analysis_time(self, seconds: float):
        self._analysis_time = max(0.05, seconds)

    # ── Análisis ───────────────────────────────────────────────────────────

    def request_analysis(self, board: chess.Board):
        """
        Encola una nueva posición para analizar.
        Si hay un análisis pendiente anterior, lo descarta.
        """
        if not self._available:
            return
        # Vaciar la cola (descartar petición antigua)
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(board.copy())
        except queue.Full:
            pass

    def clear(self):
        """Borra el último best_move y score (p. ej. al iniciar nueva partida)."""
        with self._lock:
            self._best_move = None
            self._score = None

    # ── Resultados (hilo-seguros) ──────────────────────────────────────────

    @property
    def best_move(self) -> chess.Move | None:
        with self._lock:
            return self._best_move

    @property
    def score(self) -> chess.engine.Score | None:
        """Score relativo a las blancas (PovScore.white())."""
        with self._lock:
            return self._score

    @property
    def is_analysing(self) -> bool:
        return self._is_analysing

    # ── Hilo worker ────────────────────────────────────────────────────────

    def _worker(self):
        while self._running:
            try:
                board = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue

            if board is None:
                break  # sentinel de shutdown

            self._is_analysing = True
            try:
                result = self._engine.analyse(
                    board,
                    chess.engine.Limit(time=self._analysis_time),
                )
                pv: list = result.get("pv", [])
                with self._lock:
                    self._best_move = pv[0] if pv else None
                    self._score = result["score"].white()
            except Exception as exc:
                log.debug("Error en análisis UCI: %s", exc)
            finally:
                self._is_analysing = False
