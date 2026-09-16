from types import SimpleNamespace

import chess
import pygame

import config as cfg
from main import ChessApp
from src.board_gui import BoardGUI, square_to_pixel
from src.game_state import GameMode, GameState


def _pieces():
    return {
        chess.Piece(piece_type, color): pygame.Surface((80, 80), pygame.SRCALPHA)
        for color in (chess.WHITE, chess.BLACK)
        for piece_type in range(chess.PAWN, chess.KING + 1)
    }


def test_free_relocation_resets_history_and_transient_rights():
    state = GameState()
    state.push_ai_move(chess.Move.from_uci("e2e4"))
    state.board.ep_square = chess.E3

    moved = state.relocate_piece_for_test(chess.A7, chess.A3)

    assert moved == chess.Piece(chess.PAWN, chess.BLACK)
    assert state.board.piece_at(chess.A7) is None
    assert state.board.piece_at(chess.A3) == chess.Piece(chess.PAWN, chess.BLACK)
    assert state.board.castling_rights == chess.BB_EMPTY
    assert state.board.ep_square is None
    assert state.san_history == []
    assert state.moves_played == []
    assert state.last_move is None
    assert state.board.move_stack == []


def test_free_relocation_refuses_to_capture_a_king_without_mutating_game():
    state = GameState()
    before = state.board.fen()

    moved = state.relocate_piece_for_test(chess.D1, chess.E8)

    assert moved is None
    assert state.board.fen() == before


def test_right_click_relocates_only_in_human_vs_human_and_resets_analysis():
    app = ChessApp.__new__(ChessApp)
    app.state = GameState(mode=GameMode.HUMAN_VS_HUMAN)
    app.gui = SimpleNamespace(flipped=False)
    app.test_mode_enabled = True
    app._dragging_piece = None
    app._drag_from = None
    app._drag_pos = (0, 0)
    app._on_test_position_edited = lambda: setattr(app, "edit_count", getattr(app, "edit_count", 0) + 1)

    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=square_to_pixel(chess.A7)
    ))
    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=square_to_pixel(chess.A3)
    ))

    assert app.state.board.piece_at(chess.A3) == chess.Piece(chess.PAWN, chess.BLACK)
    assert app.edit_count == 1

    app.state = GameState(mode=GameMode.HUMAN_VS_AI)
    app.test_mode_enabled = True
    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=square_to_pixel(chess.A7)
    ))
    assert app.state.selected_square is None


def test_right_click_source_is_independent_from_a_normal_left_click_selection():
    app = ChessApp.__new__(ChessApp)
    app.state = GameState(mode=GameMode.HUMAN_VS_HUMAN)
    app.gui = SimpleNamespace(flipped=False)
    app.test_mode_enabled = True
    app._dragging_piece = None
    app._drag_from = None
    app._drag_pos = (0, 0)
    app._on_test_position_edited = lambda: None

    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=square_to_pixel(chess.E2)
    ))
    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=square_to_pixel(chess.A7)
    ))
    app._handle_mouse(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=square_to_pixel(chess.A3)
    ))

    assert app.state.board.piece_at(chess.E2) == chess.Piece(chess.PAWN, chess.WHITE)
    assert app.state.board.piece_at(chess.A3) == chess.Piece(chess.PAWN, chess.BLACK)


def test_board_panel_shows_test_mode_toggle_only_when_requested():
    pygame.init()
    gui = BoardGUI(pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT)), _pieces())
    kwargs = dict(
        board=chess.Board(), selected_square=None, legal_targets=[], last_move=None,
        best_move=None, score=None, dragging_piece=None, drag_pos=(0, 0),
        san_history=[], mode_label="Humano vs Humano", engine_available=True,
    )

    gui.draw(**kwargs, show_test_mode_toggle=True, test_mode_enabled=True)
    assert gui.btn_toggle_test_mode.width > 0

    gui.draw(**kwargs, show_test_mode_toggle=False)
    assert gui.btn_toggle_test_mode.width == 0
