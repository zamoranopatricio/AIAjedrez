"""
main.py — Punto de entrada de AIAjedrez.
Coordina el menú, el estado de la partida, la GUI y el motor Stockfish.
"""
import logging
import sys
import threading
import time

import pygame
import chess

import config as cfg
from src.asset_loader import download_pieces, load_piece_images
from src.board_gui import BoardGUI, pixel_to_square
from src.engine_wrapper import EngineWrapper
from src.game_state import GameMode, GameState
from src.menu import MenuScreen
from src.analysis_screen import AnalysisScreen, _BackToMenu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────────────────────
# Pantalla de carga
# ─────────────────────────────────────────────────────────────────────────────

def _show_loading(screen: pygame.Surface, message: str):
    screen.fill(cfg.C_BG)
    pygame.font.init()
    font = pygame.font.SysFont("monospace", 18)
    t = font.render(message, True, cfg.C_TEXT_DIM)
    screen.blit(t, t.get_rect(center=(cfg.WINDOW_WIDTH // 2, cfg.WINDOW_HEIGHT // 2)))
    pygame.display.flip()


# ─────────────────────────────────────────────────────────────────────────────
# Clase principal del juego
# ─────────────────────────────────────────────────────────────────────────────

class ChessApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        pygame.display.set_caption(cfg.TITLE)

        # Intentar poner icono (puede fallar si no hay piezas aún)
        try:
            icon = pygame.Surface((32, 32))
            icon.fill((40, 40, 70))
            font = pygame.font.SysFont("segoeuisymbol,symbola,unifont", 28)
            t = font.render("♟", True, (200, 200, 200))
            icon.blit(t, t.get_rect(center=(16, 16)))
            pygame.display.set_icon(icon)
        except Exception:
            pass

        self.clock = pygame.time.Clock()

        # Descargar piezas si faltan
        _show_loading(self.screen, "Verificando assets de piezas…")
        ok = download_pieces(cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE)
        if not ok:
            log.warning("Algunas piezas no se pudieron descargar. Se usará fallback Unicode.")

        # Cargar imágenes de piezas
        _show_loading(self.screen, "Cargando imágenes…")
        self.piece_images = load_piece_images(cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE)

        # Motor Stockfish
        self.engine = EngineWrapper(cfg.STOCKFISH_PATH)
        engine_ok   = self.engine.start()
        if not engine_ok:
            log.warning(
                "Stockfish no disponible. El análisis IA estará desactivado.\n"
                "Instala con: sudo apt install stockfish"
            )

        # Estado de juego (se inicializará en cada partida)
        self.state: GameState | None = None
        self.gui:   BoardGUI  | None = None

        # Variables de interacción
        self._dragging_piece: chess.Piece | None = None
        self._drag_from: int | None = None
        self._drag_pos  = (0, 0)

        # Control de solicitud de análisis
        self._analysis_requested_for: chess.Zobrist | None = None   # type: ignore
        self._last_fen = ""

        # Temporizador para movimiento de IA
        self._ai_move_pending = False
        self._ai_move_time    = 0.0
        self._AI_DELAY        = 0.3   # segundos de pausa antes de que la IA mueva

    # ── Loop de aplicación ─────────────────────────────────────────────────

    def run(self):
        while True:
            result = MenuScreen(self.screen).run()
            self._start_game(result)
            self._game_loop()

    # ── Inicio de partida ──────────────────────────────────────────────────

    def _start_game(self, result):
        from src.menu import MenuResult  # evitar import circular
        diff   = cfg.DIFFICULTY_LEVELS[result.difficulty_index]
        self.state = GameState(mode=result.mode, human_color=result.human_color)
        self.gui   = BoardGUI(
            screen=self.screen,
            piece_images=self.piece_images,
            flipped=(result.human_color == chess.BLACK and result.mode == GameMode.HUMAN_VS_AI),
        )
        self.engine.clear()
        if self.engine.is_available():
            self.engine.set_skill_level(diff["skill"])
            self.engine.set_analysis_time(diff["time"])

        self._dragging_piece = None
        self._drag_from      = None
        self._drag_pos       = (0, 0)
        self._ai_move_pending = False
        self._last_fen        = ""

        log.info(
            "Partida iniciada — Modo: %s | Dificultad: %s",
            result.mode.name, diff["name"]
        )

    # ── Loop de partida ────────────────────────────────────────────────────

    def _game_loop(self):
        running = True
        while running:
            dt = self.clock.tick(cfg.FPS) / 1000.0
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown(); return
                if event.type == pygame.KEYDOWN:
                    action = self._handle_key(event.key)
                    if action == "menu":
                        return
                    if action == "quit":
                        self._shutdown(); return
                    if action == "analysis":
                        self._open_analysis(); continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    ui_action = self._handle_ui_click(event.pos)
                    if ui_action == "menu":     return
                    if ui_action == "analysis": self._open_analysis(); continue
                    if ui_action:               continue  # otro botón manejado
                if not self.state.game_over and self.state.is_human_turn():
                    self._handle_mouse(event)

            # Solicitar análisis si cambió la posición
            self._maybe_request_analysis()

            # Mover IA si es su turno
            if not self.state.game_over and not self.state.is_human_turn():
                self._handle_ai_turn(dt)

            # Renderizar
            self.gui.draw(
                board=self.state.board,
                selected_square=self.state.selected_square,
                legal_targets=self.state.legal_targets,
                last_move=self.state.last_move,
                best_move=self.engine.best_move if self.engine.is_available() else None,
                score=self.engine.score if self.engine.is_available() else None,
                dragging_piece=self._dragging_piece,
                drag_pos=self._drag_pos,
                san_history=self.state.san_history,
                mode_label=self._mode_label(),
                engine_available=self.engine.is_available(),
                mouse_pos=mouse_pos,
            )

            if self.state.game_over:
                self.gui.draw_game_over(self.state.result_text, mouse_pos)

            pygame.display.flip()

    # ── Clics en botones de UI ─────────────────────────────────────────────

    def _handle_ui_click(self, pos) -> str | None:
        """
        Comprueba si el clic cayó sobre algún botón de la UI.
        Devuelve una cadena con la acción o None si no tocó ningún botón.
        """
        g = self.gui

        # ── Botones del panel lateral (siempre visibles) ───────────────────
        if g.flip_btn_rect.collidepoint(pos):
            g.flipped = not g.flipped
            self.state.deselect()
            return "flip"

        if g.btn_undo.collidepoint(pos):
            double = (self.state.mode == GameMode.HUMAN_VS_AI)
            if self.state.undo(double=double):
                self.engine.clear()
                self._ai_move_pending = False
                self._last_fen = ""
            return "undo"

        if g.btn_save.collidepoint(pos):
            self.state.save_pgn(cfg.SAVES_DIR)
            return "save"

        if g.btn_restart.collidepoint(pos):
            self.state.reset()
            self.engine.clear()
            self._ai_move_pending = False
            self._last_fen = ""
            return "restart"

        if g.btn_analysis.collidepoint(pos):
            return "analysis"

        if g.btn_menu.collidepoint(pos):
            return "menu"

        # ── Botones del overlay de fin de partida ──────────────────────────
        if self.state.game_over:
            if g.go_btn_restart.collidepoint(pos):
                self.state.reset()
                self.engine.clear()
                self._ai_move_pending = False
                self._last_fen = ""
                return "restart"
            if g.go_btn_analysis.collidepoint(pos):
                return "analysis"
            if g.go_btn_menu.collidepoint(pos):
                return "menu"

        return None

    # ── Eventos de ratón ───────────────────────────────────────────────────

    def _handle_mouse(self, event: pygame.event.Event):
        flipped = self.gui.flipped

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            sq = pixel_to_square(*event.pos, flipped)
            if sq is None:
                self.state.deselect(); return

            piece = self.state.board.piece_at(sq)
            if piece and piece.color == self.state.board.turn:
                # Iniciar selección + posible arrastre
                self.state.select(sq)
                self._dragging_piece = piece
                self._drag_from      = sq
                self._drag_pos       = event.pos
            else:
                # Intentar mover a esta casilla
                moved = self.state.try_move(sq)
                if moved:
                    self._on_move_made()

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging_piece:
                self._drag_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_piece and self._drag_from is not None:
                sq = pixel_to_square(*event.pos, flipped)
                if sq is not None and sq != self._drag_from:
                    moved = self.state.try_move_drag(self._drag_from, sq)
                    if moved:
                        self._on_move_made()
                    else:
                        # Soltar en casilla inválida: mantener selección
                        self.state.select(self._drag_from)
                self._dragging_piece = None
                self._drag_from      = None

    # ── Turno de la IA ─────────────────────────────────────────────────────

    def _handle_ai_turn(self, dt: float):
        if not self.engine.is_available():
            return

        if not self._ai_move_pending:
            # Iniciar espera (para que el análisis pueda correr al menos un poco)
            self._ai_move_pending = True
            self._ai_move_time    = 0.0
            self.engine.request_analysis(self.state.board)
            return

        self._ai_move_time += dt
        if self._ai_move_time < self._AI_DELAY:
            return

        move = self.engine.best_move
        if move is None:
            # El motor aún no tiene resultado; seguir esperando
            return

        self._ai_move_pending = False
        pushed = self.state.push_ai_move(move)
        if pushed:
            self._on_move_made()

    # ── Post-movimiento ────────────────────────────────────────────────────

    def _on_move_made(self):
        self._ai_move_pending = False
        self.engine.clear()
        self._last_fen = ""   # forzar nueva solicitud de análisis

    # ── Análisis continuo ──────────────────────────────────────────────────

    def _maybe_request_analysis(self):
        if not self.engine.is_available() or self.state.game_over:
            return
        fen = self.state.board.fen()
        if fen != self._last_fen and not self.engine.is_analysing:
            self._last_fen = fen
            self.engine.request_analysis(self.state.board)

    # ── Teclado ────────────────────────────────────────────────────────────

    def _handle_key(self, key) -> str | None:
        if key == pygame.K_ESCAPE or key == pygame.K_m:
            return "menu"
        if key == pygame.K_q:
            return "quit"
        if key == pygame.K_r:
            self.state.reset()
            self.engine.clear()
            self._ai_move_pending = False
            self._last_fen = ""
        if key == pygame.K_s:
            path = self.state.save_pgn(cfg.SAVES_DIR)
            log.info("PGN guardado: %s", path)
        if key == pygame.K_f:
            self.gui.flipped = not self.gui.flipped
            self.state.deselect()
        if key == pygame.K_z:
            # Deshacer: en H vs IA popé dos jugadas (IA + humano)
            double = (self.state.mode == GameMode.HUMAN_VS_AI)
            ok = self.state.undo(double=double)
            if ok:
                self.engine.clear()
                self._ai_move_pending = False
                self._last_fen = ""
                log.info("Jugada deshecha.")
        if key == pygame.K_a:
            return "analysis"
        return None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _mode_label(self) -> str:
        if self.state.mode == GameMode.HUMAN_VS_HUMAN:
            return "Humano vs Humano"
        color_str = "Blancas" if self.state.human_color == chess.WHITE else "Negras"
        return f"Humano ({color_str}) vs IA"

    def _open_analysis(self):
        """Abre la pantalla de análisis post-partida."""
        if not self.state.moves_played:
            log.info("No hay jugadas para analizar.")
            return
        # Pausar motor mientras dura el análisis
        try:
            screen = AnalysisScreen(
                screen=self.screen,
                engine_path=cfg.STOCKFISH_PATH,
                snapshots=list(self.state._snapshots),
                moves_played=list(self.state.moves_played),
                san_history=list(self.state.san_history),
                result_text=self.state.result_text or "Partida en curso",
                piece_images=self.piece_images,
            )
            screen.run()
        except _BackToMenu:
            pass
        except Exception as exc:
            log.error("Error en pantalla de análisis: %s", exc)

    def _shutdown(self):
        log.info("Cerrando aplicación…")
        self.engine.shutdown()
        pygame.quit()
        sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ChessApp().run()
