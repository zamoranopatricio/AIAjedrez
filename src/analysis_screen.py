"""
src/analysis_screen.py
Pantalla de análisis post-partida: revisión paso a paso con
evaluación de cada jugada (rating 1-5, justificación, mejor opción).
"""
import math
import sys
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine
import pygame

import config as cfg
from src import font_manager as fm

# ── Constantes de layout ───────────────────────────────────────────────────
SQ   = 60                          # tamaño casilla en análisis
BSZ  = SQ * 8                      # 480
BX   = 16                          # x del tablero
BY   = 68                          # y del tablero
PX   = BX + BSZ + 18               # x del panel derecho
PW   = cfg.WINDOW_WIDTH - PX - 10  # ancho del panel derecho

# Colores de rating (armónicos, tonos oscuros elegantes y legibles)
RATING_META = [
    # (delta_max, rating, color_bg,       color_text,       badge, label)
    (20,   5, (20, 120,  70), (220, 255, 230), "[5]", "Excelente"),
    (50,   4, (30, 100, 150), (210, 235, 255), "[4]", "Bueno"),
    (100,  3, (140, 110,  20), (255, 245, 200), "[3]", "Imprecision"),
    (200,  2, (150,  70,  20), (255, 225, 200), "[2]", "Error"),
    (9999, 1, (150,  35,  35), (255, 205, 205), "[1]", "Error grave"),
]


def _rate(delta: int) -> tuple:
    for dmax, rating, cbg, ctxt, badge, label in RATING_META:
        if delta <= dmax:
            return rating, cbg, ctxt, badge, label
    return 1, (180, 0, 0), (255, 180, 160), "[1]", "Error grave"


