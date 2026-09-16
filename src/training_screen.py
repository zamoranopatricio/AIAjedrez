"""Pantalla local de entrenamiento: una posición y una respuesta del jugador."""
from __future__ import annotations

import pygame
import chess

from src.board_gui import BoardGUI, pixel_to_square
from src.training import TrainingChallenge
from src import font_manager as fm
import config as cfg


_PUZZLE_FENS = (
    "6k1/5ppp/8/7Q/8/8/6PP/6K1 w - - 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r1bqkbnr/pppp1ppp/2n5/8/2B1P3/8/PPPP1PPP/RNBQK1NR b KQkq - 2 2",
)


class TrainingScreen:
    """Reto aislado del juego: Stockfish sólo valida la respuesta local."""

    def __init__(
        self,
        screen: pygame.Surface,
        piece_images: dict,
        engine,
        puzzles: tuple[str, ...] = _PUZZLE_FENS,
    ) -> None:
        if not puzzles:
            raise ValueError("El entrenamiento necesita al menos una posición.")
        self.screen = screen
        self.engine = engine
        self.gui = BoardGUI(screen, piece_images)
        self._puzzles = puzzles
        self._puzzle_index = 0
        self.board = chess.Board(self._puzzles[self._puzzle_index])
        self.selected: int | None = None
        self.challenge: TrainingChallenge | None = None
        self.solution_move: chess.Move | None = None
        self.solved = False
        self._requested_fen: str | None = None
        self.message = "Stockfish está preparando el reto…"
        self.clock = pygame.time.Clock()
        self.btn_retry = pygame.Rect(0, 0, 0, 0)
        self.btn_next = pygame.Rect(0, 0, 0, 0)
        self.btn_menu = pygame.Rect(0, 0, 0, 0)

    def run(self) -> None:
        self._request_current_challenge()
        running = True
        while running:
            self.clock.tick(cfg.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m):
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._handle_panel_click(event.pos):
                        if self.btn_menu.collidepoint(event.pos):
                            return
                        continue
                    self._handle_click(event.pos)

            self._make_challenge_when_ready()
            targets = self._legal_targets()
            self.gui.draw(
                self.board, self.selected, targets, self.solution_move, None, None, None, (0, 0), [],
                "Entrenamiento local", True, show_ai_indicator=False,
            )
            self._draw_message()
            pygame.display.flip()

    def _make_challenge_when_ready(self) -> None:
        if self.challenge is not None or self.solved or self.engine.is_analysing:
            return

        result_fen = getattr(self.engine, "analysis_fen", None)
        if result_fen is not None and result_fen != self._requested_fen:
            return

        candidates = [
            move for move in (
                self.engine.best_move,
                getattr(self.engine, "alternative_move", None),
            )
            if move is not None and move in self.board.legal_moves
        ]
        if candidates:
            self.challenge = TrainingChallenge.from_engine(self.board, candidates)
            self.message = "Tu turno: encuentra una de las mejores jugadas."

    def _request_current_challenge(self) -> None:
        """Pide una respuesta nueva y descarta de forma segura datos anteriores."""
        self.challenge = None
        self.solution_move = None
        self.solved = False
        self.selected = None
        self._requested_fen = self.board.fen()
        self.message = "Stockfish está preparando el reto…"
        self.engine.clear()
        self.engine.request_analysis(self.board)

    def next_challenge(self) -> None:
        """Carga otro reto sólo después de dejar visible la solución actual."""
        self._puzzle_index = (self._puzzle_index + 1) % len(self._puzzles)
        self.board = chess.Board(self._puzzles[self._puzzle_index])
        self._request_current_challenge()

    def retry_challenge(self) -> None:
        """Mantiene la misma posición y permite intentar de nuevo."""
        if self.challenge is not None and not self.solved:
            self.selected = None
            self.message = "Intenta otra vez: encuentra una de las mejores jugadas."

    def _legal_targets(self) -> list[int]:
        if self.selected is None:
            return []
        return [move.to_square for move in self.board.legal_moves if move.from_square == self.selected]

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.challenge is None:
            return
        square = pixel_to_square(*pos, self.gui.flipped)
        if square is None:
            self.selected = None
            return
        piece = self.board.piece_at(square)
        if self.selected is None:
            if piece and piece.color == self.board.turn:
                self.selected = square
            return
        move = self._build_move(self.selected, square)
        if move is None:
            self.selected = square if piece and piece.color == self.board.turn else None
            return
        self.submit_move(move)

    def submit_move(self, move: chess.Move):
        """Registra un intento sin modificar la posición del desafío."""
        if self.challenge is None or self.solved:
            return None
        attempt = self.challenge.check_move(move)
        self.selected = None
        if attempt.correct:
            self.solved = True
            self.solution_move = move
            self.message = f"¡Correcto! {attempt.san}. Pulsa Nuevo reto para continuar."
        else:
            self.message = f"{attempt.message} Intenta otra vez."
        return attempt

    def _build_move(self, from_square: int, to_square: int) -> chess.Move | None:
        candidates = [
            move for move in self.board.legal_moves
            if move.from_square == from_square and move.to_square == to_square
        ]
        if not candidates:
            return None
        return next(
            (move for move in candidates if move.promotion == chess.QUEEN), candidates[0]
        )

    def _handle_panel_click(self, pos: tuple[int, int]) -> bool:
        if self.btn_retry.collidepoint(pos):
            self.retry_challenge()
            return True
        if self.btn_next.collidepoint(pos) and self.solved:
            self.next_challenge()
            return True
        return self.btn_menu.collidepoint(pos)

    def _draw_message(self) -> None:
        box = pygame.Rect(cfg.PANEL_X + 12, cfg.PANEL_Y + 240, cfg.PANEL_WIDTH - 24, 166)
        pygame.draw.rect(self.screen, (28, 28, 50), box, border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, box, 1, border_radius=8)
        title = fm.small(bold=True).render("RETO", True, cfg.C_TEXT_DIM)
        self.screen.blit(title, (box.x + 10, box.y + 9))
        self._draw_wrapped(self.message, box.x + 10, box.y + 32, box.width - 20)
        button_y = box.bottom - 48
        button_w, button_h, gap = 92, 32, 8
        self.btn_retry = pygame.Rect(box.x + 10, button_y, button_w, button_h)
        self.btn_next = pygame.Rect(self.btn_retry.right + gap, button_y, button_w, button_h)
        self.btn_menu = pygame.Rect(self.btn_next.right + gap, button_y, button_w, button_h)
        self._draw_button(self.btn_retry, "Reintentar", not self.solved)
        self._draw_button(self.btn_next, "Nuevo reto", self.solved)
        self._draw_button(self.btn_menu, "Menú", True)

    def _draw_button(self, rect: pygame.Rect, label: str, enabled: bool) -> None:
        color = cfg.C_BTN if enabled else cfg.C_PANEL_BORDER
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        text = fm.small(bold=True).render(label, True, cfg.C_BTN_TEXT if enabled else cfg.C_TEXT_DIM)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_wrapped(self, text: str, x: int, y: int, width: int) -> None:
        font = fm.small()
        line = ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and font.size(trial)[0] > width:
                self.screen.blit(font.render(line, True, cfg.C_TEXT), (x, y))
                y += font.get_linesize()
                line = word
            else:
                line = trial
        if line:
            self.screen.blit(font.render(line, True, cfg.C_TEXT), (x, y))
