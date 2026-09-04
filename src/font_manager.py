"""
src/font_manager.py
Selecciona automáticamente la mejor fuente amigable disponible en el sistema.
Prioriza Ubuntu > Cantarell > DejaVu Sans > Liberation Sans > fallback.
"""
import pygame

_SANS = [
    "ubuntu", "cantarell", "noto sans", "liberation sans",
    "dejavu sans", "freesans", "opensans", "segoeui", "arial",
]
_BOLD = [
    "ubuntu bold", "cantarell bold", "noto sans bold",
    "liberation sans bold", "dejavu sans bold",
]
_TITLE = [
    "ubuntu", "cantarell", "noto sans", "liberation sans",
]

_cache: dict = {}


def _resolve(names: list[str], bold: bool) -> str | None:
    for name in names:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return path
    return None


def get(size: int, bold: bool = False, style: str = "sans") -> pygame.font.Font:
    """
    Devuelve una fuente amigable del tamaño indicado.
    style: "sans" | "title"
    """
    key = (size, bold, style)
    if key in _cache:
        return _cache[key]

    candidates = _BOLD if bold else (_TITLE if style == "title" else _SANS)
    path = _resolve(candidates, bold)

    if path:
        font = pygame.font.Font(path, size)
    else:
        font = pygame.font.SysFont("sans", size, bold=bold)

    _cache[key] = font
    return font


def small(bold: bool = False)  -> pygame.font.Font: return get(12, bold)
def normal(bold: bool = False) -> pygame.font.Font: return get(14, bold)
def medium(bold: bool = False) -> pygame.font.Font: return get(16, bold)
def large(bold: bool = False)  -> pygame.font.Font: return get(20, bold)
def title(bold: bool = True)   -> pygame.font.Font: return get(36, bold, "title")
def huge(bold: bool = True)    -> pygame.font.Font: return get(48, bold, "title")
