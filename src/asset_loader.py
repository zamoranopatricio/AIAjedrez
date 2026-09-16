"""
src/asset_loader.py
Descarga el set de piezas "cburnett" de lichess (SVG → PNG) y las carga en Pygame.
Solo necesita internet la primera vez; luego funciona 100 % offline.
"""
import logging
from pathlib import Path

import requests
import cairosvg
import pygame
import chess

log = logging.getLogger(__name__)

# Mapa nombre ↔ código cburnett
_COLOR_MAP  = {chess.WHITE: "w", chess.BLACK: "b"}
_PIECE_MAP  = {
    chess.PAWN:   "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK:   "R",
    chess.QUEEN:  "Q",
    chess.KING:   "K",
}

# Tonos cercanos al set gris/crema de Chess.com. Se aplican sobre los SVG
# cburnett ya incluidos, por lo que la silueta usada por el importador y la que
# ve el usuario son la misma.
_BLACK_BODY = (75, 75, 75)
_BLACK_OUTLINE = (45, 45, 45)
_WHITE_OUTLINE = (70, 70, 70)

_LICHESS_BASE = (
    "https://raw.githubusercontent.com/lichess-org/lila/"
    "master/public/piece/cburnett"
)

# ── Descarga ───────────────────────────────────────────────────────────────

def download_pieces(assets_dir: Path, size: int = 80) -> bool:
    """
    Descarga y convierte las 12 piezas SVG a PNG.
    Devuelve True si todas las piezas están disponibles.
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    all_names = [
        f"{c}{p}"
        for c in ("w", "b")
        for p in ("P", "N", "B", "R", "Q", "K")
    ]
    missing = [n for n in all_names if not (assets_dir / f"{n}.png").exists()]

    if not missing:
        return True

    log.info("Descargando set de piezas cburnett (%d piezas)…", len(missing))
    ok = True
    for name in missing:
        url = f"{_LICHESS_BASE}/{name}.svg"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            png_bytes = cairosvg.svg2png(
                bytestring=resp.content,
                output_width=size,
                output_height=size,
            )
            (assets_dir / f"{name}.png").write_bytes(png_bytes)
            log.debug("  ✓ %s", name)
        except Exception as exc:
            log.error("  ✗ No se pudo descargar %s: %s", name, exc)
            ok = False

    if ok:
        log.info("Piezas descargadas correctamente.")
    return ok


# ── Carga en Pygame ────────────────────────────────────────────────────────

def load_piece_images(assets_dir: Path, size: int = 80) -> dict:
    """
    Devuelve un dict { chess.Piece → pygame.Surface }.
    Si no existe el PNG de alguna pieza devuelve superficie vacía (fallback).
    """
    images: dict[chess.Piece, pygame.Surface] = {}

    for color in (chess.WHITE, chess.BLACK):
        for piece_type in (
            chess.PAWN, chess.KNIGHT, chess.BISHOP,
            chess.ROOK,  chess.QUEEN,  chess.KING,
        ):
            name = f"{_COLOR_MAP[color]}{_PIECE_MAP[piece_type]}"
            path = assets_dir / f"{name}.png"
            piece = chess.Piece(piece_type, color)

            if path.exists():
                surf = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.smoothscale(surf, (size, size))
                images[piece] = _apply_chess_com_style(surf, color)
            else:
                log.warning("Pieza no encontrada: %s — usando fallback Unicode", name)
                images[piece] = _make_unicode_surface(piece, size)

    return images


def _apply_chess_com_style(surface: pygame.Surface, color: chess.Color) -> pygame.Surface:
    """Aproxima el acabado gris con bordes visibles del set de Chess.com.

    No sustituye la geometría cburnett: así una captura de la aplicación usa
    exactamente las mismas siluetas que reconoce ``position_import``.
    """
    styled = surface.copy()
    replacement = _BLACK_BODY if color == chess.BLACK else _WHITE_OUTLINE

    for y in range(styled.get_height()):
        for x in range(styled.get_width()):
            px = styled.get_at((x, y))
            if px.a and max(px.r, px.g, px.b) <= 12:
                styled.set_at((x, y), (*replacement, px.a))

    if color == chess.BLACK:
        mask = pygame.mask.from_surface(styled, threshold=1)
        outline = mask.outline()
        if len(outline) > 1:
            pygame.draw.lines(styled, _BLACK_OUTLINE, True, outline, 1)
    return styled


def _make_unicode_surface(piece: chess.Piece, size: int) -> pygame.Surface:
    """Fallback: renderiza el símbolo Unicode de la pieza en una superficie."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.font.init()
    font = pygame.font.SysFont("segoeuisymbol,symbola,unifont", int(size * 0.85))
    symbol = piece.unicode_symbol()
    color = (255, 255, 255) if piece.color == chess.WHITE else (30, 30, 30)
    outline_color = (30, 30, 30) if piece.color == chess.WHITE else (220, 220, 220)
    # outline
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        t = font.render(symbol, True, outline_color)
        r = t.get_rect(center=(size // 2 + dx, size // 2 + dy))
        surf.blit(t, r)
    text = font.render(symbol, True, color)
    rect = text.get_rect(center=(size // 2, size // 2))
    surf.blit(text, rect)
    return surf
