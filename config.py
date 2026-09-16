"""
config.py — Configuración global del proyecto AIAjedrez.
Modifica este archivo o usa un .env para cambiar rutas y parámetros.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.platform_utils import get_base_dir, find_stockfish_binary

BASE_DIR = get_base_dir()

# ── Ventana ────────────────────────────────────────────────────────────────
WINDOW_WIDTH  = 1100
WINDOW_HEIGHT = 720
FPS           = 60
TITLE         = "AI Ajedrez"

# ── Tablero ────────────────────────────────────────────────────────────────
SQUARE_SIZE    = 80           # px por casilla
BOARD_SIZE     = SQUARE_SIZE * 8   # 640
BOARD_OFFSET_X = 80           # margen izquierdo del tablero
BOARD_OFFSET_Y = 40           # margen superior del tablero

# ── Panel lateral ──────────────────────────────────────────────────────────
PANEL_X      = BOARD_OFFSET_X + BOARD_SIZE + 24
PANEL_Y      = BOARD_OFFSET_Y
PANEL_WIDTH  = WINDOW_WIDTH - PANEL_X - 14
PANEL_HEIGHT = BOARD_SIZE

# ── Barra de evaluación ────────────────────────────────────────────────────
EVAL_BAR_X      = 44
EVAL_BAR_Y      = BOARD_OFFSET_Y
EVAL_BAR_WIDTH  = 20
EVAL_BAR_HEIGHT = BOARD_SIZE

# ── Paleta de colores ──────────────────────────────────────────────────────
C_BG               = (14, 14, 26)
C_LIGHT_SQ         = (240, 217, 181)
C_DARK_SQ          = (181, 136, 99)
C_HIGHLIGHT_SEL    = (20,  200,  60, 170)
C_HIGHLIGHT_LEGAL  = (20,  200,  60,  75)
C_LAST_MOVE        = (205, 210, 106, 140)
C_CHECK            = (220,  40,  40, 170)
C_ARROW_FILL       = (255, 160,   0, 185)
C_ARROW_OUTLINE    = (200, 110,   0, 255)
C_PANEL_BG         = (22,  22,  40)
C_PANEL_BORDER     = (55,  55,  90)
C_TEXT             = (230, 230, 235)
C_TEXT_DIM         = (130, 130, 155)
C_TEXT_ACCENT      = (100, 180, 255)
C_EVAL_WHITE       = (245, 245, 245)
C_EVAL_BLACK       = (25,  25,  35)
C_EVAL_BORDER      = (70,  70, 100)
C_BTN              = (40, 100, 200)
C_BTN_HOVER        = (60, 130, 240)
C_BTN_DANGER       = (180,  40,  40)
C_BTN_DANGER_HOVER = (220,  60,  60)
C_BTN_TEXT         = (255, 255, 255)
C_OVERLAY          = (0,    0,   0, 200)

# Menú
C_MENU_BG       = (14, 14, 26)
C_CARD          = (28, 28, 50)
C_CARD_HOVER    = (40, 40, 70)
C_CARD_BORDER   = (60, 60, 100)
C_ACCENT        = (100, 160, 255)
C_SELECTED      = (60,  130, 255)
C_SELECTED_BG   = (30,  60, 130)

# ── Stockfish ──────────────────────────────────────────────────────────────
STOCKFISH_PATH = find_stockfish_binary(BASE_DIR)

# ── Análisis ───────────────────────────────────────────────────────────────
ANALYSIS_TIME_S = 0.15   # segundos por análisis en background

# ── Niveles de dificultad ──────────────────────────────────────────────────
DIFFICULTY_LEVELS = [
    {"name": "Principiante", "skill": 1,  "time": 0.05},
    {"name": "Fácil",        "skill": 5,  "time": 0.10},
    {"name": "Intermedio",   "skill": 10, "time": 0.15},
    {"name": "Avanzado",     "skill": 15, "time": 0.25},
    {"name": "Experto",      "skill": 18, "time": 0.40},
    {"name": "Máximo",       "skill": 20, "time": 0.60},
]

# ── Assets ─────────────────────────────────────────────────────────────────
ASSETS_DIR = BASE_DIR / "assets" / "pieces"
SAVES_DIR  = BASE_DIR / "saves"
