"""Pantalla local de entrenamiento: una posición y una respuesta del jugador."""
from __future__ import annotations

import pygame
import chess

from src.board_gui import BoardGUI, pixel_to_square
from src.training import TrainingChallenge
from src import font_manager as fm
import config as cfg


_PUZZLE_FEN = "6k1/5ppp/8/7Q/8/8/6PP/6K1 w - - 0 1"


class TrainingScreen:
    """Reto aislado del juego: Stockfish sólo valida la respuesta local."""

    def __init__(self, screen: pygame.Surface, piece_images: dict, engine) -> None:
        self.screen = screen
        self.engine = engine
        self.gui = BoardGUI(screen, piece_images)
        self.board = chess.Board(_PUZZLE_FEN)
        self.selected: int | None = None
        self.challenge: TrainingChallenge | None = None
        self.message = "Stockfish está preparando el reto…"
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        self.engine.clear()
        self.engine.request_analysis(self.board)
        running = True
        while running:
            self.clock.tick(cfg.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m):
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._make_challenge_when_ready()
            targets = self._legal_targets()
            self.gui.draw(
                self.board, self.selected, targets, None, None, None, None, (0, 0), [],
                "Entrenamiento local", True, show_ai_indicator=False,
            )
            self._draw_message()
            pygame.display.flip()

    def _make_challenge_when_ready(self) -> None:
        if self.challenge is None and not self.engine.is_analysing:
            best = self.engine.best_move
            if best is not None:
                self.challenge = TrainingChallenge.from_engine(self.board, [best])
                self.message = "Tu turno: encuentra la mejor jugada. Esc para volver."

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
        attempt = self.challenge.check_move(move)
        self.message = attempt.message
        self.selected = None

    def _build_move(self, from_square: int, to_square: int) -> chess.Move | None:
        for move in self.board.legal_moves:
            if move.from_square == from_square and move.to_square == to_square:
                return chess.Move(from_square, to_square, chess.QUEEN) if move.promotion else move
        return None

    def _draw_message(self) -> None:
        box = pygame.Rect(cfg.PANEL_X + 12, cfg.PANEL_Y + 240, cfg.PANEL_WIDTH - 24, 92)
        pygame.draw.rect(self.screen, (28, 28, 50), box, border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, box, 1, border_radius=8)
        title = fm.small(bold=True).render("RETO", True, cfg.C_TEXT_DIM)
        self.screen.blit(title, (box.x + 10, box.y + 9))
        self._draw_wrapped(self.message, box.x + 10, box.y + 32, box.width - 20)

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
