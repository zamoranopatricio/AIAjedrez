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
from src.live_tracking_screen import LiveTrackingScreen
from src.training_screen import TrainingScreen
from src.game_analysis import EvaluationHistory, MoveReview, review_move, summarize_game
from src.history_navigation import HistoryNavigator
from src.opening_book import detect_opening
from src.windows_clickthrough import install_windows_clickthrough

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
        self._clickthrough_handler = install_windows_clickthrough()

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
        self.visual_theme = cfg.VISUAL_THEME_CHESS_COM
        ok = download_pieces(
            cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE, theme=self.visual_theme,
        )
        if not ok:
            log.warning("Algunas piezas no se pudieron descargar. Se usará fallback Unicode.")

        # Cargar imágenes de piezas
        _show_loading(self.screen, "Cargando imágenes…")
        self.piece_images = load_piece_images(
            cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE, theme=self.visual_theme,
        )

        # Motor Stockfish
        self.engine = EngineWrapper(cfg.STOCKFISH_PATH)
        engine_ok   = self.engine.start()
        if not engine_ok:
            log.warning(
                "Stockfish no disponible. Humano vs Humano sigue disponible; "
                "el modo contra IA y el análisis requieren el motor. "
                "Consulta README.md para instalarlo en tu sistema."
            )

        # Estado de juego (se inicializará en cada partida)
        self.state: GameState | None = None
        self.gui:   BoardGUI  | None = None
        self.show_ai_indicator: bool = True
        self.show_blue_alternative: bool = True
        self.test_mode_enabled: bool = False
        self.evaluation_history = EvaluationHistory()
        self.move_reviews: list[MoveReview] = []
        self.history_navigator: HistoryNavigator | None = None
        self._review_pending: dict | None = None

        # Variables de interacción
        self._dragging_piece: chess.Piece | None = None
        self._drag_from: int | None = None
        self._drag_pos  = (0, 0)
        self._test_move_from: int | None = None

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
            result = MenuScreen(
                self.screen,
                engine_available=self.engine.is_available(),
                visual_theme=self.visual_theme,
            ).run()
            self._apply_visual_theme(result.visual_theme)
            if result.tracking_mode:
                self._run_tracking(result)
                continue
            if result.training_mode:
                self._run_training()
                continue
            self._start_game(result)
            self._game_loop()

    def _run_tracking(self, result) -> None:
        """Abre el registrador local; no inicia motor ni habilita mover el tablero."""
        LiveTrackingScreen(
            self.screen,
            self.piece_images,
            result.initial_fen,
            white_bottom=not bool(result.initial_flipped),
            visual_theme=getattr(self, "visual_theme", result.visual_theme),
        ).run()

    def _run_training(self) -> None:
        """Reto de motor aislado: no modifica ninguna partida local."""
        if self.engine.is_available():
            TrainingScreen(
                self.screen, self.piece_images, self.engine,
                visual_theme=self.visual_theme,
            ).run()

    # ── Inicio de partida ──────────────────────────────────────────────────

    def _start_game(self, result):
        from src.menu import MenuResult  # evitar import circular
        diff   = cfg.DIFFICULTY_LEVELS[result.difficulty_index]
        self.state = GameState(
            mode=result.mode,
            human_color=result.human_color,
            initial_fen=result.initial_fen,
        )
        self.show_ai_indicator = result.show_ai_indicator
        self.test_mode_enabled = False
        self.gui   = BoardGUI(
            screen=self.screen,
            piece_images=self.piece_images,
            flipped=(result.initial_flipped if result.initial_flipped is not None else
                     result.human_color == chess.BLACK and result.mode == GameMode.HUMAN_VS_AI),
            visual_theme=getattr(self, "visual_theme", result.visual_theme),
        )
        self.engine.clear()
        if self.engine.is_available():
            self.engine.set_skill_level(diff["skill"])
            self.engine.set_analysis_time(diff["time"])

        self._dragging_piece = None
        self._drag_from      = None
        self._drag_pos       = (0, 0)
        self._test_move_from = None
        self._ai_move_pending = False
        self._last_fen        = ""
        self.evaluation_history = EvaluationHistory()
        self.move_reviews = []
        self.history_navigator = HistoryNavigator.from_game_state(self.state)
        self._review_pending = None

        log.info(
            "Partida iniciada — Modo: %s | Dificultad: %s | Indicador IA: %s",
            result.mode.name, diff["name"], "ON" if self.show_ai_indicator else "OFF"
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
                if (not self.state.game_over and self.state.is_human_turn()
                        and self._history_is_live()):
                    self._handle_mouse(event)

            # Solicitar análisis si cambió la posición
            self._maybe_request_analysis()

            # Mover IA si es su turno
            if (not self.state.game_over and not self.state.is_human_turn()
                    and self._history_is_live()):
                self._handle_ai_turn(dt)

            # Renderizar
            display_board = self._display_board()
            browsing_history = not self._history_is_live()
            self.gui.draw(
                board=display_board,
                selected_square=None if browsing_history else self.state.selected_square,
                legal_targets=[] if browsing_history else self.state.legal_targets,
                last_move=(display_board.peek() if browsing_history and display_board.move_stack
                           else self.state.last_move),
                best_move=self.engine.best_move if self.engine.is_available() else None,
                alternative_move=self._blue_suggestion_move(),
                score=self.engine.score if self.engine.is_available() else None,
                dragging_piece=self._dragging_piece,
                drag_pos=self._drag_pos,
                san_history=self.state.san_history,
                mode_label=self._mode_label(),
                engine_available=self.engine.is_available(),
                show_ai_indicator=self.show_ai_indicator,
                show_blue_arrow_toggle=(self.state.mode == GameMode.HUMAN_VS_HUMAN),
                blue_arrow_enabled=self.show_blue_alternative,
                show_test_mode_toggle=(self.state.mode == GameMode.HUMAN_VS_HUMAN),
                test_mode_enabled=self.test_mode_enabled,
                mouse_pos=mouse_pos,
                evaluation_samples=[(sample.ply, sample.score_cp)
                                    for sample in self.evaluation_history.samples],
                opening_label=self._opening_label(),
                history_index=self.history_navigator.active_index if self.history_navigator else None,
                history_position_count=self.history_navigator.position_count if self.history_navigator else None,
            )

            if self.state.game_over:
                self.gui.draw_game_over(self.state.result_text, mouse_pos,
                                        summary=summarize_game(self.move_reviews))

            pygame.display.flip()

    # ── Clics en botones de UI ─────────────────────────────────────────────

    def _handle_ui_click(self, pos) -> str | None:
        """
        Comprueba si el clic cayó sobre algún botón de la UI.
        Devuelve una cadena con la acción o None si no tocó ningún botón.
        """
        g = self.gui

        # Navegar sólo cambia la vista: el GameState activo no se toca.
        if self.history_navigator:
            if g.btn_history_previous.collidepoint(pos):
                self.history_navigator.previous(); self.state.deselect(); return "history"
            if g.btn_history_next.collidepoint(pos):
                self.history_navigator.next(); self.state.deselect(); return "history"
            if g.btn_history_live.collidepoint(pos):
                self.history_navigator.latest(); self.state.deselect(); return "history"
            for move_index, rect in g.history_move_rects.items():
                if rect.collidepoint(pos):
                    self.history_navigator.go_to(move_index)
                    self.state.deselect()
                    return "history"

        # ── Botones del panel lateral (siempre visibles) ───────────────────
        if g.flip_btn_rect.collidepoint(pos):
            g.flipped = not g.flipped
            self.state.deselect()
            return "flip"

        if g.btn_toggle_indicator.collidepoint(pos):
            self.show_ai_indicator = not self.show_ai_indicator
            return "toggle_indicator"

        if (self.state.mode == GameMode.HUMAN_VS_HUMAN
                and g.btn_toggle_blue_arrow.collidepoint(pos)):
            self.show_blue_alternative = not self.show_blue_alternative
            return "toggle_blue_arrow"

        if (self.state.mode == GameMode.HUMAN_VS_HUMAN
                and g.btn_toggle_test_mode.collidepoint(pos)):
            self.test_mode_enabled = not self.test_mode_enabled
            self._test_move_from = None
            self.state.deselect()
            return "toggle_test_mode"

        if g.btn_undo.collidepoint(pos):
            double = (self.state.mode == GameMode.HUMAN_VS_AI)
            if self.state.undo(double=double):
                self.engine.clear()
                self._ai_move_pending = False
                self._last_fen = ""
                self._clear_analysis_history()
                self._refresh_history_navigation()
            return "undo"

        if g.btn_save.collidepoint(pos):
            self.state.save_pgn(cfg.SAVES_DIR)
            return "save"

        if g.btn_restart.collidepoint(pos):
            self.state.reset()
            self.engine.clear()
            self._ai_move_pending = False
            self._last_fen = ""
            self._clear_analysis_history()
            self._refresh_history_navigation()
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
                self._clear_analysis_history()
                self._refresh_history_navigation()
                return "restart"
            if g.go_btn_analysis.collidepoint(pos):
                return "analysis"
            if g.go_btn_menu.collidepoint(pos):
                return "menu"

        return None

    # ── Eventos de ratón ───────────────────────────────────────────────────

    def _handle_mouse(self, event: pygame.event.Event):
        flipped = self.gui.flipped

        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
                and self.state.mode == GameMode.HUMAN_VS_HUMAN
                and self.test_mode_enabled):
            sq = pixel_to_square(*event.pos, flipped)
            if sq is None:
                self._test_move_from = None
                self.state.deselect()
                return
            if getattr(self, "_test_move_from", None) is None:
                if self.state.board.piece_at(sq) is not None:
                    # Reutiliza el highlight de selección, sin destinos legales:
                    # en modo prueba cualquier casilla será un destino válido.
                    self.state.deselect()
                    self._test_move_from = sq
                    self.state.selected_square = sq
                    self.state.legal_targets = []
                return
            if self.state.relocate_piece_for_test(self._test_move_from, sq):
                self._test_move_from = None
                self._on_test_position_edited()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._test_move_from = None
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
        # Guardar la evaluación disponible antes de limpiar el motor. Cuando
        # llegue el análisis de la nueva posición se clasificará la jugada.
        played = self.state.last_move
        previous = self.state._snapshots[-1] if self.state._snapshots else None
        if played is not None and previous is not None:
            best = self.engine.best_move if self.engine.is_available() else None
            best_san = previous.san(best) if best in previous.legal_moves else None
            self._review_pending = {
                "ply": len(self.state.san_history), "san": self.state.san_history[-1],
                "mover": previous.turn, "played": played, "best": best,
                "best_san": best_san, "before": self._score_to_cp(self.engine.score),
            }
        self._ai_move_pending = False
        self.engine.clear()
        self._last_fen = ""   # forzar nueva solicitud de análisis
        self._refresh_history_navigation()

    def _on_test_position_edited(self) -> None:
        """Invalida datos derivados después de cambiar el tablero manualmente."""
        self._ai_move_pending = False
        self.engine.clear()
        self._last_fen = ""
        self._clear_analysis_history()
        self._refresh_history_navigation()

    # ── Análisis continuo ──────────────────────────────────────────────────

    def _maybe_request_analysis(self):
        if not self.engine.is_available() or self.state.game_over:
            return
        fen = self.state.board.fen()
        if fen != self._last_fen and not self.engine.is_analysing:
            self._last_fen = fen
            self.engine.request_analysis(self.state.board)
            return
        if self._review_pending and not self.engine.is_analysing and self.engine.score is not None:
            pending = self._review_pending
            review = review_move(
                pending["ply"], pending["san"], pending["before"],
                self._score_to_cp(self.engine.score), pending["mover"],
                played_move=pending["played"], best_move=pending["best"],
                best_san=pending["best_san"],
            )
            self.move_reviews.append(review)
            self.evaluation_history.record(pending["san"], self._score_to_cp(self.engine.score))
            self._review_pending = None

    def _blue_suggestion_move(self) -> chess.Move | None:
        """Alternativa de Stockfish visible solo en la partida local entre humanos."""
        if (
            self.state.mode != GameMode.HUMAN_VS_HUMAN
            or not self.show_ai_indicator
            or not self.show_blue_alternative
            or not self.engine.is_available()
        ):
            return None
        return self.engine.alternative_move

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
            self._clear_analysis_history()
            self._refresh_history_navigation()
        if key == pygame.K_s:
            path = self.state.save_pgn(cfg.SAVES_DIR)
            log.info("PGN guardado: %s", path)
        if key == pygame.K_f:
            self.gui.flipped = not self.gui.flipped
            self.state.deselect()
        if key == pygame.K_i:
            self.show_ai_indicator = not self.show_ai_indicator
            log.info("Indicador IA: %s", "ON" if self.show_ai_indicator else "OFF")
        if key == pygame.K_z:
            # Deshacer: en H vs IA popé dos jugadas (IA + humano)
            double = (self.state.mode == GameMode.HUMAN_VS_AI)
            ok = self.state.undo(double=double)
            if ok:
                self.engine.clear()
                self._ai_move_pending = False
                self._last_fen = ""
                self._clear_analysis_history()
                self._refresh_history_navigation()
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

    def _refresh_history_navigation(self) -> None:
        self.history_navigator = HistoryNavigator.from_game_state(self.state)

    def _clear_analysis_history(self) -> None:
        """Evita que una curva o resumen incluya jugadas que se deshicieron."""
        self.evaluation_history = EvaluationHistory()
        self.move_reviews = []
        self._review_pending = None

    def _history_is_live(self) -> bool:
        return self.history_navigator is None or (
            self.history_navigator.active_index == self.history_navigator.position_count - 1
        )

    def _display_board(self) -> chess.Board:
        if self.history_navigator and not self._history_is_live():
            return self.history_navigator.view_board
        return self.state.board

    def _opening_label(self) -> str | None:
        opening = detect_opening(self.state.moves_played)
        return f"{opening.name} ({opening.eco})" if opening else None

    @staticmethod
    def _score_to_cp(score) -> int:
        if score is None:
            return 0
        try:
            if score.is_mate():
                return 100000 if score.mate() > 0 else -100000
            return score.score() or 0
        except Exception:
            return 0

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
                visual_theme=getattr(self, "visual_theme", cfg.VISUAL_THEME_CHESS_COM),
            )
            screen.run()
        except _BackToMenu:
            pass
        except Exception as exc:
            log.error("Error en pantalla de análisis: %s", exc)

    def _apply_visual_theme(self, theme: str) -> None:
        """Carga las piezas del tema elegido antes de abrir cualquier modo."""
        selected = cfg.normalize_visual_theme(theme)
        if selected == self.visual_theme:
            return
        _show_loading(self.screen, f"Cargando estilo {selected}…")
        if not download_pieces(cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE, theme=selected):
            log.warning("No se pudo completar el set de piezas %s.", selected)
        self.piece_images = load_piece_images(
            cfg.ASSETS_DIR, size=cfg.SQUARE_SIZE, theme=selected,
        )
        self.visual_theme = selected

    def _shutdown(self):
        log.info("Cerrando aplicación…")
        if self._clickthrough_handler:
            self._clickthrough_handler.uninstall()
        self.engine.shutdown()
        pygame.quit()
        sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ChessApp().run()
