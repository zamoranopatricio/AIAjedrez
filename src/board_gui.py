"""
src/board_gui.py
Renderizado completo del tablero, piezas, highlights, flecha IA y barra de evaluación.
"""
import math
import pygame
import chess
from typing import Optional

import config as cfg
from src import font_manager as fm


# ── Helpers de coordenadas ─────────────────────────────────────────────────

def square_to_pixel(square: int, flipped: bool = False) -> tuple[int, int]:
    """Centro en píxeles de la casilla dada."""
    col = chess.square_file(square)
    row = chess.square_rank(square)
    if flipped:
        col = 7 - col
        row = 7 - row
    x = cfg.BOARD_OFFSET_X + col * cfg.SQUARE_SIZE + cfg.SQUARE_SIZE // 2
    y = cfg.BOARD_OFFSET_Y + (7 - row) * cfg.SQUARE_SIZE + cfg.SQUARE_SIZE // 2
    return x, y


def square_to_rect(square: int, flipped: bool = False) -> pygame.Rect:
    col = chess.square_file(square)
    row = chess.square_rank(square)
    if flipped:
        col = 7 - col
        row = 7 - row
    x = cfg.BOARD_OFFSET_X + col * cfg.SQUARE_SIZE
    y = cfg.BOARD_OFFSET_Y + (7 - row) * cfg.SQUARE_SIZE
    return pygame.Rect(x, y, cfg.SQUARE_SIZE, cfg.SQUARE_SIZE)


def pixel_to_square(px: int, py: int, flipped: bool = False) -> Optional[int]:
    """Convierte coordenadas de pantalla a número de casilla (0-63), o None."""
    col = (px - cfg.BOARD_OFFSET_X) // cfg.SQUARE_SIZE
    row = (py - cfg.BOARD_OFFSET_Y) // cfg.SQUARE_SIZE
    if not (0 <= col <= 7 and 0 <= row <= 7):
        return None
    file_ = 7 - col if flipped else col
    rank_ = row if flipped else 7 - row
    return chess.square(file_, rank_)


# ── Dibujo de flecha ────────────────────────────────────────────────────────

