import chess

from main import ChessApp
from src.game_state import GameMode
from src.menu import MenuResult


def test_app_launches_tracking_screen_before_the_initial_screen_position_is_read(monkeypatch):
    launched = {}

    class FakeTrackingScreen:
        def __init__(self, screen, piece_images, initial_fen, *, white_bottom):
            launched.update(
                screen=screen,
                piece_images=piece_images,
                initial_fen=initial_fen,
                white_bottom=white_bottom,
            )

        def run(self):
            launched["ran"] = True

    monkeypatch.setattr("main.LiveTrackingScreen", FakeTrackingScreen)
    app = ChessApp.__new__(ChessApp)
    app.screen = "screen"
    app.piece_images = "pieces"
    result = MenuResult(
        GameMode.HUMAN_VS_HUMAN,
        chess.WHITE,
        0,
        initial_fen=None,
        initial_flipped=None,
        tracking_mode=True,
    )

    app._run_tracking(result)

    assert launched == {
        "screen": "screen",
        "piece_images": "pieces",
        "initial_fen": None,
        "white_bottom": True,
        "ran": True,
    }
