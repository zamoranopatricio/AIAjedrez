from types import SimpleNamespace

import chess
import pygame

from main import ChessApp
from src.board_gui import square_to_pixel
from src.game_state import GameMode, GameState


class _EngineStub:
    def clear(self):
        pass


def _app_at_initial_position():
    app = ChessApp.__new__(ChessApp)
    app.state = GameState(mode=GameMode.HUMAN_VS_HUMAN)
    app.gui = SimpleNamespace(flipped=False)
    app.engine = _EngineStub()
    app._dragging_piece = None
    app._drag_from = None
    app._drag_pos = (0, 0)
    app._ai_move_pending = False
    app._last_fen = ""
    app._focus_click_pending = True
    app._focus_click_replayed = False
    return app


def test_held_click_when_focus_returns_can_drag_a_pawn():
    app = _app_at_initial_position()
    from_pos = square_to_pixel(chess.E2)
    to_pos = square_to_pixel(chess.E4)

    replayed = app._recover_focus_click(from_pos, left_button_down=True)
    app._handle_mouse(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=to_pos))

    assert replayed is True
    assert app.state.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert app.state.board.piece_at(chess.E2) is None


def test_focus_recovery_does_not_select_a_piece_without_a_held_click():
    app = _app_at_initial_position()

    replayed = app._recover_focus_click(square_to_pixel(chess.E2), left_button_down=False)

    assert replayed is False
    assert app.state.selected_square is None
    assert app._dragging_piece is None
    assert app._focus_click_replayed is False


def test_replayed_focus_press_is_consumed_only_once_when_pygame_also_reports_it():
    app = _app_at_initial_position()
    pos = square_to_pixel(chess.E2)
    press = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)

    app._recover_focus_click(pos, left_button_down=True)

    assert app._consume_replayed_focus_press(press) is True
    assert app._consume_replayed_focus_press(press) is False
