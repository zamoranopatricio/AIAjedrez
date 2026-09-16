import pygame

from src.game_state import GameMode
from src.menu import MenuScreen


PLACEMENT = "4k3/8/8/3Q4/8/8/8/4K3"


def _screen():
    pygame.init()
    return pygame.display.set_mode((1, 1))


def test_import_button_opens_explicit_side_to_move_question(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu = MenuScreen(_screen(), engine_available=False)

    menu._handle_click(menu._btn_import.rect.center)

    assert menu._side_dialog_active is True
    assert "Qui\u00e9n mueve" in menu._status_message

    menu._handle_click(menu._btn_orientation_white.rect.center)
    menu._handle_click(menu._btn_turn_white.rect.center)
    menu._handle_click(menu._btn_confirm_import.rect.center)
    result = menu._handle_click(menu._btn_play.rect.center)

    assert result is not None
    assert result.mode is GameMode.HUMAN_VS_HUMAN
    assert result.initial_fen == f"{PLACEMENT} w - - 0 1"


def test_turn_dialog_can_start_imported_position_with_black_to_move(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu = MenuScreen(_screen())

    menu._handle_click(menu._btn_import.rect.center)
    menu._handle_click(menu._btn_orientation_white.rect.center)
    menu._handle_click(menu._btn_turn_black.rect.center)
    menu._handle_click(menu._btn_confirm_import.rect.center)
    result = menu._handle_click(menu._btn_play.rect.center)

    assert result is not None
    assert result.initial_fen == f"{PLACEMENT} b - - 0 1"


def test_imported_second_queen_is_explained_as_a_promotion_warning(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    monkeypatch.setattr(
        "src.menu.position_warnings",
        lambda _: ("Se detectaron dos damas blancas; puede ser una promoción válida.",),
    )
    menu = MenuScreen(_screen())

    menu._handle_click(menu._btn_import.rect.center)
    menu._handle_click(menu._btn_orientation_white.rect.center)
    menu._handle_click(menu._btn_turn_white.rect.center)
    menu._handle_click(menu._btn_confirm_import.rect.center)

    assert "promoción válida" in menu._status_message


def test_invalid_new_capture_clears_a_previous_import_and_blocks_play(monkeypatch):
    from src.position_import import PositionImportError

    menu = MenuScreen(_screen())
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu._import_from_clipboard()
    menu._select_imported_orientation(True)
    menu._select_imported_turn(True)
    menu._confirm_import()
    assert menu._initial_fen() is not None

    def invalid_capture(_):
        raise PositionImportError("La posición detectada no es válida: los reyes no pueden estar adyacentes.")

    monkeypatch.setattr("src.menu.import_position_from_clipboard", invalid_capture)
    menu._import_from_clipboard()

    assert menu._initial_fen() is None
    assert menu._status_is_error is True


def test_import_requires_orientation_turn_and_explicit_confirmation(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu = MenuScreen(_screen())
    menu._import_from_clipboard()
    menu._confirm_import()
    assert menu._initial_fen() is None
    menu._select_imported_turn(True)
    menu._confirm_import()
    assert menu._initial_fen() is None
    assert menu._side_dialog_active
    menu._select_imported_orientation(False)
    assert menu._initial_fen() is None
    menu._confirm_import()
    assert menu._initial_fen() == "3K4/8/8/8/4Q3/8/8/3k4 w - - 0 1"
    result = menu._handle_click(menu._btn_play.rect.center)
    assert result.initial_flipped is True


def test_invalid_turn_can_be_corrected_without_losing_capture(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: "4k3/8/8/8/8/8/8/4R2K")
    menu = MenuScreen(_screen())
    menu._import_from_clipboard()
    menu._select_imported_orientation(True)
    menu._select_imported_turn(True)
    menu._confirm_import()
    assert menu._side_dialog_active and menu._status_is_error
    assert menu._initial_fen() is None
    menu._select_imported_turn(False)
    menu._confirm_import()
    assert menu._initial_fen() == "4k3/8/8/8/8/8/8/4R2K b - - 0 1"


def test_cancel_import_discards_pending_position_and_allows_standard_game(monkeypatch):
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu = MenuScreen(_screen())
    menu._import_from_clipboard()
    menu._select_imported_orientation(False)
    menu._select_imported_turn(True)
    menu._handle_click(menu._btn_cancel_import.rect.center)
    assert not menu._side_dialog_active
    assert menu._initial_fen() is None
    assert menu._imported_placement is None
    assert menu._handle_click(menu._btn_play.rect.center).initial_fen is None


def test_preview_coordinates_and_pieces_match_selected_capture_orientation(monkeypatch):
    import chess
    monkeypatch.setattr("src.menu.import_position_from_clipboard", lambda _: PLACEMENT)
    menu = MenuScreen(_screen())
    menu._import_from_clipboard()
    menu._select_imported_orientation(True)
    assert menu._preview_square(0, 7) == chess.A1
    assert menu._preview_board().piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK)
    menu._select_imported_orientation(False)
    assert menu._preview_square(0, 7) == chess.H8
    assert menu._preview_board().piece_at(chess.D1) == chess.Piece(chess.KING, chess.BLACK)
    menu._draw((0, 0))
