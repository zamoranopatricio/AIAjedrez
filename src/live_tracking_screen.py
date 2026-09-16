"""Pantalla de seguimiento local de un tablero visible en otra aplicación."""
from __future__ import annotations

import sys
import time

import chess
import pygame
from PIL import ImageGrab

import config as cfg
from src import font_manager as fm
from src.board_gui import BoardGUI
from src.game_state import GameMode, GameState
from src.position_import import PositionImportError, validate_initial_fen
from src.screen_monitor import MonitorResult, ScreenRegionMonitor, selection_to_desktop_bbox
from src.screenshot_tracking import ScreenshotTracker


class LiveTrackingScreen:
    """Registra jugadas detectadas, sin enviar entradas a la app observada."""

    POLL_SECONDS = 1.0

    def __init__(
        self,
        screen: pygame.Surface,
        piece_images: dict,
        initial_fen: str | None,
        *,
        white_bottom: bool,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self._needs_initial_position = initial_fen is None
        self._initial_turn: chess.Color = chess.WHITE
        self._orientation_confirmed = initial_fen is not None
        self._turn_confirmed = initial_fen is not None
        # Mientras se configura, el tablero solo es una vista provisional: no acepta clics.
        self.state = GameState(mode=GameMode.HUMAN_VS_HUMAN, initial_fen=initial_fen)
        self.gui = BoardGUI(screen, piece_images, flipped=not white_bottom)
        self.monitor = ScreenRegionMonitor(
            ScreenshotTracker(self.state), cfg.ASSETS_DIR, white_bottom=white_bottom
        )
        self.status_message = "Selecciona una zona del escritorio y comienza el monitor."
        self.status_is_error = False
        self._next_poll = 0.0
        self._selection_image = None
        self._selection_surface: pygame.Surface | None = None
        self._selection_preview = pygame.Rect(0, 0, 0, 0)
        self._selection_start: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        self._selection_active = False
        self._build_buttons()

    def _build_buttons(self) -> None:
        px, py, pw, ph = cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_WIDTH, cfg.PANEL_HEIGHT
        pad, gap = 12, 8
        width = pw - pad * 2
        y = py + ph - 218
        self.btn_select = pygame.Rect(px + pad, y, width, 36)
        self.btn_monitor = pygame.Rect(px + pad, y + 44, width, 36)
        self.btn_flip = pygame.Rect(px + pad, y + 88, width, 32)
        half = (width - gap) // 2
        self.btn_reset = pygame.Rect(px + pad, y + 128, half, 32)
        self.btn_menu = pygame.Rect(px + pad + half + gap, y + 128, half, 32)
        self.btn_orientation_white = pygame.Rect(px + pad, py + 122, half, 30)
        self.btn_orientation_black = pygame.Rect(px + pad + half + gap, py + 122, half, 30)
        self.btn_turn_white = pygame.Rect(px + pad, py + 160, half, 30)
        self.btn_turn_black = pygame.Rect(px + pad + half + gap, py + 160, half, 30)

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if self._handle_event(event) == "menu":
                    return

            if self.monitor.active and not self._selection_active and time.monotonic() >= self._next_poll:
                self._next_poll = time.monotonic() + self.POLL_SECONDS
                self._on_monitor_result(self.monitor.poll())

            self._draw(pygame.mouse.get_pos())
            pygame.display.flip()
            self.clock.tick(cfg.FPS)

    def _handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                if self._selection_active:
                    self._cancel_selection()
                    return None
                return "menu"
            if event.key == pygame.K_SPACE:
                self._toggle_monitor()
                return None

        if self._selection_active:
            self._handle_selection_event(event)
            return None

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        if self._needs_initial_position and self.btn_orientation_white.collidepoint(event.pos):
            self.monitor.white_bottom = True
            self._orientation_confirmed = True
            self.status_message = "Orientación seleccionada: blancas abajo (a1)."
            self.status_is_error = False
        elif self._needs_initial_position and self.btn_orientation_black.collidepoint(event.pos):
            self.monitor.white_bottom = False
            self._orientation_confirmed = True
            self.status_message = "Orientación seleccionada: negras abajo (h8)."
            self.status_is_error = False
        elif self._needs_initial_position and self.btn_turn_white.collidepoint(event.pos):
            self._initial_turn = chess.WHITE
            self._turn_confirmed = True
            self.status_message = "Turno inicial seleccionado: blancas."
            self.status_is_error = False
        elif self._needs_initial_position and self.btn_turn_black.collidepoint(event.pos):
            self._initial_turn = chess.BLACK
            self._turn_confirmed = True
            self.status_message = "Turno inicial seleccionado: negras."
            self.status_is_error = False
        elif self.btn_select.collidepoint(event.pos):
            self._request_region_selection()
        elif self.btn_monitor.collidepoint(event.pos):
            self._toggle_monitor()
        elif self.btn_flip.collidepoint(event.pos):
            self.gui.flipped = not self.gui.flipped
        elif self.btn_reset.collidepoint(event.pos):
            self.state.reset()
            self.status_message = "Registro reiniciado; el monitor seguirá comparando desde la captura inicial."
            self.status_is_error = False
        elif self.btn_menu.collidepoint(event.pos):
            self.monitor.stop()
            return "menu"
        # Los clics sobre el tablero se ignoran deliberadamente: este modo solo observa.
        return None

    def _toggle_monitor(self) -> None:
        if self.monitor.active:
            self.monitor.stop()
            self.status_message = "Monitor detenido. No se leerán más capturas hasta iniciarlo otra vez."
            self.status_is_error = False
            return
        if self._needs_initial_position and not self._read_initial_position():
            return
        try:
            self.monitor.start()
        except ValueError as exc:
            self.status_message = str(exc)
            self.status_is_error = True
            return
        self._next_poll = 0.0
        self.status_message = "Monitor activo: se lee únicamente la zona elegida, una vez por segundo."
        self.status_is_error = False

    def _read_initial_position(self) -> bool:
        if not self._orientation_confirmed or not self._turn_confirmed:
            self.status_message = "Antes de iniciar, confirma orientación y quién mueve en la captura inicial."
            self.status_is_error = True
            return False
        try:
            placement = self.monitor.read_current_placement()
            side = "w" if self._initial_turn == chess.WHITE else "b"
            initial_fen = f"{placement} {side} - - 0 1"
            validate_initial_fen(initial_fen)
        except (PositionImportError, ValueError) as exc:
            self.status_message = str(exc)
            self.status_is_error = True
            return False
        except Exception:
            self.status_message = "No se pudo leer la captura inicial. Verifica que la zona muestre el tablero completo."
            self.status_is_error = True
            return False
        self.state = GameState(mode=GameMode.HUMAN_VS_HUMAN, initial_fen=initial_fen)
        self.monitor.tracker = ScreenshotTracker(self.state)
        self._needs_initial_position = False
        return True

    def _on_monitor_result(self, result: MonitorResult) -> None:
        # Se comunica cada frame inválido o válido; un frame idéntico no altera el historial.
        self.status_message = result.message
        self.status_is_error = not result.accepted and "sin cambios" not in result.message.lower()

    def _request_region_selection(self) -> None:
        """Oculta brevemente la app para fotografiar el escritorio, sin automatizarlo."""
        self.monitor.stop()
        self.status_message = "Preparando una imagen del escritorio para elegir el tablero…"
        self._draw(pygame.mouse.get_pos())
        pygame.display.flip()
        try:
            pygame.display.iconify()
            time.sleep(0.8)
            image = ImageGrab.grab().convert("RGB")
            # Volver a crear la superficie restaura la ventana en plataformas Pygame comunes.
            self.screen = pygame.display.set_mode((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        except Exception:
            self.status_message = "No se pudo capturar el escritorio. Este modo necesita permisos de captura de pantalla."
            self.status_is_error = True
            return

        self._selection_image = image
        self._selection_surface = pygame.image.fromstring(image.tobytes(), image.size, "RGB")
        scale = min((cfg.WINDOW_WIDTH - 80) / image.width, (cfg.WINDOW_HEIGHT - 120) / image.height)
        preview_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        self._selection_surface = pygame.transform.smoothscale(self._selection_surface, preview_size)
        self._selection_preview = self._selection_surface.get_rect(center=(cfg.WINDOW_WIDTH // 2, cfg.WINDOW_HEIGHT // 2 + 20))
        self._selection_start = None
        self._selection_end = None
        self._selection_active = True
        self.status_message = "Arrastra exactamente sobre las 64 casillas del tablero y suelta para confirmar."
        self.status_is_error = False

    def _handle_selection_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._selection_preview.collidepoint(event.pos):
                self._selection_start = event.pos
                self._selection_end = event.pos
            return
        if event.type == pygame.MOUSEMOTION and self._selection_start is not None:
            self._selection_end = event.pos
            return
        if event.type != pygame.MOUSEBUTTONUP or event.button != 1 or self._selection_start is None:
            return
        self._selection_end = event.pos
        bbox = selection_to_desktop_bbox(
            (*self._selection_start, *self._selection_end),
            tuple(self._selection_preview),
            self._selection_image.size,
        )
        left, top, right, bottom = bbox
        width, height = right - left, bottom - top
        if min(width, height) < 192 or abs(width - height) > max(width, height) * 0.12:
            self.status_message = "La zona debe incluir un tablero completo, casi cuadrado y de al menos 192 píxeles. Intenta otra vez."
            self.status_is_error = True
            self._selection_start = None
            self._selection_end = None
            return
        self.monitor.set_region(bbox)
        self._selection_active = False
        self.status_message = "Zona seleccionada. Presiona INICIAR MONITOR para registrar jugadas."
        self.status_is_error = False

    def _cancel_selection(self) -> None:
        self._selection_active = False
        self._selection_start = None
        self._selection_end = None
        self.status_message = "Selección cancelada."
        self.status_is_error = False

    def _draw(self, mouse_pos: tuple[int, int]) -> None:
        self.gui.draw(
            board=self.state.board,
            selected_square=None,
            legal_targets=[],
            last_move=self.state.last_move,
            best_move=None,
            score=None,
            dragging_piece=None,
            drag_pos=(0, 0),
            san_history=self.state.san_history,
            mode_label="Seguimiento de capturas",
            engine_available=False,
            show_ai_indicator=False,
            mouse_pos=mouse_pos,
        )
        self._draw_tracking_panel(mouse_pos)
        if self._selection_active:
            self._draw_selection_overlay()

    def _draw_tracking_panel(self, mouse_pos: tuple[int, int]) -> None:
        px, py, pw, ph = cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_WIDTH, cfg.PANEL_HEIGHT
        pygame.draw.rect(self.screen, cfg.C_PANEL_BG, (px, py, pw, ph), border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, (px, py, pw, ph), 1, border_radius=8)
        x, y, pad = px + 12, py + 18, 12
        title = fm.small(bold=True).render("SEGUIMIENTO EN VIVO", True, cfg.C_TEXT_DIM)
        self.screen.blit(title, (x, y)); y += 24
        subtitle = fm.normal().render("Solo registra; no juega ni recomienda.", True, cfg.C_TEXT_ACCENT)
        self.screen.blit(subtitle, (x, y)); y += 34
        if self._needs_initial_position:
            guide = fm.small(bold=True).render("CAPTURA INICIAL", True, cfg.C_TEXT_DIM)
            self.screen.blit(guide, (x, y)); y += 22
            self._button(self.btn_orientation_white, "Blancas abajo", mouse_pos, (45, 90, 150),
                         selected=self.monitor.white_bottom and self._orientation_confirmed)
            self._button(self.btn_orientation_black, "Negras abajo", mouse_pos, (45, 90, 150),
                         selected=not self.monitor.white_bottom and self._orientation_confirmed)
            self._button(self.btn_turn_white, "Mueven blancas", mouse_pos, (45, 90, 150),
                         selected=self._initial_turn == chess.WHITE and self._turn_confirmed)
            self._button(self.btn_turn_black, "Mueven negras", mouse_pos, (45, 90, 150),
                         selected=self._initial_turn == chess.BLACK and self._turn_confirmed)
            y = py + 205
        state = "ACTIVO" if self.monitor.active else "DETENIDO"
        col = (80, 200, 100) if self.monitor.active else cfg.C_TEXT_DIM
        text = fm.normal(bold=True).render(f"Monitor: {state}", True, col)
        self.screen.blit(text, (x, y)); y += 30
        y = self._draw_wrapped(self.status_message, x, y, pw - pad * 2,
                               (230, 115, 115) if self.status_is_error else cfg.C_TEXT_DIM)
        y += 14
        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER, (x, y), (px + pw - pad, y)); y += 12
        label = fm.small(bold=True).render("JUGADAS DETECTADAS", True, cfg.C_TEXT_DIM)
        self.screen.blit(label, (x, y)); y += 22
        max_lines = 9
        for pair in range(max(0, (len(self.state.san_history) + 1) // 2 - max_lines), (len(self.state.san_history) + 1) // 2):
            i = pair * 2
            white = self.state.san_history[i] if i < len(self.state.san_history) else ""
            black = self.state.san_history[i + 1] if i + 1 < len(self.state.san_history) else ""
            text = fm.normal().render(f"{pair + 1:>3}. {white:<10} {black}", True, cfg.C_TEXT)
            self.screen.blit(text, (x, y)); y += 19

        self._button(self.btn_select, "Seleccionar zona de pantalla", mouse_pos, cfg.C_BTN)
        monitor_label = "Detener monitor" if self.monitor.active else "Iniciar monitor"
        self._button(self.btn_monitor, monitor_label, mouse_pos, (35, 110, 60))
        self._button(self.btn_flip, "Voltear vista", mouse_pos, (45, 90, 150))
        self._button(self.btn_reset, "Reiniciar", mouse_pos, (100, 50, 50))
        self._button(self.btn_menu, "Menú", mouse_pos, (70, 50, 100))

    def _button(self, rect: pygame.Rect, label: str, mouse_pos: tuple[int, int], color: tuple[int, int, int], *, selected: bool = False) -> None:
        draw_color = tuple(min(255, c + 35) for c in color) if rect.collidepoint(mouse_pos) else color
        if selected:
            draw_color = tuple(min(255, c + 45) for c in color)
        pygame.draw.rect(self.screen, draw_color, rect, border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, rect, 1, border_radius=8)
        text = fm.small(bold=True).render(label, True, cfg.C_BTN_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_wrapped(self, text: str, x: int, y: int, width: int, color) -> int:
        font = fm.small()
        line = ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and font.size(trial)[0] > width:
                self.screen.blit(font.render(line, True, color), (x, y))
                y += font.get_linesize()
                line = word
            else:
                line = trial
        if line:
            self.screen.blit(font.render(line, True, color), (x, y))
            y += font.get_linesize()
        return y

    def _draw_selection_overlay(self) -> None:
        overlay = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        self.screen.blit(overlay, (0, 0))
        assert self._selection_surface is not None
        self.screen.blit(self._selection_surface, self._selection_preview)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, self._selection_preview, 2)
        title = fm.normal(bold=True).render("Arrastra sobre las 64 casillas del tablero", True, cfg.C_TEXT)
        self.screen.blit(title, title.get_rect(center=(cfg.WINDOW_WIDTH // 2, 28)))
        if self._selection_start and self._selection_end:
            rect = pygame.Rect(*self._selection_start, 0, 0).union(pygame.Rect(*self._selection_end, 0, 0))
            pygame.draw.rect(self.screen, (100, 180, 255), rect, 3)