def _draw_arrow(
    surface: pygame.Surface,
    start: tuple,
    end: tuple,
    fill_color=None,
    outline_color=None,
):
    """
    Dibuja una flecha vectorizada elegante de 7 vértices estilo Lichess/Chess.com.
    Combina un cuerpo rectilíneo con una punta triangular afilada y borde sutil.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    ux, uy = dx / length, dy / length
    px, py = -uy, ux   # Vector perpendicular (rotación de 90°)

    sq = cfg.SQUARE_SIZE
    pad_start   = sq * 0.24
    pad_end     = sq * 0.16
    head_length = sq * 0.38
    stem_width  = sq * 0.18
    head_width  = sq * 0.42

    sx = start[0] + ux * pad_start
    sy = start[1] + uy * pad_start

    tip_x = end[0] - ux * pad_end
    tip_y = end[1] - uy * pad_end

    base_x = tip_x - ux * head_length
    base_y = tip_y - uy * head_length

    # 7 vértices del polígono estilizado
    pts = [
        (sx + px * (stem_width / 2), sy + py * (stem_width / 2)),
        (base_x + px * (stem_width / 2), base_y + py * (stem_width / 2)),
        (base_x + px * (head_width / 2), base_y + py * (head_width / 2)),
        (tip_x, tip_y),
        (base_x - px * (head_width / 2), base_y - py * (head_width / 2)),
        (base_x - px * (stem_width / 2), base_y - py * (stem_width / 2)),
        (sx - px * (stem_width / 2), sy - py * (stem_width / 2)),
    ]

    fill_col    = fill_color or getattr(cfg, "C_ARROW_FILL", (255, 170, 0, 200))
    outline_col = outline_color or getattr(cfg, "C_ARROW_OUTLINE", (180, 90, 0, 255))

    int_pts = [(int(x), int(y)) for x, y in pts]

    # Dibujar relleno poligonal + contorno afilado sin solapamiento
    pygame.draw.polygon(surface, fill_col, int_pts)
    pygame.draw.polygon(surface, outline_col, int_pts, width=2)


# ── Clase principal ────────────────────────────────────────────────────────

class BoardGUI:
    """
    Gestiona todo el renderizado del tablero y la interacción de usuario.

    Parámetros:
        screen      : pygame.Surface principal
        piece_images: dict { chess.Piece → pygame.Surface }
        flipped     : True para mostrar tablero con negras abajo
    """

    def __init__(
        self,
        screen: pygame.Surface,
        piece_images: dict,
        flipped: bool = False,
        visual_theme: str = cfg.VISUAL_THEME_CHESS_COM,
    ):
        self.screen = screen
        self.piece_images = piece_images
        self.flipped = flipped
        self.visual_theme = cfg.normalize_visual_theme(visual_theme)

        pygame.font.init()
        # Rects de botones de acción (actualizados en cada frame)
        self.flip_btn_rect        : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_toggle_indicator : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_toggle_blue_arrow: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_toggle_test_mode : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_history_previous  : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_history_next      : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_history_live      : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        # Índice de jugada (1-based) -> rect clickeable del historial visible.
        self.history_move_rects: dict[int, pygame.Rect] = {}
        self.btn_undo             : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_save             : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_restart          : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_analysis         : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_menu             : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        # Botones del overlay de fin de partida
        self.go_btn_restart       : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.go_btn_analysis      : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.go_btn_menu          : pygame.Rect = pygame.Rect(0, 0, 0, 0)

        # Superficie con alpha del tamaño completo de la ventana.
        # Se blitta en (0, 0) para que los rects en coordenadas de pantalla
        # coincidan exactamente sin doble offset.
        self._alpha_surf = pygame.Surface(
            (cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA
        )

    # ── Render principal ───────────────────────────────────────────────────

    def draw(
        self,
        board: chess.Board,
        selected_square: Optional[int],
        legal_targets: list[int],
        last_move: Optional[chess.Move],
        best_move: Optional[chess.Move],
        score,                          # chess.engine.Score | None
        dragging_piece: Optional[chess.Piece],
        drag_pos: tuple[int, int],
        san_history: list[str],
        mode_label: str,
        engine_available: bool,
        show_ai_indicator: bool = True,
        alternative_move: Optional[chess.Move] = None,
        show_blue_arrow_toggle: bool = False,
        blue_arrow_enabled: bool = False,
        show_test_mode_toggle: bool = False,
        test_mode_enabled: bool = False,
        mouse_pos: tuple[int, int] = (0, 0),
        evaluation_samples: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
        opening_label: str | None = None,
        history_index: int | None = None,
        history_position_count: int | None = None,
    ):
        self.screen.fill(cfg.C_BG)
        self._draw_board_squares(board, selected_square, legal_targets, last_move)
        if show_ai_indicator:
            self._draw_arrow_overlay(best_move, alternative_move)
        self._draw_pieces(board, selected_square if dragging_piece else None, dragging_piece, drag_pos)
        self._draw_coordinates()
        self._draw_eval_bar(score, board, show_ai_indicator)
        self._draw_side_panel(
            board, san_history, mode_label, engine_available, score,
            show_ai_indicator, show_blue_arrow_toggle, blue_arrow_enabled,
            show_test_mode_toggle, test_mode_enabled, mouse_pos,
            evaluation_samples, opening_label, history_index, history_position_count,
        )

    def draw_game_over(self, result_text: str, mouse_pos: tuple = (0, 0), summary=None):
        """Overlay semitransparente de fin de partida con botones clickeables."""
        overlay = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 520, (310 if summary and summary.reviews else 230)
        bx = (cfg.WINDOW_WIDTH  - box_w) // 2
        by = (cfg.WINDOW_HEIGHT - box_h) // 2
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box_surf.fill((22, 22, 45, 245))
        pygame.draw.rect(box_surf, cfg.C_ACCENT, (0, 0, box_w, box_h), 2, border_radius=16)
        self.screen.blit(box_surf, (bx, by))

        cx = cfg.WINDOW_WIDTH // 2
        t1 = fm.title().render("Partida Terminada", True, cfg.C_TEXT)
        self.screen.blit(t1, t1.get_rect(center=(cx, by + 50)))
        t2 = fm.medium().render(result_text, True, cfg.C_TEXT_ACCENT)
        self.screen.blit(t2, t2.get_rect(center=(cx, by + 92)))

        if summary and summary.reviews:
            counts = (f"Mejores: {len(summary.best_moves)}   Buenas: {len(summary.good_moves)}   "
                      f"Errores: {len(summary.errors)}   Blunders: {len(summary.blunders)}")
            info = fm.small(bold=True).render("RESUMEN DE ANÁLISIS", True, cfg.C_TEXT_DIM)
            self.screen.blit(info, info.get_rect(center=(cx, by + 124)))
            text = fm.small().render(counts, True, cfg.C_TEXT)
            self.screen.blit(text, text.get_rect(center=(cx, by + 147)))
            noteworthy = (summary.blunders or summary.errors or summary.best_moves or summary.good_moves)[0]
            detail = fm.small().render(f"{noteworthy.san}: {noteworthy.explanation}", True, cfg.C_TEXT_ACCENT)
            self.screen.blit(detail, detail.get_rect(center=(cx, by + 171)))

        # Tres botones de acción
        bw, bh = 148, 40
        gap = 12
        total_w = bw * 3 + gap * 2
        bx0 = cx - total_w // 2
        btn_y = by + box_h - 68

        self.go_btn_restart  = pygame.Rect(bx0,              btn_y, bw, bh)
        self.go_btn_analysis = pygame.Rect(bx0 + bw + gap,   btn_y, bw, bh)
        self.go_btn_menu     = pygame.Rect(bx0 + (bw+gap)*2, btn_y, bw, bh)

        labels = [
            (self.go_btn_restart,  "Reiniciar",  cfg.C_BTN),
            (self.go_btn_analysis, "Analisis",   (40, 120, 80)),
            (self.go_btn_menu,     "Menu",        (70, 60, 100)),
        ]
        for rect, label, base_col in labels:
            hov = rect.collidepoint(mouse_pos)
            col = tuple(min(255, c + 35) for c in base_col) if hov else base_col
            pygame.draw.rect(self.screen, col, rect, border_radius=10)
            pygame.draw.rect(self.screen, cfg.C_ACCENT, rect, 1, border_radius=10)
            t = fm.normal(bold=True).render(label, True, cfg.C_BTN_TEXT)
            self.screen.blit(t, t.get_rect(center=rect.center))

    # ── Tablero ────────────────────────────────────────────────────────────

    def _draw_board_squares(
        self,
        board: chess.Board,
        selected: Optional[int],
        legal_targets: list[int],
        last_move: Optional[chess.Move],
    ):
        self._alpha_surf.fill((0, 0, 0, 0))
        light_sq, dark_sq = cfg.board_palette(self.visual_theme)

        for sq in range(64):
            rect = square_to_rect(sq, self.flipped)
            col  = chess.square_file(sq)
            row  = chess.square_rank(sq)
            # En un tablero reglamentario a1 es oscuro. El color pertenece a
            # la casilla lógica; square_to_rect se encarga de rotarla cuando
            # se muestra la vista de negras.
            light = (col + row) % 2 == 1

            # Color base de la casilla
            base = light_sq if light else dark_sq
            pygame.draw.rect(self.screen, base, rect)

        # Último movimiento
        if last_move:
            for sq in (last_move.from_square, last_move.to_square):
                pygame.draw.rect(self._alpha_surf, cfg.C_LAST_MOVE, square_to_rect(sq, self.flipped))

        # Rey en jaque
        if board.is_check():
            king_sq = board.king(board.turn)
            if king_sq is not None:
                pygame.draw.rect(self._alpha_surf, cfg.C_CHECK, square_to_rect(king_sq, self.flipped))

        # Casilla seleccionada
        if selected is not None:
            pygame.draw.rect(self._alpha_surf, cfg.C_HIGHLIGHT_SEL, square_to_rect(selected, self.flipped))

        # Movimientos legales (puntos o highlight)
        for sq in legal_targets:
            rect = square_to_rect(sq, self.flipped)
            if board.piece_at(sq):  # captura
                border_r = pygame.Rect(rect.x, rect.y, rect.w, rect.h)
                pygame.draw.rect(self._alpha_surf, cfg.C_HIGHLIGHT_SEL, border_r, 6)
            else:
                cx, cy = rect.centerx, rect.centery
                r = cfg.SQUARE_SIZE // 6
                dot_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(dot_surf, cfg.C_HIGHLIGHT_LEGAL, (r, r), r)
                self._alpha_surf.blit(dot_surf, (cx - r, cy - r))

        self.screen.blit(self._alpha_surf, (0, 0))

        # Borde del tablero
        board_rect = pygame.Rect(
            cfg.BOARD_OFFSET_X, cfg.BOARD_OFFSET_Y, cfg.BOARD_SIZE, cfg.BOARD_SIZE
        )
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, board_rect, 2)

    # ── Piezas ────────────────────────────────────────────────────────────

    def _draw_pieces(
        self,
        board: chess.Board,
        skip_square: Optional[int],   # casilla a omitir (pieza siendo arrastrada)
        dragging_piece: Optional[chess.Piece],
        drag_pos: tuple[int, int],
    ):
        for sq in range(64):
            if sq == skip_square and dragging_piece:
                continue
            piece = board.piece_at(sq)
            if piece and piece in self.piece_images:
                rect = square_to_rect(sq, self.flipped)
                self.screen.blit(self.piece_images[piece], rect.topleft)

        # Dibujar pieza arrastrada encima de todo
        if dragging_piece and dragging_piece in self.piece_images:
            img = self.piece_images[dragging_piece]
            r = img.get_rect(center=drag_pos)
            self.screen.blit(img, r)

    # ── Flecha de sugerencia ───────────────────────────────────────────────

    def _draw_arrow_overlay(
        self,
        best_move: Optional[chess.Move],
        alternative_move: Optional[chess.Move] = None,
    ):
        if best_move is None and alternative_move is None:
            return

        # Dibujar sobre superficie con alpha
        arrow_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        if alternative_move is not None and alternative_move != best_move:
            alt_start = square_to_pixel(alternative_move.from_square, self.flipped)
            alt_end = square_to_pixel(alternative_move.to_square, self.flipped)
            _draw_arrow(arrow_surf, alt_start, alt_end, cfg.C_ALT_ARROW_FILL, cfg.C_ALT_ARROW_OUTLINE)
        if best_move is not None:
            start = square_to_pixel(best_move.from_square, self.flipped)
            end = square_to_pixel(best_move.to_square, self.flipped)
            _draw_arrow(arrow_surf, start, end, cfg.C_ARROW_FILL, cfg.C_ARROW_OUTLINE)
        self.screen.blit(arrow_surf, (0, 0))

    # ── Coordenadas ────────────────────────────────────────────────────────

    def _draw_coordinates(self):
        """Dibuja las coordenadas dentro de las esquinas, como en Chess.com."""
        light_sq, dark_sq = cfg.board_palette(self.visual_theme)
        for screen_row in range(8):
            rank = screen_row if self.flipped else 7 - screen_row
            square = chess.square(7 if self.flipped else 0, rank)
            rect = square_to_rect(square, self.flipped)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = dark_sq if light else light_sq
            label = fm.small(bold=True).render(str(rank + 1), True, color)
            self.screen.blit(label, (rect.x + 4, rect.y + 2))

        for screen_col in range(8):
            file_ = 7 - screen_col if self.flipped else screen_col
            square = chess.square(file_, 7 if self.flipped else 0)
            rect = square_to_rect(square, self.flipped)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = dark_sq if light else light_sq
            label = fm.small(bold=True).render(chess.FILE_NAMES[file_], True, color)
            self.screen.blit(label, label.get_rect(bottomright=(rect.right - 4, rect.bottom - 2)))

    # ── Barra de evaluación ────────────────────────────────────────────────

    def _draw_eval_bar(self, score, board: chess.Board, show_ai_indicator: bool = True):
        bx = cfg.EVAL_BAR_X
        by = cfg.EVAL_BAR_Y
        bw = cfg.EVAL_BAR_WIDTH
        bh = cfg.EVAL_BAR_HEIGHT

        # Fondo
        pygame.draw.rect(self.screen, cfg.C_EVAL_BLACK, (bx, by, bw, bh))

        if not show_ai_indicator:
            # Indicador oculto: barra neutra
            pygame.draw.rect(self.screen, (50, 50, 70), (bx, by, bw, bh))
            pygame.draw.rect(self.screen, cfg.C_EVAL_BORDER, (bx, by, bw, bh), 1)
            t = fm.small().render("OFF", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, t.get_rect(center=(bx + bw // 2, by + bh + 14)))
            return

        # Calcular fracción blanca [0.0, 1.0]
        white_frac = 0.5
        score_str  = "0.00"

        if score is not None:
            try:
                if score.is_mate():
                    m = score.mate()
                    white_frac = 1.0 if m > 0 else 0.0
                    score_str  = f"M{abs(m)}" if m > 0 else f"-M{abs(m)}"
                else:
                    cp = score.score()
                    white_frac = 1 / (1 + math.exp(-cp / 200))
                    score_str  = f"{cp/100:+.2f}"
            except Exception:
                pass

        white_h = int(bh * white_frac)
        black_h = bh - white_h

        # Blanco abajo, negro arriba (convención visual)
        pygame.draw.rect(self.screen, cfg.C_EVAL_BLACK, (bx, by, bw, black_h))
        pygame.draw.rect(self.screen, cfg.C_EVAL_WHITE, (bx, by + black_h, bw, white_h))
        pygame.draw.rect(self.screen, cfg.C_EVAL_BORDER, (bx, by, bw, bh), 1)

        # Score numérico
        t = fm.small().render(score_str, True, cfg.C_TEXT_DIM)
        self.screen.blit(t, t.get_rect(center=(bx + bw // 2, by + bh + 14)))

    # ── Panel lateral ──────────────────────────────────────────────────────

    def _draw_side_panel(
        self,
        board: chess.Board,
        san_history: list[str],
        mode_label: str,
        engine_available: bool,
        score,
        show_ai_indicator: bool = True,
        show_blue_arrow_toggle: bool = False,
        blue_arrow_enabled: bool = False,
        show_test_mode_toggle: bool = False,
        test_mode_enabled: bool = False,
        mouse_pos: tuple[int, int] = (0, 0),
        evaluation_samples: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
        opening_label: str | None = None,
        history_index: int | None = None,
        history_position_count: int | None = None,
    ):
        px = cfg.PANEL_X
        py = cfg.PANEL_Y
        pw = cfg.PANEL_WIDTH
        ph = cfg.PANEL_HEIGHT

        # Fondo del panel
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((*cfg.C_PANEL_BG, 230))
        pygame.draw.rect(panel_surf, cfg.C_PANEL_BORDER, (0, 0, pw, ph), 1, border_radius=8)
        self.screen.blit(panel_surf, (px, py))

        y = py + 18
        pad = 12

        # ── Modo ──────────────────────────────────────────────────────────
        t = fm.small(bold=True).render("MODO", True, cfg.C_TEXT_DIM)
        self.screen.blit(t, (px + pad, y)); y += 20
        t = fm.normal().render(mode_label, True, cfg.C_TEXT_ACCENT)
        self.screen.blit(t, (px + pad, y)); y += 28

        if opening_label:
            t = fm.small().render(opening_label, True, (190, 210, 140))
            self.screen.blit(t, (px + pad, y)); y += 20

        # ── Turno ─────────────────────────────────────────────────────────
        turn_str = "Turno: Blancas" if board.turn == chess.WHITE else "Turno: Negras"
        t = fm.normal(bold=True).render(turn_str, True, cfg.C_TEXT)
        self.screen.blit(t, (px + pad, y)); y += 26

        if board.is_check():
            t = fm.normal().render("  !! JAQUE !", True, (255, 80, 80))
            self.screen.blit(t, (px + pad, y))
        y += 24

        # ── Evaluación ────────────────────────────────────────────────────
        if engine_available:
            t = fm.small(bold=True).render("EVALUACIÓN IA", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, (px + pad, y)); y += 20

            if show_ai_indicator:
                if score is not None:
                    try:
                        if score.is_mate():
                            m = score.mate()
                            ev_text = f"Mate en {abs(m)}" + (" (Blancas)" if m > 0 else " (Negras)")
                        else:
                            cp = score.score()
                            ev_text = f"{cp/100:+.2f}  ({'↑ Blancas' if cp > 0 else '↓ Negras' if cp < 0 else 'Igual'})"
                    except Exception:
                        ev_text = "—"
                else:
                    ev_text = "Calculando…"
                t = fm.normal().render(ev_text, True, cfg.C_TEXT_ACCENT)
            else:
                t = fm.normal().render("Oculta (Indicador OFF)", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, (px + pad, y)); y += 28
        else:
            t = fm.normal().render("⚙ Stockfish no disponible", True, (180, 80, 80))
            self.screen.blit(t, (px + pad, y)); y += 28

        if evaluation_samples:
            y = self._draw_evaluation_chart(px + pad, y, pw - pad * 2, evaluation_samples)

        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER, (px + pad, y), (px + pw - pad, y)); y += 12

        t = fm.small(bold=True).render("MOVIMIENTOS", True, cfg.C_TEXT_DIM)
        self.screen.blit(t, (px + pad, y)); y += 20

        toggle_rows = int(show_blue_arrow_toggle) + int(show_test_mode_toggle)
        FOOTER_H = 242 + 40 * toggle_rows
        max_visible = max(0, (py + ph - y - FOOTER_H) // 18)
        pairs_total = (len(san_history) + 1) // 2
        start_pair  = max(0, pairs_total - max_visible)

        self.history_move_rects = {}
        for pair_idx in range(start_pair, pairs_total):
            i = pair_idx * 2
            w_san = san_history[i] if i < len(san_history) else ""
            b_san = san_history[i + 1] if i + 1 < len(san_history) else ""
            line  = f"{pair_idx + 1:>3}. {w_san:<10} {b_san}"
            active = history_index is None or history_index in (i + 1, i + 2)
            color = cfg.C_TEXT if active else cfg.C_TEXT_DIM
            t = fm.normal().render(line, True, color)
            row_rect = pygame.Rect(px + pad, y, pw - pad * 2, 18)
            if row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, (45, 45, 75), row_rect, border_radius=3)
            self.screen.blit(t, (px + pad, y))
            if i < len(san_history):
                self.history_move_rects[i + 1] = pygame.Rect(
                    row_rect.x, row_rect.y, row_rect.width // 2, row_rect.height
                )
            if i + 1 < len(san_history):
                self.history_move_rects[i + 2] = pygame.Rect(
                    row_rect.x + row_rect.width // 2, row_rect.y,
                    row_rect.width - row_rect.width // 2, row_rect.height
                )
            y += 18

        btn_start_y = py + ph - FOOTER_H
        self._draw_history_controls(px, btn_start_y, pw, pad, mouse_pos,
                                    history_index, history_position_count)
        btn_start_y += 40
        flip_w = pw - pad * 2
        col_w  = (flip_w - 6) // 2

        # Fila 1: Voltear Tablero + Toggle Indicador IA
        self.flip_btn_rect = pygame.Rect(px + pad, btn_start_y, col_w, 32)
        self.btn_toggle_indicator = pygame.Rect(px + pad + col_w + 6, btn_start_y, col_w, 32)

        # Render Voltear
        hov_f = self.flip_btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, cfg.C_BTN_HOVER if hov_f else cfg.C_BTN, self.flip_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, self.flip_btn_rect, 1, border_radius=8)
        txt = fm.small(bold=True).render("Voltear", True, cfg.C_BTN_TEXT)
        self.screen.blit(txt, txt.get_rect(center=self.flip_btn_rect.center))

        # Render Indicador IA Toggle Button
        hov_i = self.btn_toggle_indicator.collidepoint(mouse_pos)
        ind_bg = (30, 110, 60) if show_ai_indicator else (90, 40, 50)
        ind_bg_draw = tuple(min(255, c + 35) for c in ind_bg) if hov_i else ind_bg
        pygame.draw.rect(self.screen, ind_bg_draw, self.btn_toggle_indicator, border_radius=8)
        pygame.draw.rect(self.screen, (100, 160, 255) if show_ai_indicator else (180, 80, 80), self.btn_toggle_indicator, 1, border_radius=8)
        ind_text = "IA: ON" if show_ai_indicator else "IA: OFF"
        txt = fm.small(bold=True).render(ind_text, True, cfg.C_BTN_TEXT)
        self.screen.blit(txt, txt.get_rect(center=self.btn_toggle_indicator.center))

        blue_row_y = btn_start_y + 40
        if show_blue_arrow_toggle:
            self.btn_toggle_blue_arrow = pygame.Rect(px + pad, blue_row_y, flip_w, 32)
            hov_b = self.btn_toggle_blue_arrow.collidepoint(mouse_pos)
            blue_bg = (35, 85, 165) if blue_arrow_enabled else (55, 45, 75)
            blue_draw = tuple(min(255, c + 35) for c in blue_bg) if hov_b else blue_bg
            pygame.draw.rect(self.screen, blue_draw, self.btn_toggle_blue_arrow, border_radius=8)
            pygame.draw.rect(self.screen, (90, 165, 255), self.btn_toggle_blue_arrow, 1, border_radius=8)
            blue_text = "Flecha azul: ON" if blue_arrow_enabled else "Flecha azul: OFF"
            txt = fm.small(bold=True).render(blue_text, True, cfg.C_BTN_TEXT)
            self.screen.blit(txt, txt.get_rect(center=self.btn_toggle_blue_arrow.center))
        else:
            self.btn_toggle_blue_arrow = pygame.Rect(0, 0, 0, 0)

        test_row_y = btn_start_y + 40 + 40 * int(show_blue_arrow_toggle)
        if show_test_mode_toggle:
            self.btn_toggle_test_mode = pygame.Rect(px + pad, test_row_y, flip_w, 32)
            hov_t = self.btn_toggle_test_mode.collidepoint(mouse_pos)
            test_bg = (125, 80, 35) if test_mode_enabled else (55, 45, 75)
            test_draw = tuple(min(255, c + 35) for c in test_bg) if hov_t else test_bg
            pygame.draw.rect(self.screen, test_draw, self.btn_toggle_test_mode, border_radius=8)
            pygame.draw.rect(self.screen, (230, 165, 70), self.btn_toggle_test_mode, 1, border_radius=8)
            test_text = "Prueba ON: clic derecho" if test_mode_enabled else "Modo prueba: OFF"
            txt = fm.small(bold=True).render(test_text, True, cfg.C_BTN_TEXT)
            self.screen.blit(txt, txt.get_rect(center=self.btn_toggle_test_mode.center))
        else:
            self.btn_toggle_test_mode = pygame.Rect(0, 0, 0, 0)

        orient_y = btn_start_y + 41 + 40 * toggle_rows
        orient_label = "Vista: Negras abajo" if self.flipped else "Vista: Blancas abajo"
        t_orient = fm.small().render(orient_label, True, cfg.C_TEXT_DIM)
        self.screen.blit(t_orient, t_orient.get_rect(center=(px + pw // 2, orient_y)))

        # Cuadrícula 2×2 de botones de acción
        cell_y = btn_start_y + 52 + 40 * toggle_rows
        cell_h = 32
        cell_gap = 6

        action_defs = [
            ("btn_undo",     "Deshacer",  (60,  60, 110)),
            ("btn_save",     "Guardar",   (40, 100,  80)),
            ("btn_restart",  "Reiniciar", (100, 50,  50)),
            ("btn_analysis", "Analisis",  (40,  90, 160)),
        ]
        for i, (attr, label, base_col) in enumerate(action_defs):
            col = i % 2
            row = i // 2
            rx = px + pad + col * (col_w + cell_gap)
            ry = cell_y + row * (cell_h + cell_gap)
            rect = pygame.Rect(rx, ry, col_w, cell_h)
            setattr(self, attr, rect)
            hov = rect.collidepoint(mouse_pos)
            draw_col = tuple(min(255, c + 40) for c in base_col) if hov else base_col
            pygame.draw.rect(self.screen, draw_col, rect, border_radius=8)
            pygame.draw.rect(self.screen, (80, 80, 130), rect, 1, border_radius=8)
            txt = fm.small(bold=True).render(label, True, cfg.C_BTN_TEXT)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        # Botón Menú (ancho completo al fondo)
        menu_y = cell_y + 2 * (cell_h + cell_gap) + 4
        menu_rect = pygame.Rect(px + pad, menu_y, flip_w, cell_h)
        self.btn_menu = menu_rect
        hov = menu_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (80, 50, 110) if hov else (55, 35, 80),
                         menu_rect, border_radius=8)
        pygame.draw.rect(self.screen, (80, 80, 130), menu_rect, 1, border_radius=8)
        txt = fm.small(bold=True).render("Menu Principal", True, cfg.C_BTN_TEXT)
        self.screen.blit(txt, txt.get_rect(center=menu_rect.center))

    def _draw_evaluation_chart(self, x: int, y: int, width: int,
                               samples: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> int:
        """Mini gráfico de evaluación; cada punto es ``(ply, centipeones)``."""
        height = 54
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (18, 18, 34), rect, border_radius=5)
        label = fm.small(bold=True).render("CURVA DE EVALUACIÓN", True, cfg.C_TEXT_DIM)
        self.screen.blit(label, (x + 6, y + 4))
        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER, (x, y + height // 2),
                         (x + width, y + height // 2), 1)
        if len(samples) > 1:
            limit = 400
            points = []
            for index, (_, score_cp) in enumerate(samples):
                clipped = max(-limit, min(limit, score_cp))
                px = x + round(width * index / (len(samples) - 1))
                py = y + height // 2 - round((height // 2 - 3) * clipped / limit)
                points.append((px, py))
            pygame.draw.lines(self.screen, cfg.C_TEXT_ACCENT, False, points, 2)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, rect, 1, border_radius=5)
        return y + height + 8

    def _draw_history_controls(self, px: int, y: int, pw: int, pad: int,
                               mouse_pos: tuple[int, int], history_index: int | None,
                               history_position_count: int | None) -> None:
        """Controles de navegación que sólo cambian la vista, nunca el juego."""
        inner_w = pw - pad * 2
        small_w = 52
        self.btn_history_previous = pygame.Rect(px + pad, y, small_w, 30)
        self.btn_history_next = pygame.Rect(px + pad + small_w + 5, y, small_w, 30)
        self.btn_history_live = pygame.Rect(px + pad + 2 * (small_w + 5), y,
                                            inner_w - 2 * (small_w + 5), 30)
        browsing = history_index is not None and history_position_count is not None \
            and history_index != history_position_count - 1
        labels = ((self.btn_history_previous, "‹", cfg.C_BTN),
                  (self.btn_history_next, "›", cfg.C_BTN),
                  (self.btn_history_live, "Volver en vivo" if browsing else "En vivo", (45, 105, 75)))
        for rect, label, base in labels:
            color = tuple(min(255, c + 30) for c in base) if rect.collidepoint(mouse_pos) else base
            pygame.draw.rect(self.screen, color, rect, border_radius=7)
            pygame.draw.rect(self.screen, cfg.C_ACCENT, rect, 1, border_radius=7)
            txt = fm.small(bold=True).render(label, True, cfg.C_BTN_TEXT)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
