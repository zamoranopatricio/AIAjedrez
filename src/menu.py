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
from src.position_import import (
    PositionImportError,
    import_position_from_clipboard,
    position_warnings,
    validate_initial_fen,
)


@dataclass
class MenuResult:
    mode: GameMode
    human_color: chess.Color
    difficulty_index: int
    show_ai_indicator: bool = True
    initial_fen: str | None = None


class _Button:
    def __init__(self, rect: pygame.Rect, text: str,
                 selected: bool = False, font: Optional[pygame.font.Font] = None):
        self.rect = rect
        self.text = text
        self.selected = selected
        self._font = font

    def draw(self, surface: pygame.Surface, hovered: bool, disabled: bool = False):
        if disabled:
            bg  = (35, 35, 48)
            bdr = (75, 75, 88)
        elif self.selected:
            bg  = cfg.C_SELECTED_BG
            bdr = cfg.C_SELECTED
        else:
            bg  = cfg.C_CARD_HOVER if hovered else cfg.C_CARD
            bdr = cfg.C_ACCENT if hovered else cfg.C_CARD_BORDER

        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, bdr, self.rect, 2, border_radius=10)

        font = self._font or fm.normal(bold=self.selected)
        t = font.render(self.text, True, cfg.C_TEXT_DIM if disabled else cfg.C_TEXT)
        surface.blit(t, t.get_rect(center=self.rect.center))

    def is_hovered(self, pos) -> bool:
        return self.rect.collidepoint(pos)