def _justify(san: str, best_san: str, delta: int, rating: int,
             score_after: int, is_best: bool,
             color=None, move_idx: int = 0) -> str:
    """Justificacion contextual y variada segun tipo de jugada, fase y error."""
    import chess as _chess

    is_capture   = "x" in san
    is_check     = "+" in san or "#" in san
    is_castling  = san.startswith("O-O")
    is_promotion = "=" in san

    if is_castling:
        piece = "enroque"
    elif san and san[0].isupper() and san[0] != "O":
        piece = {"N": "caballo", "B": "alfil", "R": "torre",
                 "Q": "dama", "K": "rey"}.get(san[0], "pieza")
    else:
        piece = "peon"

    phase = "apertura" if move_idx < 12 else ("final" if move_idx > 28 else "mediojuego")
    mover = "Las blancas" if color == _chess.WHITE else "Las negras"
    rival = "las negras"  if color == _chess.WHITE else "las blancas"
    sc    = f"{score_after / 100:+.2f}"
    seed  = (move_idx * 17 + int(abs(delta)) * 3 + rating * 11) % 9

    if rating == 5:
        opts = [f"{san} es la jugada optima. Evaluacion: {sc}."]
        if is_best:
            opts += [
                f"{mover} encontraron exactamente la mejor respuesta. Sin perdida de ventaja.",
                f"Perfecto. El motor confirma {san} como jugada numero uno en esta posicion.",
            ]
        if is_castling:
            opts += ["El enroque es prioritario: asegura al rey y activa la torre al mismo tiempo.",
                     "Enrocar en este momento es correcto: mejora seguridad y coordinacion."]
        if is_capture:
            opts += [f"La captura {san} es la mas eficiente: toma material sin conceder contraplay.",
                     f"Excelente captura. Toma en el momento justo y mantiene la iniciativa."]
        if is_check:
            opts += [f"{san} con jaque es la continuacion mas fuerte: fuerza al rival a reaccionar y gana tempo."]
        if piece in ("caballo", "alfil") and phase == "apertura":
            opts += [f"Desarrollar el {piece} con {san} es el principio de apertura correcto aplicado con precision."]
        if piece == "peon" and phase == "apertura":
            opts += [f"El avance {san} controla el centro y facilita el desarrollo. Apertura solida."]
        return opts[seed % len(opts)]

    if rating == 4:
        pos = "favorable" if score_after > 40 else ("dificil" if score_after < -40 else "equilibrada")
        opts = [
            f"Buena jugada. Solo {delta} cp de diferencia. La posicion {pos} se mantiene.",
            f"{san} es correcto, aunque {best_san} era {delta} cp mas preciso. Resultado similar.",
            f"Solido. {san} no concede ventajas y la posicion {pos} sigue bajo control.",
        ]
        if is_capture:
            opts += [f"La captura {san} es buena, aunque {best_san} era ligeramente superior ({delta} cp). Sin consecuencias graves."]
        if phase == "apertura":
            opts += [f"Apertura solida. {best_san} optimizaba mejor el desarrollo, pero {delta} cp es asumible."]
        if is_castling:
            opts += [f"Enrocar es una buena decision. {best_san} era algo mas activo, pero la seguridad del rey es prioridad."]
        return opts[seed % len(opts)]

    if rating == 3:
        opts = [
            f"Imprecision de {delta} cp. {san} es jugable pero {best_san} mantenia mas presion sobre {rival}.",
            f"Con {best_san} se evitaban {delta} cp de perdida y se mantenia la iniciativa.",
            f"Jugada pasiva. {san} le da a {rival} tiempo para reorganizarse; {best_san} era superior.",
        ]
        if is_capture:
            opts += [f"La captura {san} es prematura: {best_san} era mejor forma de resolver la tension ({delta} cp)."]
        if phase == "mediojuego":
            opts += [f"En el mediojuego, {san} pierde {delta} cp que {rival} pueden convertir en ventaja concreta."]
        if phase == "final":
            opts += [f"Imprecision en el final ({delta} cp). {best_san} conservaba mejor estructura y conversion."]
        if piece in ("caballo", "alfil"):
            opts += [f"El {piece} estaba mejor colocado tras {best_san}. {san} lo lleva a casilla menos activa."]
        return opts[seed % len(opts)]

    if rating == 2:
        opts = [
            f"Error de {delta} cp. {san} cede ventaja significativa; {best_san} era la continuacion correcta.",
            f"{san} permite a {rival} mejorar. {best_san} hubiera mantenido el control ({delta} cp).",
            f"Movimiento que cambia el balance. {rival.capitalize()} ganan recursos. {best_san} era superior.",
        ]
        if is_capture:
            opts += [f"La captura {san} parecia ganar material, pero {best_san} era la secuencia correcta sin conceder {delta} cp."]
        if piece == "rey":
            opts += [f"Mover el rey con {san} lo expone ({delta} cp perdidos). {best_san} mantenia la seguridad."]
        if phase == "apertura":
            opts += [f"En la apertura, {san} cede {delta} cp. {best_san} seguia el desarrollo correcto."]
        return opts[seed % len(opts)]

    opts = [
        f"Error grave ({delta} cp). {san} cambia el resultado. {best_san} era imprescindible.",
        f"Blunder de {delta} cp. {san} regala ventaja decisiva a {rival}. Muy dificil de revertir.",
        f"El error mas costoso: {delta} cp perdidos con {san}. {best_san} era la unica respuesta correcta.",
    ]
    if is_capture:
        opts += [f"La captura {san} es un error grave ({delta} cp). Parecia ganar material pero {best_san} mantenia la posicion."]
    if piece == "rey":
        opts += [f"Mover el rey con {san} es decisivo: queda expuesto. {best_san} era esencial para la defensa."]
    if phase == "apertura":
        opts += [f"Error grave de apertura ({delta} cp). {san} viola principios y cede ventaja enorme desde el inicio."]
    return opts[seed % len(opts)]


