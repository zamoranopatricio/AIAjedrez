"""
src/menu.py
Pantalla de menú inicial con selección de modo, dificultad y color.
"""
import pygame
import chess
import sys
from dataclasses import dataclass
from typing import Optional

import config as cfg
from src.game_state import GameMode
from src import font_manager as fm


@dataclass
class MenuResult:
    mode: GameMode
    human_color: chess.Color
    difficulty_index: int
    show_ai_indicator: bool = True


class _Button:
    def __init__(self, rect: pygame.Rect, text: str,
                 selected: bool = False, font: Optional[pygame.font.Font] = None):
        self.rect = rect
        self.text = text
        self.selected = selected
        self._font = font

    def draw(self, surface: pygame.Surface, hovered: bool):
        if self.selected:
            bg  = cfg.C_SELECTED_BG
            bdr = cfg.C_SELECTED
        else:
            bg  = cfg.C_CARD_HOVER if hovered else cfg.C_CARD
            bdr = cfg.C_ACCENT if hovered else cfg.C_CARD_BORDER

        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, bdr, self.rect, 2, border_radius=10)

        font = self._font or fm.normal(bold=self.selected)
        t = font.render(self.text, True, cfg.C_TEXT)
        surface.blit(t, t.get_rect(center=self.rect.center))

    def is_hovered(self, pos) -> bool:
        return self.rect.collidepoint(pos)