class MenuScreen:
    def __init__(self, screen: pygame.Surface, engine_available: bool = True):
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self.engine_available = engine_available

        # Sin motor, una partida local sigue siendo completamente jugable.
        self._mode         = GameMode.HUMAN_VS_AI if engine_available else GameMode.HUMAN_VS_HUMAN
        self._color        = chess.WHITE
        self._diff_index   = 2
        self._ai_indicator = True
        self._imported_placement: str | None = None
        self._import_warning = ""
        self._side_dialog_active = False
        self._status_message = "Pega una captura de un tablero verde/crema (Ctrl+V)."
        self._status_is_error = False

        self._build_buttons()

    # ── Loop ───────────────────────────────────────────────────────────────

    def run(self) -> MenuResult:
        while True:
            mp = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self._side_dialog_active:
                        self._side_dialog_active = False
                    else:
                        pygame.quit(); sys.exit()
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_v
                        and event.mod & pygame.KMOD_CTRL):
                    self._import_from_clipboard()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    r = self._handle_click(event.pos)
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
        self._btn_import = _Button(
            pygame.Rect(cx - 190, 224, 380, 42), "Pegar captura del tablero  (Ctrl+V)")

        self._btn_turn_white = _Button(pygame.Rect(cx - 150, 330, 140, 46), "Mueven Blancas")
        self._btn_turn_black = _Button(pygame.Rect(cx + 10, 330, 140, 46), "Mueven Negras")

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
        self._layout_buttons()

    def _layout_buttons(self):
        """Mantiene las zonas clicables sincronizadas con el modo visible."""
        H = cfg.WINDOW_HEIGHT
        y_next = 142

        self._btn_hvai.rect.y = y_next + 16
        self._btn_hvh.rect.y = y_next + 16
        self._btn_import.rect.y = y_next + 82
        y_next += 16 + 48 + 108

        if self._mode == GameMode.HUMAN_VS_AI:
            self._btn_white.rect.y = y_next + 16
            self._btn_black.rect.y = y_next + 16
            y_next += 16 + 42 + 26

            for btn in self._btn_diffs:
                btn.rect.y = y_next + 16
            y_next += 16 + 42 + 26

        self._btn_ind_on.rect.y = y_next + 16
        self._btn_ind_off.rect.y = y_next + 16
        self._btn_play.rect.y = H - 115
        self._sync_button_selection()

        if self._side_dialog_active:
            self._layout_turn_dialog()

    def _sync_button_selection(self):
        """Refleja el estado elegido incluso antes del siguiente renderizado."""
        self._btn_hvai.selected = (
            self._mode == GameMode.HUMAN_VS_AI and self.engine_available
        )
        self._btn_hvh.selected = self._mode == GameMode.HUMAN_VS_HUMAN
        self._btn_import.selected = self._initial_fen() is not None
        self._btn_white.selected = self._color == chess.WHITE
        self._btn_black.selected = self._color == chess.BLACK
        for i, btn in enumerate(self._btn_diffs):
            btn.selected = i == self._diff_index
        self._btn_ind_on.selected = self._ai_indicator
        self._btn_ind_off.selected = not self._ai_indicator

    def _layout_turn_dialog(self):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        card = pygame.Rect(W // 2 - 270, H // 2 - 105, 540, 210)
        self._btn_turn_white.rect.center = (card.centerx - 82, card.y + 147)
        self._btn_turn_black.rect.center = (card.centerx + 82, card.y + 147)

    # ── Clics ──────────────────────────────────────────────────────────────

    def _handle_click(self, pos) -> Optional[MenuResult]:
        # El modo puede haber cambiado desde el último frame: nunca evaluamos
        # clics contra la distribución anterior.
        self._layout_buttons()
        if self._side_dialog_active:
            if self._btn_turn_white.is_hovered(pos):
                self._select_imported_turn(chess.WHITE)
            elif self._btn_turn_black.is_hovered(pos):
                self._select_imported_turn(chess.BLACK)
            self._layout_buttons()
            return None

        if self._btn_import.is_hovered(pos):
            self._import_from_clipboard()
        elif self._btn_hvai.is_hovered(pos) and self.engine_available:
            self._mode = GameMode.HUMAN_VS_AI
        elif self._btn_hvh.is_hovered(pos):
            self._mode = GameMode.HUMAN_VS_HUMAN
        elif (self._mode == GameMode.HUMAN_VS_AI
              and self._btn_white.is_hovered(pos)):
            self._color = chess.WHITE
        elif (self._mode == GameMode.HUMAN_VS_AI
              and self._btn_black.is_hovered(pos)):
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
                initial_fen=self._initial_fen(),
            )
        elif self._mode == GameMode.HUMAN_VS_AI:
            for i, btn in enumerate(self._btn_diffs):
                if btn.is_hovered(pos):
                    self._diff_index = i
                    break
        self._layout_buttons()
        return None

    def _import_from_clipboard(self):
        # Una captura rechazada nunca debe dejar disponible una posición previa
        # por accidente: el botón JUGAR debe quedar bloqueado hasta importar una
        # posición nueva y válida.
        self._imported_placement = None
        self._import_warning = ""
        try:
            self._imported_placement = import_position_from_clipboard(cfg.ASSETS_DIR)
            self._import_warning = " ".join(position_warnings(self._imported_placement))
        except PositionImportError as exc:
            self._status_message = str(exc)
            self._status_is_error = True
            return
        except Exception:
            # La pantalla de menú debe permanecer utilizable incluso si el SO
            # bloquea temporalmente el portapapeles.
            self._status_message = "No se pudo importar la captura. Copia la imagen y vuelve a intentar."
            self._status_is_error = True
            return

        self._side_dialog_active = True
        self._status_is_error = False
        self._status_message = "Captura detectada. ¿Quién mueve primero?"

    def _select_imported_turn(self, turn: chess.Color):
        if self._imported_placement is None:
            return
        side = "Blancas" if turn == chess.WHITE else "Negras"
        placement = self._imported_placement.rsplit(" ", 1)[0]
        selected_turn = "w" if turn == chess.WHITE else "b"
        try:
            validate_initial_fen(f"{placement} {selected_turn} - - 0 1")
        except PositionImportError as exc:
            self._imported_placement = placement
            self._status_message = str(exc)
            self._status_is_error = True
            return
        self._imported_placement = f"{placement} {selected_turn}"
        self._side_dialog_active = False
        self._status_is_error = False
        self._status_message = f"Posición importada. Mueven {side}. Presiona JUGAR para comenzar."
        if self._import_warning:
            self._status_message += f" Aviso: {self._import_warning}"

    def _initial_fen(self) -> str | None:
        if self._imported_placement is None:
            return None
        # Antes de elegir el turno solo se guarda placement; por tanto nunca
        # se inicia una partida importada sin responder la pregunta explícita.
        if self._imported_placement.endswith((" w", " b")):
            return self._imported_placement + " - - 0 1"
        return None

    # ── Render ─────────────────────────────────────────────────────────────

    def _draw(self, mp):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        cx = W // 2
        self._layout_buttons()
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
        self._btn_hvai.draw(
            self.screen, self._btn_hvai.is_hovered(mp), disabled=not self.engine_available
        )
        self._btn_hvh.draw(self.screen,  self._btn_hvh.is_hovered(mp))

        self._btn_import.draw(self.screen, self._btn_import.is_hovered(mp))
        status = fm.small().render(
            self._status_message, True,
            (230, 115, 115) if self._status_is_error else cfg.C_TEXT_DIM,
        )
        self.screen.blit(status, status.get_rect(center=(cx, y_next + 136)))

        y_next += 16 + 48 + 108  # reserva para importar captura y estado

        # Color (solo H vs IA)
        if self._mode == GameMode.HUMAN_VS_AI:
            self._label("JUGAR CON", cx, y_next)
            self._btn_white.draw(self.screen, self._btn_white.is_hovered(mp))
            self._btn_black.draw(self.screen, self._btn_black.is_hovered(mp))
            y_next += 16 + 42 + 26  # 316

        # Dificultad (solo H vs IA)
        if self._mode == GameMode.HUMAN_VS_AI:
            self._label("DIFICULTAD DE LA IA", cx, y_next)
            for i, btn in enumerate(self._btn_diffs):
                btn.draw(self.screen, btn.is_hovered(mp))
            y_next += 16 + 42 + 26  # 400

        # Indicador IA (para ambos modos: H vs IA y H vs H)
        self._label("INDICADOR DE IA (EVALUACIÓN Y FLECHA)", cx, y_next)
        self._btn_ind_on.draw(self.screen, self._btn_ind_on.is_hovered(mp))
        self._btn_ind_off.draw(self.screen, self._btn_ind_off.is_hovered(mp))

        # Botón Jugar
        self._draw_play_btn(mp)

        # Estado Stockfish. El modo local sigue disponible aunque no esté instalado.
        ok = self.engine_available
        sf_col  = (80, 200, 100) if ok else (230, 185, 90)
        sf_text = ("Stockfish detectado" if ok
                   else "Sin Stockfish: puedes jugar Humano vs Humano. Consulta el README para instalarlo.")
        t = fm.small().render(sf_text, True, sf_col)
        self.screen.blit(t, t.get_rect(center=(cx, H - 32)))

        if self._side_dialog_active:
            self._draw_turn_dialog(mp)

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

    def _draw_turn_dialog(self, mp):
        """Pregunta necesaria porque el turno no se puede leer de una imagen."""
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        self._layout_turn_dialog()
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        card = pygame.Rect(W // 2 - 270, H // 2 - 105, 540, 210)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BG, card, border_radius=14)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, card, 2, border_radius=14)
        title = fm.large(bold=True).render("¿Quién mueve?", True, cfg.C_TEXT)
        self.screen.blit(title, title.get_rect(center=(card.centerx, card.y + 48)))
        help_text = fm.normal().render("La captura no contiene información del turno.", True, cfg.C_TEXT_DIM)
        self.screen.blit(help_text, help_text.get_rect(center=(card.centerx, card.y + 82)))
        self._btn_turn_white.draw(self.screen, self._btn_turn_white.is_hovered(mp))
        self._btn_turn_black.draw(self.screen, self._btn_turn_black.is_hovered(mp))