@dataclass
class MoveData:
    idx: int                       # 0-based dentro de moves_played
    color: chess.Color
    san: str
    fen_before: str
    move: chess.Move
    best_move: Optional[chess.Move]
    best_san: str
    score_after_cp: int            # evaluación post-movimiento (perspectiva blancas)
    delta_cp: int                  # pérdida del bando que movió
    rating: int
    cbg: tuple; ctxt: tuple; badge: str; label: str
    justification: str


# ── Pantalla principal ─────────────────────────────────────────────────────

class AnalysisScreen:
    """
    Uso:
        screen = AnalysisScreen(pygame_surface, engine_path,
                                snapshots, moves_played, san_history,
                                result_text, piece_images)
        screen.run()   # bloquea hasta que el usuario sale
    """

    def __init__(
        self,
        screen: pygame.Surface,
        engine_path: str,
        snapshots: list,        # list[chess.Board] — estado ANTES de cada movimiento
        moves_played: list,     # list[chess.Move]
        san_history: list,      # list[str]
        result_text: str,
        piece_images: dict,
    ):
        self.screen      = screen
        self.engine_path = engine_path
        self.snapshots   = snapshots
        self.moves       = moves_played
        self.san_history = san_history
        self.result_text = result_text
        self.clock       = pygame.time.Clock()

        # Escalar piezas al tamaño del tablero de análisis
        self.pieces = {}
        for p, img in piece_images.items():
            self.pieces[p] = pygame.transform.smoothscale(img, (SQ, SQ))

        # Datos calculados tras el análisis
        self.data: list[MoveData] = []
        self.current_idx  = 0          # índice del movimiento seleccionado (-1 = posición inicial)
        self._scroll_offset = 0        # scroll en la lista de movimientos
        self._list_item_h   = 36
        self._list_top      = BY + 10
        self._list_visible  = 10       # aprox. cuántos caben

        # Botones de navegación (ubicados debajo de las coordenadas a-h)
        nav_y = BY + BSZ + 38
        bw, bh = 72, 34
        self._btn_first = pygame.Rect(BX,          nav_y, bw, bh)
        self._btn_prev  = pygame.Rect(BX + bw + 6, nav_y, bw, bh)
        self._btn_next  = pygame.Rect(BX + (bw+6)*2, nav_y, bw, bh)
        self._btn_last  = pygame.Rect(BX + (bw+6)*3, nav_y, bw, bh)
        self._btn_menu  = pygame.Rect(cfg.WINDOW_WIDTH - 160, 14, 148, 36)

    # ── Run ────────────────────────────────────────────────────────────────

    def run(self):
        self._run_analysis()
        if not self.data:
            return                      # partida sin movimientos, salir

        self.current_idx = len(self.data) - 1
        self._ensure_scroll()

        while True:
            mp = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_m):
                        return
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self._go(self.current_idx - 1)
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._go(self.current_idx + 1)
                    if event.key == pygame.K_HOME:
                        self._go(0)
                    if event.key == pygame.K_END:
                        self._go(len(self.data) - 1)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)
                if event.type == pygame.MOUSEWHEEL:
                    self._scroll_offset = max(
                        0, min(len(self.data) - self._list_visible,
                               self._scroll_offset - event.y))

            self._draw(mp)
            pygame.display.flip()
            self.clock.tick(cfg.FPS)

    # ── Análisis con Stockfish ─────────────────────────────────────────────

    def _run_analysis(self):
        if not self.moves:
            return
        n = len(self.moves)
        self._draw_loading(0, n)

        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        except Exception:
            return

        for i, (board_before, move, san) in enumerate(
                zip(self.snapshots, self.moves, self.san_history)):
            self._draw_loading(i, n)
            try:
                info = engine.analyse(board_before, chess.engine.Limit(time=0.25))
                best_pv = info.get("pv", [])
                best_move = best_pv[0] if best_pv else None
                score_best_pov = info["score"].pov(board_before.turn)
                score_best_cp  = score_best_pov.score(mate_score=10000) or 0
            except Exception:
                best_move, score_best_cp = None, 0

            # 2. Analizar posición DESPUÉS del movimiento real
            board_after = board_before.copy()
            board_after.push(move)
            try:
                info2 = engine.analyse(board_after, chess.engine.Limit(time=0.20))
                score_after_next = info2["score"].pov(board_after.turn)
                score_after_cp_next = score_after_next.score(mate_score=10000) or 0
                # Desde la perspectiva del que acaba de mover: negamos
                score_after_mover = -score_after_cp_next
                # Desde perspectiva de blancas (para barra eval)
                score_after_white = info2["score"].white().score(mate_score=10000) or 0
            except Exception:
                score_after_mover, score_after_white = 0, 0

            # 3. Delta (pérdida del bando que movió)
            delta = max(0, score_best_cp - score_after_mover)

            # 4. SAN de la mejor jugada
            best_san = ""
            if best_move:
                try:
                    best_san = board_before.san(best_move)
                except Exception:
                    best_san = str(best_move)

            is_best = (best_move == move)

            rating, cbg, ctxt, badge, label = _rate(delta)
            justif = _justify(san, best_san, delta, rating,
                               score_after_white, is_best,
                               color=board_before.turn, move_idx=i)

            self.data.append(MoveData(
                idx=i,
                color=board_before.turn,
                san=san,
                fen_before=board_before.fen(),
                move=move,
                best_move=best_move,
                best_san=best_san,
                score_after_cp=score_after_white,
                delta_cp=delta,
                rating=rating,
                cbg=cbg, ctxt=ctxt, badge=badge, label=label,
                justification=justif,
            ))

        engine.quit()

    # ── Navegación ────────────────────────────────────────────────────────

    def _go(self, idx: int):
        if not self.data:
            return
        self.current_idx = max(0, min(len(self.data) - 1, idx))
        self._ensure_scroll()

    def _ensure_scroll(self):
        if self.current_idx < self._scroll_offset:
            self._scroll_offset = self.current_idx
        elif self.current_idx >= self._scroll_offset + self._list_visible:
            self._scroll_offset = self.current_idx - self._list_visible + 1

    def _handle_click(self, pos):
        if self._btn_menu.collidepoint(pos):
            raise _BackToMenu()
        if self._btn_first.collidepoint(pos): self._go(0)
        if self._btn_prev.collidepoint(pos):  self._go(self.current_idx - 1)
        if self._btn_next.collidepoint(pos):  self._go(self.current_idx + 1)
        if self._btn_last.collidepoint(pos):  self._go(len(self.data) - 1)
        # Click en lista de movimientos
        for vis_i in range(self._list_visible):
            real_i = vis_i + self._scroll_offset
            if real_i >= len(self.data):
                break
            item_y = self._list_top + vis_i * self._list_item_h
            item_r = pygame.Rect(PX + 4, item_y, PW - 8, self._list_item_h - 2)
            if item_r.collidepoint(pos):
                self._go(real_i)
                return

    # ── Render ─────────────────────────────────────────────────────────────

    def _draw(self, mp):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        self.screen.fill(cfg.C_BG)

        # ── Header ─────────────────────────────────────────────────────────
        header = pygame.Surface((W, 56), pygame.SRCALPHA)
        header.fill((20, 20, 40, 220))
        self.screen.blit(header, (0, 0))

        t = fm.medium(bold=True).render("Analisis de Partida", True, cfg.C_TEXT)
        self.screen.blit(t, (16, 16))
        t2 = fm.small().render(self.result_text, True, cfg.C_TEXT_ACCENT)
        self.screen.blit(t2, (16, 36))

        hov = self._btn_menu.collidepoint(mp)
        pygame.draw.rect(self.screen,
                         cfg.C_BTN_HOVER if hov else cfg.C_BTN,
                         self._btn_menu, border_radius=8)
        t3 = fm.normal().render("<< Volver al menu", True, cfg.C_BTN_TEXT)
        self.screen.blit(t3, t3.get_rect(center=self._btn_menu.center))

        # ── Tablero ────────────────────────────────────────────────────────
        d = self.data[self.current_idx]
        board = chess.Board(d.fen_before)
        board.push(d.move)
        self._draw_board(board, d)

        # ── Navegación ─────────────────────────────────────────────────────
        nav_labels = [("<<", self._btn_first), ("<", self._btn_prev),
                      (">", self._btn_next),  (">>", self._btn_last)]
        for label, rect in nav_labels:
            hov = rect.collidepoint(mp)
            pygame.draw.rect(self.screen,
                             cfg.C_BTN_HOVER if hov else (40, 40, 70),
                             rect, border_radius=6)
            pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER, rect, 1, border_radius=6)
            t = fm.normal(bold=True).render(label, True, cfg.C_TEXT)
            self.screen.blit(t, t.get_rect(center=rect.center))

        nav_y = self._btn_first.y
        move_n = d.idx + 1
        info_t = fm.small().render(
            f"Jugada {move_n} / {len(self.data)}  —  "
            f"{'Blancas' if d.color == chess.WHITE else 'Negras'}",
            True, cfg.C_TEXT)
        self.screen.blit(info_t, (BX + 4 * (72 + 6) + 12, nav_y + 9))

        # ── Panel derecho ──────────────────────────────────────────────────
        self._draw_right_panel(d, mp)

    def _draw_board(self, board: chess.Board, d: MoveData):
        # Casillas base
        for sq in range(64):
            col, row = chess.square_file(sq), chess.square_rank(sq)
            light = (col + row) % 2 == 0
            rx = BX + col * SQ
            ry = BY + (7 - row) * SQ
            pygame.draw.rect(self.screen,
                             cfg.C_LIGHT_SQ if light else cfg.C_DARK_SQ,
                             (rx, ry, SQ, SQ))

        # Highlight último movimiento
        alpha = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
        for sq in (d.move.from_square, d.move.to_square):
            col, row = chess.square_file(sq), chess.square_rank(sq)
            alpha.fill((*cfg.C_LAST_MOVE[:3], 140))
            self.screen.blit(alpha, (BX + col * SQ, BY + (7 - row) * SQ))

        # Piezas
        for sq in range(64):
            piece = board.piece_at(sq)
            if piece and piece in self.pieces:
                col, row = chess.square_file(sq), chess.square_rank(sq)
                self.screen.blit(self.pieces[piece],
                                 (BX + col * SQ, BY + (7 - row) * SQ))

        # Flecha jugada real (azul)
        self._arrow(d.move.from_square, d.move.to_square, (80, 160, 255, 180))

        # Flecha mejor jugada (naranja), si es distinta
        if d.best_move and d.best_move != d.move:
            self._arrow(d.best_move.from_square, d.best_move.to_square,
                        (255, 160, 0, 180))
            # Leyenda
            t = fm.small().render(
                f"  ← Jugada real   ← Mejor jugada ({d.best_san})", True, cfg.C_TEXT_DIM)
            # No cabe bien en una línea, mostramos solo en el panel

        # Coordenadas
        for i in range(8):
            tf = fm.small().render("abcdefgh"[i], True, cfg.C_TEXT_DIM)
            self.screen.blit(tf, (BX + i * SQ + SQ // 2 - 4, BY + BSZ + 2))
            tr = fm.small().render(str(i + 1), True, cfg.C_TEXT_DIM)
            self.screen.blit(tr, (BX - 12, BY + (7 - i) * SQ + SQ // 2 - 6))

        # Borde
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER,
                         (BX, BY, BSZ, BSZ), 2)

    def _arrow(self, from_sq: int, to_sq: int, color: tuple):
        fc, fr = chess.square_file(from_sq), chess.square_rank(from_sq)
        tc, tr = chess.square_file(to_sq),   chess.square_rank(to_sq)
        sx = BX + fc * SQ + SQ // 2
        sy = BY + (7 - fr) * SQ + SQ // 2
        ex = BX + tc * SQ + SQ // 2
        ey = BY + (7 - tr) * SQ + SQ // 2

        surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        pad = SQ * 0.25
        sx2, sy2 = sx + ux * pad, sy + uy * pad
        ex2, ey2 = ex - ux * pad, ey - uy * pad

        pygame.draw.line(surf, color, (int(sx2), int(sy2)), (int(ex2), int(ey2)), 7)
        al = SQ * 0.38
        aw = 14
        p0 = (int(ex2), int(ey2))
        bx2 = ex2 - ux * al
        by2 = ey2 - uy * al
        p1 = (int(bx2 + (-uy) * aw), int(by2 + ux * aw))
        p2 = (int(bx2 - (-uy) * aw), int(by2 - ux * aw))
        pygame.draw.polygon(surf, color, [p0, p1, p2])
        self.screen.blit(surf, (0, 0))

    def _draw_right_panel(self, d: MoveData, mp):
        H = cfg.WINDOW_HEIGHT

        # Fondo panel
        panel = pygame.Surface((PW, H - BY), pygame.SRCALPHA)
        panel.fill((*cfg.C_PANEL_BG, 220))
        pygame.draw.rect(panel, cfg.C_PANEL_BORDER, (0, 0, PW, H - BY), 1, border_radius=6)
        self.screen.blit(panel, (PX, BY))

        pad = 10

        # ── Lista de movimientos ──────────────────────────────────────────
        list_h = self._list_visible * self._list_item_h
        t = fm.small(bold=True).render("MOVIMIENTOS", True, cfg.C_TEXT_DIM)
        self.screen.blit(t, (PX + pad, self._list_top - 16))

        for vis_i in range(self._list_visible):
            real_i = vis_i + self._scroll_offset
            if real_i >= len(self.data):
                break
            md = self.data[real_i]
            iy = self._list_top + vis_i * self._list_item_h
            item_r = pygame.Rect(PX + 4, iy, PW - 8, self._list_item_h - 2)

            is_sel = (real_i == self.current_idx)
            bg = (*md.cbg, 220) if is_sel else (*md.cbg, 95)
            bdr = (255, 255, 255) if is_sel else md.cbg

            pygame.draw.rect(self.screen, bg, item_r, border_radius=6)
            pygame.draw.rect(self.screen, bdr, item_r, 2 if is_sel else 1, border_radius=6)

            move_num = real_i // 2 + 1
            dot = "." if md.color == chess.WHITE else "..."
            label = f"{move_num}{dot} {md.san}"
            text_color = (255, 255, 255) if is_sel else (225, 230, 240)
            tc = fm.normal(bold=is_sel).render(label, True, text_color)
            self.screen.blit(tc, (item_r.x + 10, item_r.y + 7))

            # Badge rating
            badge = fm.small(bold=True).render(f"{md.badge} {md.rating}", True, md.ctxt)
            self.screen.blit(badge, badge.get_rect(
                right=item_r.right - 8, centery=item_r.centery))

        # ── Separador ─────────────────────────────────────────────────────
        sep_y = self._list_top + list_h + 6
        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER,
                         (PX + pad, sep_y), (PX + PW - pad, sep_y))

        # ── Análisis detallado ────────────────────────────────────────────
        ay = sep_y + 12

        # Encabezado rating
        badge_r = pygame.Rect(PX + pad, ay, PW - pad * 2, 38)
        pygame.draw.rect(self.screen, (*d.cbg, 200), badge_r, border_radius=8)
        t = fm.medium(bold=True).render(
            f"{d.label}  ({d.rating}/5)", True, d.ctxt)
        self.screen.blit(t, t.get_rect(center=badge_r.center))
        ay += 48

        # Jugada
        t = fm.normal(bold=True).render(
            f"Jugada:  {d.san}", True, cfg.C_TEXT)
        self.screen.blit(t, (PX + pad, ay)); ay += 22

        if d.delta_cp > 0:
            t = fm.small().render(
                f"Pérdida:  {d.delta_cp} céntipawns", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, (PX + pad, ay)); ay += 20

        if d.best_san and d.best_san != d.san:
            t = fm.normal().render(f"Mejor:  {d.best_san}", True, (100, 220, 140))
            self.screen.blit(t, (PX + pad, ay)); ay += 22

        # Evaluación
        sc = d.score_after_cp / 100
        sc_str = f"Eval. post-jugada:  {sc:+.2f}"
        t = fm.small().render(sc_str, True, cfg.C_TEXT_ACCENT)
        self.screen.blit(t, (PX + pad, ay)); ay += 20

        # Leyenda flechas (si hay mejor jugada distinta)
        if d.best_move and d.best_move != d.move:
            ay += 4
            dot_blue = pygame.Surface((10, 10))
            dot_blue.fill((80, 160, 255))
            self.screen.blit(dot_blue, (PX + pad, ay + 3))
            t = fm.small().render("  Jugada real", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, (PX + pad + 12, ay)); ay += 16
            dot_ora = pygame.Surface((10, 10))
            dot_ora.fill((255, 160, 0))
            self.screen.blit(dot_ora, (PX + pad, ay + 3))
            t = fm.small().render(f"  Mejor jugada ({d.best_san})", True, cfg.C_TEXT_DIM)
            self.screen.blit(t, (PX + pad + 12, ay)); ay += 18

        # Separador
        ay += 6
        pygame.draw.line(self.screen, cfg.C_PANEL_BORDER,
                         (PX + pad, ay), (PX + PW - pad, ay))
        ay += 10

        # Justificación (texto ajustado)
        t_label = fm.small(bold=True).render("ANÁLISIS", True, cfg.C_TEXT_DIM)
        self.screen.blit(t_label, (PX + pad, ay)); ay += 18

        for line in self._wrap(d.justification, PW - pad * 2 - 6, fm.small()):
            tl = fm.small().render(line, True, cfg.C_TEXT)
            self.screen.blit(tl, (PX + pad, ay))
            ay += 17

    # ── Pantalla de carga ─────────────────────────────────────────────────

    def _draw_loading(self, done: int, total: int):
        W, H = cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT
        self.screen.fill(cfg.C_BG)
        t = fm.large(bold=True).render("Analizando partida…", True, cfg.C_TEXT)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 50)))

        bar_w, bar_h = 400, 18
        bx = (W - bar_w) // 2
        by = H // 2
        pygame.draw.rect(self.screen, (40, 40, 70), (bx, by, bar_w, bar_h), border_radius=8)
        fill = int(bar_w * done / max(total, 1))
        if fill > 0:
            pygame.draw.rect(self.screen, cfg.C_BTN, (bx, by, fill, bar_h), border_radius=8)
        pygame.draw.rect(self.screen, cfg.C_PANEL_BORDER,
                         (bx, by, bar_w, bar_h), 1, border_radius=8)

        pct = fm.small().render(f"{done}/{total} posiciones", True, cfg.C_TEXT_DIM)
        self.screen.blit(pct, pct.get_rect(center=(W // 2, H // 2 + 30)))
        pygame.display.flip()
        pygame.event.pump()

    # ── Utilidades ─────────────────────────────────────────────────────────

    @staticmethod
    def _wrap(text: str, max_px: int, font: pygame.font.Font) -> list[str]:
        words  = text.split()
        lines  = []
        line   = ""
        for w in words:
            test = (line + " " + w).strip()
            if font.size(test)[0] <= max_px:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)
        return lines


class _BackToMenu(Exception):
    pass
