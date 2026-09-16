from pathlib import Path

import chess
import pytest
from PIL import Image


def _board_image(placements: dict[str, str], assets_dir: Path) -> Image.Image:
    """Construye una captura sintética a partir de las mismas piezas cburnett."""
    from PIL import ImageDraw

    size = 80
    image = Image.new("RGB", (size * 8, size * 8), (238, 238, 210))
    draw = ImageDraw.Draw(image)
    for rank_from_top in range(8):
        for file_index in range(8):
            if (rank_from_top + file_index) % 2:
                draw.rectangle(
                    (file_index * size, rank_from_top * size,
                     (file_index + 1) * size - 1, (rank_from_top + 1) * size - 1),
                    fill=(118, 150, 86),
                )
    for square, piece_name in placements.items():
        file_index = ord(square[0]) - ord("a")
        rank_from_top = 8 - int(square[1])
        piece = Image.open(assets_dir / f"{piece_name}.png").convert("RGBA")
        image.paste(piece, (file_index * size, rank_from_top * size), piece)
    return image


def test_detects_starting_position_from_cburnett_board():
    from src.position_import import detect_position_from_image

    assets = Path("assets/pieces")
    pieces = {
        **{f"{file}2": "wP" for file in "abcdefgh"},
        **{f"{file}7": "bP" for file in "abcdefgh"},
        "a1": "wR", "b1": "wN", "c1": "wB", "d1": "wQ", "e1": "wK", "f1": "wB", "g1": "wN", "h1": "wR",
        "a8": "bR", "b8": "bN", "c8": "bB", "d8": "bQ", "e8": "bK", "f8": "bB", "g8": "bN", "h8": "bR",
    }

    assert detect_position_from_image(_board_image(pieces, assets), assets) == chess.STARTING_BOARD_FEN


def test_detects_sparse_position_and_keeps_empty_squares_empty():
    from src.position_import import detect_position_from_image

    assets = Path("assets/pieces")
    image = _board_image({"e1": "wK", "d5": "wQ", "e8": "bK", "a7": "bP"}, assets)

    assert detect_position_from_image(image, assets) == "4k3/p7/8/3Q4/8/8/8/4K3"


def test_rejects_image_that_is_not_a_supported_chessboard():
    from src.position_import import PositionImportError, detect_position_from_image

    with pytest.raises(PositionImportError, match="tablero"):
        detect_position_from_image(Image.new("RGB", (400, 300), "red"), Path("assets/pieces"))


def test_detects_reference_chess_com_capture_with_highlighted_squares():
    """A highlighted square is still a square, never a queen-sized piece."""
    from src.position_import import detect_position_from_image

    screenshot = Path(
        r"C:\Users\esteb\AppData\Local\Temp\codex-clipboard-14b22909-ffde-4a25-890b-900426513888.png"
    )
    if not screenshot.exists():
        pytest.skip("La captura de regresión solo está disponible en el equipo de desarrollo.")

    assert detect_position_from_image(Image.open(screenshot), Path("assets/pieces")) == (
        "r1b1k1nr/p5bp/n1p2p2/8/3N4/8/PPP2PPP/RNBK1B1R"
    )


@pytest.mark.parametrize(
    ("placement", "message"),
    [
        ("8/8/8/8/8/8/8/4K3", "rey negro"),
        ("4k3/8/8/8/8/8/8/3KK3", "rey blanco"),
        ("4k3/PPPPPPPP/P7/8/8/8/8/4K3", "8 peones"),
        ("4k3/8/8/8/8/8/8/P3K3", "primera fila"),
        ("4k3/4K3/8/8/8/8/8/8", "adyacentes"),
        ("4k3/8/8/8/8/8/8/QQQ1K3", "más de dos damas"),
    ],
)
def test_rejects_obvious_invalid_material_before_starting_imported_game(placement, message):
    from src.position_import import PositionImportError, _validate_placement

    with pytest.raises(PositionImportError, match=message):
        _validate_placement(placement)


def test_allows_two_queens_as_a_possible_promotion_and_explains_it():
    from src.position_import import _validate_placement

    warnings = _validate_placement("4k3/8/8/8/8/8/8/QQ2K3")

    assert warnings == ("Se detectaron dos damas blancas; puede ser una promoción válida.",)


def test_check_legality_is_validated_after_the_user_chooses_the_turn():
    from src.position_import import PositionImportError, validate_initial_fen

    # Las blancas están dando jaque a e8: solo es válido si mueven negras.
    placement = "4k3/8/8/8/8/8/8/4R2K"
    validate_initial_fen(f"{placement} b - - 0 1")

    with pytest.raises(PositionImportError, match="turno elegido"):
        validate_initial_fen(f"{placement} w - - 0 1")