class MenuScreen:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock  = pygame.time.Clock()

        self._mode         = GameMode.HUMAN_VS_AI
        self._color        = chess.WHITE
        self._diff_index   = 2
        self._ai_indicator = True

        self._build_buttons()

    # ── Loop ───────────────────────────────────────────────────────────────

    def run(self) -> MenuResult:
        while True:
            mp = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    r = self._handle_click(mp)
                    if r:
                        return r

            self._draw(mp)
            pygame.display.flip()
            self.clock.tick(cfg.FPS)

    # ── Botones ────────────────────────────────────────────────────────────

    def _build_buttons(self):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        cx = W // 2

        bw, bh = 220, 48
        gap = 18
        total = bw * 2 + gap
        self._btn_hvai = _Button(
            pygame.Rect(cx - total // 2, 158, bw, bh), "Humano vs IA")
        self._btn_hvh = _Button(
            pygame.Rect(cx - total // 2 + bw + gap, 158, bw, bh), "Humano vs Humano")

        self._btn_white = _Button(pygame.Rect(cx - 125, 248, 115, 42), "Blancas")
        self._btn_black = _Button(pygame.Rect(cx + 10,  248, 115, 42), "Negras")

        diffs   = cfg.DIFFICULTY_LEVELS
        d_btn_w = min(118, (W - 80) // len(diffs) - 8)
        total_d = len(diffs) * d_btn_w + (len(diffs) - 1) * 6
        d_start = cx - total_d // 2
        self._btn_diffs = []
        for i, d in enumerate(diffs):
            rect = pygame.Rect(d_start + i * (d_btn_w + 6), 332, d_btn_w, 42)
            self._btn_diffs.append(_Button(rect, d["name"], font=fm.small(bold=False)))

        # Selector Indicador IA (Activado / Desactivado)
        self._btn_ind_on  = _Button(pygame.Rect(cx - 145, 416, 140, 42), "ON (Activo)")
        self._btn_ind_off = _Button(pygame.Rect(cx + 5,   416, 140, 42), "OFF (Oculto)")

        self._btn_play = _Button(
            pygame.Rect(cx - 125, H - 115, 250, 54), "JUGAR",
            font=fm.large(bold=True))

    # ── Clics ──────────────────────────────────────────────────────────────

    def _handle_click(self, pos) -> Optional[MenuResult]:
        if self._btn_hvai.is_hovered(pos):
            self._mode = GameMode.HUMAN_VS_AI
        elif self._btn_hvh.is_hovered(pos):
            self._mode = GameMode.HUMAN_VS_HUMAN
        elif self._btn_white.is_hovered(pos):
            self._color = chess.WHITE
        elif self._btn_black.is_hovered(pos):
            self._color = chess.BLACK
        elif self._btn_ind_on.is_hovered(pos):
            self._ai_indicator = True
        elif self._btn_ind_off.is_hovered(pos):
            self._ai_indicator = False
        elif self._btn_play.is_hovered(pos):
            return MenuResult(
                mode=self._mode,
                human_color=self._color,
                difficulty_index=self._diff_index,
                show_ai_indicator=self._ai_indicator,
            )
        else:
            for i, btn in enumerate(self._btn_diffs):
                if btn.is_hovered(pos):
                    self._diff_index = i
                    break
        return None

    # ── Render ─────────────────────────────────────────────────────────────

    def _draw(self, mp):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        cx = W // 2
        self.screen.fill(cfg.C_MENU_BG)

        # Gradiente sutil
        grad = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(H):
            a = int(35 * (1 - i / H))
            pygame.draw.line(grad, (80, 120, 255, a), (0, i), (W, i))
        self.screen.blit(grad, (0, 0))

        # Título
        t = fm.title().render("AI Ajedrez", True, cfg.C_TEXT)
        self.screen.blit(t, t.get_rect(center=(cx, 56)))
        t2 = fm.normal().render(
            "Entorno local de ajedrez con análisis Stockfish en tiempo real",
            True, cfg.C_TEXT_DIM)
        self.screen.blit(t2, t2.get_rect(center=(cx, 96)))

        # Separador decorativo
        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER, (cx - 200, 118), (cx + 200, 118), 1)

        y_next = 142

        # Modo de juego
        self._label("MODO DE JUEGO", cx, y_next)
        self._btn_hvai.rect.y = y_next + 16
        self._btn_hvh.rect.y  = y_next + 16
        self._btn_hvai.selected = self._mode == GameMode.HUMAN_VS_AI
        self._btn_hvh.selected  = self._mode == GameMode.HUMAN_VS_HUMAN
        self._btn_hvai.draw(self.screen, self._btn_hvai.is_hovered(mp))
        self._btn_hvh.draw(self.screen,  self._btn_hvh.is_hovered(mp))

        y_next += 16 + 48 + 26  # Y para la siguiente sección (232)

        # Color (solo H vs IA)
        if self._mode == GameMode.HUMAN_VS_AI:
            self._label("JUGAR CON", cx, y_next)
            self._btn_white.rect.y = y_next + 16
            self._btn_black.rect.y = y_next + 16
            self._btn_white.selected = self._color == chess.WHITE
            self._btn_black.selected = self._color == chess.BLACK
            self._btn_white.draw(self.screen, self._btn_white.is_hovered(mp))
            self._btn_black.draw(self.screen, self._btn_black.is_hovered(mp))
            y_next += 16 + 42 + 26  # 316

        # Dificultad (solo H vs IA)
        if self._mode == GameMode.HUMAN_VS_AI:
            self._label("DIFICULTAD DE LA IA", cx, y_next)
            for i, btn in enumerate(self._btn_diffs):
                btn.rect.y = y_next + 16
                btn.selected = (i == self._diff_index)
                btn.draw(self.screen, btn.is_hovered(mp))
            y_next += 16 + 42 + 26  # 400

        # Indicador IA (para ambos modos: H vs IA y H vs H)
        self._label("INDICADOR DE IA (EVALUACIÓN Y FLECHA)", cx, y_next)
        self._btn_ind_on.rect.y  = y_next + 16
        self._btn_ind_off.rect.y = y_next + 16
        self._btn_ind_on.selected  = self._ai_indicator
        self._btn_ind_off.selected = not self._ai_indicator
        self._btn_ind_on.draw(self.screen, self._btn_ind_on.is_hovered(mp))
        self._btn_ind_off.draw(self.screen, self._btn_ind_off.is_hovered(mp))

        # Botón Jugar
        self._btn_play.rect.y = H - 115
        self._draw_play_btn(mp)

        # Estado Stockfish
        ok = self._sf_ok()
        sf_col  = (80, 200, 100) if ok else (200, 80, 80)
        sf_text = ("Stockfish detectado" if ok
                   else "Stockfish no encontrado — instala: sudo apt install stockfish")
        t = fm.small().render(sf_text, True, sf_col)
        self.screen.blit(t, t.get_rect(center=(cx, H - 32)))

    def _draw_play_btn(self, mp):
        r    = self._btn_play.rect
        hov  = r.collidepoint(mp)
        bg   = cfg.C_BTN_HOVER if hov else cfg.C_BTN
        pygame.draw.rect(self.screen, bg, r, border_radius=12)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, r, 2, border_radius=12)
        t = fm.large(bold=True).render("JUGAR", True, cfg.C_BTN_TEXT)
        self.screen.blit(t, t.get_rect(center=r.center))

    def _label(self, text: str, cx: int, y: int):
        t = fm.small(bold=True).render(text, True, cfg.C_TEXT_DIM)
        self.screen.blit(t, t.get_rect(center=(cx, y)))

    @staticmethod
    def _sf_ok() -> bool:
        from pathlib import Path
        return Path(cfg.STOCKFISH_PATH).is_file()
