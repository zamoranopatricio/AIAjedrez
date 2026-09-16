"""Importación local de posiciones desde una captura pegada del portapapeles.

Está deliberadamente acotada al tablero frontal verde/crema con las piezas
cburnett incluidas por la aplicación. No envía la imagen a ningún servicio.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

import chess
from PIL import Image, ImageChops, ImageGrab


class PositionImportError(ValueError):
    """La captura no contiene un tablero que el importador pueda leer."""


_LIGHT_MIN_PIXELS = 200
_MIN_PIECE_OVERLAP = 0.35


def read_clipboard_image(
    clipboard_reader: Callable[[], object] | None = None,
) -> Image.Image:
    """Lee una imagen del portapapeles de Windows o explica por qué no se pudo."""
    try:
        content = (clipboard_reader or ImageGrab.grabclipboard)()
    except Exception as exc:  # Windows puede negar el portapapeles momentáneamente.
        raise PositionImportError("No se pudo leer el portapapeles. Intenta copiar la captura otra vez.") from exc

    if isinstance(content, Image.Image):
        return content.convert("RGB")
    raise PositionImportError(
        "El portapapeles no contiene una imagen. Copia una captura del tablero y vuelve a intentar."
    )


def import_position_from_clipboard(assets_dir: Path) -> str:
    """Devuelve la colocación FEN (sin turno) de la captura pegada."""
    return detect_position_from_image(read_clipboard_image(), assets_dir)


def detect_position_from_image(image: Image.Image, assets_dir: Path) -> str:
    """Reconoce piezas cburnett sobre un tablero verde/crema visto de frente.

    La salida es la parte de *piece placement* del FEN. El turno se consulta en
    el menú, porque una imagen estática no permite deducirlo de forma fiable.
    """
    image = image.convert("RGB")
    board, light, dark = _extract_board(image)
    normalized = board.resize((640, 640), Image.Resampling.LANCZOS)
    templates = _load_templates(assets_dir)

    rows: list[str] = []
    for rank_from_top in range(8):
        row: list[str] = []
        empty = 0
        for file_index in range(8):
            cell = normalized.crop((file_index * 80, rank_from_top * 80,
                                    (file_index + 1) * 80, (rank_from_top + 1) * 80))
            name, overlap = _best_piece(cell, templates, light, dark)
            if overlap < _MIN_PIECE_OVERLAP:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            row.append(_fen_symbol(name))
        if empty:
            row.append(str(empty))
        rows.append("".join(row))

    placement = "/".join(rows)
    _validate_placement(placement)
    return placement


def _extract_board(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int], tuple[int, int, int]]:
    colors = image.getcolors(maxcolors=image.width * image.height)
    if not colors:
        raise PositionImportError("La captura tiene demasiados colores para detectar el tablero.")

    frequent = sorted(colors, reverse=True)
    light = next((rgb for count, rgb in frequent
                  if count >= _LIGHT_MIN_PIXELS and _is_light_square(rgb)), None)
    dark = next((rgb for count, rgb in frequent
                 if count >= _LIGHT_MIN_PIXELS and _is_dark_square(rgb)), None)
    if light is None or dark is None:
        raise PositionImportError(
            "No se detectó un tablero verde/crema compatible en la captura."
        )

    pixels = image.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            pixel = pixels[x, y]
            if _near(pixel, light) or _near(pixel, dark):
                xs.append(x)
                ys.append(y)
    if not xs:
        raise PositionImportError("No se pudo ubicar el tablero en la captura.")

    left, right = min(xs), max(xs) + 1
    top, bottom = min(ys), max(ys) + 1
    width, height = right - left, bottom - top
    # Un tablero frontal debe ser esencialmente cuadrado y suficientemente grande.
    if min(width, height) < 192 or abs(width - height) > max(width, height) * 0.08:
        raise PositionImportError(
            "La captura no parece un tablero completo visto de frente. Incluye las 64 casillas."
        )

    side = min(width, height)
    return image.crop((left, top, left + side, top + side)), light, dark


def _is_light_square(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    return r >= 180 and g >= 180 and b >= 130 and abs(r - g) <= 35 and g - b >= 5


def _is_dark_square(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    return 45 <= r <= 180 and g - r >= 18 and g - b >= 25


def _near(pixel: tuple[int, int, int], color: tuple[int, int, int], tolerance: int = 8) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color))


def _load_templates(assets_dir: Path) -> dict[str, Image.Image]:
    """Carga las siluetas de las piezas, no sus colores exactos.

    Chess.com y Lichess usan variantes de cburnett con tonos ligeramente
    distintos. Comparar la silueta las hace compatibles sin una IA remota.
    """
    templates: dict[str, Image.Image] = {}
    for color in ("w", "b"):
        for piece in "PNBRQK":
            path = assets_dir / f"{color}{piece}.png"
            if not path.exists():
                raise PositionImportError(f"Falta la plantilla de pieza {path.name}.")
            foreground = Image.open(path).convert("RGBA").resize((80, 80), Image.Resampling.LANCZOS)
            templates[f"{color}{piece}"] = foreground.getchannel("A").point(
                lambda alpha: 255 if alpha > 30 else 0
            )
    return templates


def _best_piece(
    cell: Image.Image,
    templates: dict[str, Image.Image],
    light: tuple[int, int, int],
    dark: tuple[int, int, int],
) -> tuple[str, float]:
    foreground, bright_pixels = _foreground_mask(cell.convert("RGB"), light, dark)
    best_name = ""
    best_overlap = 0.0
    for name, template in templates.items():
        intersection = ImageChops.multiply(foreground, template).histogram()[255]
        union = ImageChops.lighter(foreground, template).histogram()[255]
        overlap = intersection / union if union else 0.0
        if overlap > best_overlap:
            best_name, best_overlap = name, overlap
    # El color se determina de la captura, no de la plantilla: las siluetas
    # blanca/negra son casi iguales en cburnett pero el tono de la pieza no.
    # Las piezas negras cburnett contienen pequeños brillos, pero no ocupan
    # una zona clara grande como las blancas. El umbral se mide en una celda
    # normalizada de 80×80 px.
    color = "w" if bright_pixels >= 500 else "b"
    return color + best_name[1:], best_overlap


def _foreground_mask(
    cell: Image.Image, light: tuple[int, int, int], dark: tuple[int, int, int]
) -> tuple[Image.Image, int]:
    """Separa pieza de fondo y devuelve además su brillo medio.

    Cada casilla determina su propio color de fondo. Las interfaces de
    ajedrez suelen resaltar la última jugada en amarillo o verde claro; si se
    compara solo con los dos colores globales del tablero, ese resaltado se
    confunde con una pieza enorme.
    """
    background = _cell_background(cell, light, dark)
    foreground_values: list[int] = []
    bright_pixels = 0
    for pixel in _pixels(cell):
        distance = sum(abs(component - component_bg)
                       for component, component_bg in zip(pixel, background))
        present = distance > 45
        foreground_values.append(255 if present else 0)
        if present and sum(pixel) / 3 >= 175:
            bright_pixels += 1
    return Image.frombytes("L", cell.size, bytes(foreground_values)), bright_pixels


def _cell_background(
    cell: Image.Image,
    light: tuple[int, int, int],
    dark: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Obtiene el color plano de una casilla, aun cuando esté resaltada."""
    width, height = cell.size
    margin_x = max(2, width // 20)
    margin_y = max(2, height // 20)
    samples = [
        cell.getpixel((margin_x, margin_y)),
        cell.getpixel((width - 1 - margin_x, margin_y)),
        cell.getpixel((margin_x, height - 1 - margin_y)),
        cell.getpixel((width - 1 - margin_x, height - 1 - margin_y)),
        cell.getpixel((width // 2, margin_y)),
        cell.getpixel((margin_x, height // 2)),
        cell.getpixel((width - 1 - margin_x, height // 2)),
    ]
    # En una casilla normal el color exacto domina. El fallback conserva la
    # compatibilidad con tableros donde una etiqueta cubre una esquina.
    background, count = Counter(samples).most_common(1)[0]
    if count >= 2:
        return background
    return min(samples, key=lambda pixel: min(
        sum(abs(a - b) for a, b in zip(pixel, light)),
        sum(abs(a - b) for a, b in zip(pixel, dark)),
    ))


def _pixels(image: Image.Image):
    """Compatibilidad con Pillow actual y versiones anteriores."""
    if hasattr(image, "get_flattened_data"):
        return image.get_flattened_data()
    return image.getdata()


def _fen_symbol(name: str) -> str:
    symbol = name[1]
    return symbol if name[0] == "w" else symbol.lower()


def _validate_placement(placement: str) -> tuple[str, ...]:
    """Valida errores simples que una imagen puede introducir al reconocer.

    No intenta reconstruir el historial de la partida: una posición puede
    tener dos damas por una promoción. Sí bloquea configuraciones imposibles
    o muy probablemente producto de una detección equivocada.
    """
    try:
        board = chess.Board(f"{placement} w - - 0 1")
    except ValueError as exc:
        raise PositionImportError("Las piezas detectadas no forman una posición FEN válida.") from exc

    for color, side in ((chess.WHITE, "blanco"), (chess.BLACK, "negro")):
        king_count = len(board.pieces(chess.KING, color))
        if king_count != 1:
            expected = "un rey"
            found = "ningún rey" if king_count == 0 else f"{king_count} reyes"
            raise PositionImportError(
                f"La posición detectada no es válida: debe haber exactamente {expected} {side}; se detectó {found}."
            )

        pawn_count = len(board.pieces(chess.PAWN, color))
        if pawn_count > 8:
            raise PositionImportError(
                f"La posición detectada no es válida: las {('blancas' if color else 'negras')} no pueden tener más de 8 peones."
            )

        piece_count = board.occupied_co[color].bit_count()
        if piece_count > 16:
            raise PositionImportError(
                f"La posición detectada no es válida: las {('blancas' if color else 'negras')} no pueden tener más de 16 piezas."
            )

        queen_count = len(board.pieces(chess.QUEEN, color))
        if queen_count > 2:
            raise PositionImportError(
                f"La posición detectada no es válida: las {('blancas' if color else 'negras')} tienen más de dos damas."
            )

    pawns_on_back_rank = board.pieces(chess.PAWN, chess.WHITE) | board.pieces(chess.PAWN, chess.BLACK)
    if pawns_on_back_rank & (chess.BB_RANK_1 | chess.BB_RANK_8):
        raise PositionImportError(
            "La posición detectada no es válida: no puede haber peones en la primera fila ni en la octava fila."
        )

    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    assert white_king is not None and black_king is not None
    if chess.square_distance(white_king, black_king) <= 1:
        raise PositionImportError(
            "La posición detectada no es válida: los reyes no pueden estar adyacentes."
        )

    warnings: list[str] = []
    for color, side in ((chess.WHITE, "blancas"), (chess.BLACK, "negras")):
        if len(board.pieces(chess.QUEEN, color)) == 2:
            warnings.append(f"Se detectaron dos damas {side}; puede ser una promoción válida.")
    return tuple(warnings)


def position_warnings(placement: str) -> tuple[str, ...]:
    """Devuelve avisos no bloqueantes para mostrar antes de iniciar la partida."""
    return _validate_placement(placement)


def validate_initial_fen(fen: str) -> None:
    """Comprueba la legalidad dependiente del turno elegido en el menú."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise PositionImportError("La posición detectada no forma una partida válida.") from exc
    if not board.is_valid():
        raise PositionImportError(
            "La posición no es legal para el turno elegido. Revisa quién mueve o vuelve a importar la captura."
        )
