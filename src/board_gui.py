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

def _draw_arrow(surface: pygame.Surface, color: tuple, start: tuple, end: tuple, width: int = 10):
    """Dibuja una flecha gruesa con punta de flecha."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    # Acortar el inicio y el final para que no tape las piezas
    pad_start = cfg.SQUARE_SIZE * 0.28
    pad_end   = cfg.SQUARE_SIZE * 0.28
    ux, uy = dx / length, dy / length
    sx = start[0] + ux * pad_start
    sy = start[1] + uy * pad_start
    ex = end[0]   - ux * pad_end
    ey = end[1]   - uy * pad_end

    arrow_length = cfg.SQUARE_SIZE * 0.42
    arrow_width  = width * 2.2

    # Cuerpo de la flecha
    pygame.draw.line(surface, color, (int(sx), int(sy)), (int(ex), int(ey)), width)

    # Punta de flecha (triángulo)
    tip = (ex, ey)
    base_cx = ex - ux * arrow_length
    base_cy = ey - uy * arrow_length
    perp_x = -uy * arrow_width / 2
    perp_y  =  ux * arrow_width / 2
    p1 = (int(base_cx + perp_x), int(base_cy + perp_y))
    p2 = (int(base_cx - perp_x), int(base_cy - perp_y))
    pygame.draw.polygon(surface, color, [tip, p1, p2])


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
    ):
        self.screen = screen
        self.piece_images = piece_images
        self.flipped = flipped

        pygame.font.init()
        # Rects de botones de acción (actualizados en cada frame)
        self.flip_btn_rect    : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_undo         : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_save         : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_restart      : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_analysis     : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.btn_menu         : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        # Botones del overlay de fin de partida
        self.go_btn_restart   : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.go_btn_analysis  : pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.go_btn_menu      : pygame.Rect = pygame.Rect(0, 0, 0, 0)

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
        mouse_pos: tuple[int, int] = (0, 0),
    ):
        self.screen.fill(cfg.C_BG)
        self._draw_board_squares(board, selected_square, legal_targets, last_move)
        self._draw_arrow_overlay(best_move, board)
        self._draw_pieces(board, selected_square if dragging_piece else None, dragging_piece, drag_pos)
        self._draw_coordinates()
        self._draw_eval_bar(score, board)
        self._draw_side_panel(board, san_history, mode_label, engine_available, score, mouse_pos)

    def draw_game_over(self, result_text: str, mouse_pos: tuple = (0, 0)):
        """Overlay semitransparente de fin de partida con botones clickeables."""
        overlay = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))

        box_w, box_h = 520, 230
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

        # Tres botones de acción
        bw, bh = 148, 40
        gap = 12
        total_w = bw * 3 + gap * 2
        bx0 = cx - total_w // 2
        btn_y = by + 162

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

        for sq in range(64):
            rect = square_to_rect(sq, self.flipped)
            col  = chess.square_file(sq)
            row  = chess.square_rank(sq)
            light = (col + row) % 2 == 0

            # Color base de la casilla
            base = cfg.C_LIGHT_SQ if light else cfg.C_DARK_SQ
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

    def _draw_arrow_overlay(self, best_move: Optional[chess.Move], board: chess.Board):
        if best_move is None:
            return
        start = square_to_pixel(best_move.from_square, self.flipped)
        end   = square_to_pixel(best_move.to_square,   self.flipped)

        # Dibujar sobre superficie con alpha
        arrow_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        outline_col = (*cfg.C_ARROW_OUTLINE[:3], 255)
        fill_col    = (*cfg.C_ARROW_FILL[:3], 185)
        _draw_arrow(arrow_surf, outline_col, start, end, width=13)
        _draw_arrow(arrow_surf, fill_col,    start, end, width=9)
        self.screen.blit(arrow_surf, (0, 0))

    # ── Coordenadas ────────────────────────────────────────────────────────

    def _draw_coordinates(self):
        files = "abcdefgh"
        ranks = "12345678"
        for i in range(8):
            fi = i if not self.flipped else 7 - i
            ri = i if not self.flipped else 7 - i
            lx = cfg.BOARD_OFFSET_X + i * cfg.SQUARE_SIZE + cfg.SQUARE_SIZE // 2
            ly = cfg.BOARD_OFFSET_Y + cfg.BOARD_SIZE + 6
            t  = fm.small().render(files[fi], True, cfg.C_TEXT_DIM)
            self.screen.blit(t, t.get_rect(center=(lx, ly)))
            rx = cfg.BOARD_OFFSET_X - 14
            ry = cfg.BOARD_OFFSET_Y + (7 - i) * cfg.SQUARE_SIZE + cfg.SQUARE_SIZE // 2
            t2 = fm.small().render(ranks[ri], True, cfg.C_TEXT_DIM)
            self.screen.blit(t2, t2.get_rect(center=(rx, ry)))

    # ── Barra de evaluación ────────────────────────────────────────────────

    def _draw_eval_bar(self, score, board: chess.Board):
        bx = cfg.EVAL_BAR_X
        by = cfg.EVAL_BAR_Y
        bw = cfg.EVAL_BAR_WIDTH
        bh = cfg.EVAL_BAR_HEIGHT

        # Fondo negro
        pygame.draw.rect(self.screen, cfg.C_EVAL_BLACK, (bx, by, bw, bh))

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
        mouse_pos: tuple[int, int] = (0, 0),
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
            self.screen.blit(t, (px + pad, y)); y += 28
        else:
            t = fm.normal().render("⚙ Stockfish no disponible", True, (180, 80, 80))
            self.screen.blit(t, (px + pad, y)); y += 28

        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER, (px + pad, y), (px + pw - pad, y)); y += 12

        t = fm.small(bold=True).render("MOVIMIENTOS", True, cfg.C_TEXT_DIM)
        self.screen.blit(t, (px + pad, y)); y += 20

        FOOTER_H = 200
        max_visible = max(0, (py + ph - y - FOOTER_H) // 18)
        pairs_total = (len(san_history) + 1) // 2
        start_pair  = max(0, pairs_total - max_visible)

        for pair_idx in range(start_pair, pairs_total):
            i = pair_idx * 2
            w_san = san_history[i] if i < len(san_history) else ""
            b_san = san_history[i + 1] if i + 1 < len(san_history) else ""
            line  = f"{pair_idx + 1:>3}. {w_san:<10} {b_san}"
            color = cfg.C_TEXT if pair_idx == pairs_total - 1 else cfg.C_TEXT_DIM
            t = fm.normal().render(line, True, color)
            self.screen.blit(t, (px + pad, y))
            y += 18

        # Botón Voltear (ancho completo)
        btn_start_y = py + ph - FOOTER_H
        flip_w = pw - pad * 2
        flip_rect = pygame.Rect(px + pad, btn_start_y, flip_w, 32)
        self.flip_btn_rect = flip_rect
        orient_label = "Vista: Negras abajo" if self.flipped else "Vista: Blancas abajo"
        hov = flip_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, cfg.C_BTN_HOVER if hov else cfg.C_BTN,
                         flip_rect, border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_ACCENT, flip_rect, 1, border_radius=8)
        self.screen.blit(
            fm.small(bold=True).render("Voltear tablero", True, cfg.C_BTN_TEXT),
            fm.small(bold=True).render("Voltear tablero", True, cfg.C_BTN_TEXT)
                .get_rect(center=flip_rect.center)
        )
        t_orient = fm.small().render(orient_label, True, cfg.C_TEXT_DIM)
        self.screen.blit(t_orient, t_orient.get_rect(
            center=(px + pw // 2, btn_start_y + 32 + 9)))

        # Cuadrícula 2×2 de botones de acción
        cell_y = btn_start_y + 52
        cell_h = 32
        cell_gap = 6
        col_w = (flip_w - cell_gap) // 2

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
