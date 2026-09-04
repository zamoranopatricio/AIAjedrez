"""
src/game_state.py
Estado completo de una partida de ajedrez.
Encapsula chess.Board y gestiona selección, movimientos y resultado.
"""
import chess
import chess.pgn
import datetime
import logging
from enum import Enum, auto
from pathlib import Path

log = logging.getLogger(__name__)


class GameMode(Enum):
    HUMAN_VS_HUMAN = auto()
    HUMAN_VS_AI    = auto()


class GameState:
    """
    Mantiene el estado de la partida.

    Atributos públicos clave:
        board           : chess.Board actual
        mode            : GameMode
        human_color     : chess.WHITE | chess.BLACK (relevante en H vs IA)
        selected_square : casilla seleccionada (int) o None
        legal_targets   : lista de casillas destino legales desde selected_square
        drag_from       : casilla origen de un drag activo, o None
        last_move       : último movimiento ejecutado
        san_history     : lista de movimientos en notación SAN
        game_over       : bool
        result_text     : texto descriptivo del resultado
    """

    def __init__(
        self,
        mode: GameMode = GameMode.HUMAN_VS_HUMAN,
        human_color: chess.Color = chess.WHITE,
    ):
        self.board = chess.Board()
        self.mode = mode
        self.human_color = human_color

        # Estado de selección / arrastre
        self.selected_square: int | None = None
        self.legal_targets: list[int] = []
        self.drag_from: int | None = None

        # Historial
        self.last_move: chess.Move | None = None
        self.san_history: list[str] = []          # notación SAN (panel lateral)
        self.moves_played: list[chess.Move] = []  # movimientos UCI (para análisis)
        self._snapshots: list[chess.Board] = []   # tablero ANTES de cada jugada

        # Resultado
        self.game_over = False
        self.result_text = ""

    # ── Consultas ──────────────────────────────────────────────────────────

    def is_human_turn(self) -> bool:
        if self.mode == GameMode.HUMAN_VS_HUMAN:
            return True
        return self.board.turn == self.human_color

    def is_in_check(self) -> bool:
        return self.board.is_check()

    def king_square(self, color: chess.Color) -> int:
        return self.board.king(color)  # type: ignore[return-value]

    # ── Selección ──────────────────────────────────────────────────────────

    def select(self, square: int) -> bool:
        """
        Selecciona una pieza en 'square' si pertenece al bando en turno.
        Devuelve True si se seleccionó correctamente.
        """
        piece = self.board.piece_at(square)
        if piece and piece.color == self.board.turn:
            self.selected_square = square
            self.legal_targets = [
                m.to_square
                for m in self.board.legal_moves
                if m.from_square == square
            ]
            return True
        self.deselect()
        return False

    def deselect(self):
        self.selected_square = None
        self.legal_targets = []

    # ── Movimientos ────────────────────────────────────────────────────────

    def try_move(self, to_square: int) -> chess.Move | None:
        """
        Intenta mover la pieza seleccionada a 'to_square'.
        Si el destino es otra pieza propia, redirige la selección.
        Devuelve el movimiento ejecutado o None.
        """
        if self.selected_square is None:
            return None

        move = self._build_move(self.selected_square, to_square)
        if move and move in self.board.legal_moves:
            return self._push(move)

        # Click en pieza propia → redirigir selección
        piece = self.board.piece_at(to_square)
        if piece and piece.color == self.board.turn:
            self.select(to_square)
        else:
            self.deselect()
        return None

    def try_move_drag(self, from_sq: int, to_sq: int) -> chess.Move | None:
        """Versión drag-and-drop: from_sq y to_sq explícitos."""
        move = self._build_move(from_sq, to_sq)
        if move and move in self.board.legal_moves:
            return self._push(move)
        self.deselect()
        return None

    def push_ai_move(self, move: chess.Move) -> chess.Move | None:
        """Ejecuta el movimiento devuelto por Stockfish."""
        if move in self.board.legal_moves:
            return self._push(move)
        log.warning("Movimiento de IA ilegal: %s", move)
        return None

    def reset(
        self,
        mode: GameMode | None = None,
        human_color: chess.Color | None = None,
    ):
        """Reinicia la partida con los parámetros actuales u opcionales."""
        if mode is not None:
            self.mode = mode
        if human_color is not None:
            self.human_color = human_color
        self.board = chess.Board()
        self.selected_square = None
        self.legal_targets = []
        self.drag_from = None
        self.last_move = None
        self.san_history = []
        self.moves_played = []
        self._snapshots = []
        self.game_over = False
        self.result_text = ""

    def undo(self, double: bool = False) -> bool:
        """
        Deshace el último movimiento (o los dos últimos si double=True).
        En modo H vs IA se llama con double=True para deshacer también
        el movimiento de la IA.
        Devuelve True si se pudo deshacer.
        """
        steps = 2 if double and len(self._snapshots) >= 2 else 1
        if len(self._snapshots) < steps:
            return False

        for _ in range(steps):
            self.board = self._snapshots.pop()
            self.san_history.pop()
            self.moves_played.pop()

        self.last_move = self.moves_played[-1] if self.moves_played else None
        self.game_over = False
        self.result_text = ""
        self.deselect()
        return True

    # ── PGN ────────────────────────────────────────────────────────────────

    def save_pgn(self, saves_dir: Path) -> Path:
        saves_dir.mkdir(parents=True, exist_ok=True)
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = "AIAjedrez"
        game.headers["Date"] = datetime.date.today().isoformat()
        filename = saves_dir / f"game_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
        with open(filename, "w") as f:
            print(game, file=f)
        log.info("Partida guardada en %s", filename)
        return filename

    # ── Internos ───────────────────────────────────────────────────────────

    def _build_move(self, from_sq: int, to_sq: int) -> chess.Move | None:
        """
        Construye el objeto Move correcto, manejando promociones automáticas
        (siempre promovemos a Reina por defecto).
        """
        for m in self.board.legal_moves:
            if m.from_square == from_sq and m.to_square == to_sq:
                if m.promotion:
                    # Hay múltiples movimientos legales (distintas promociones);
                    # elegimos automáticamente Reina.
                    return chess.Move(from_sq, to_sq, chess.QUEEN)
                return m
        return None

    def _push(self, move: chess.Move) -> chess.Move:
        self._snapshots.append(self.board.copy())   # guardar estado antes de mover
        san = self.board.san(move)
        self.board.push(move)
        self.last_move = move
        self.san_history.append(san)
        self.moves_played.append(move)
        self.deselect()
        self._check_game_over()
        return move

    def _check_game_over(self):
        b = self.board
        if b.is_checkmate():
            winner = "Negras" if b.turn == chess.WHITE else "Blancas"
            self.result_text = f"¡Jaque Mate! Ganan {winner}"
            self.game_over = True
        elif b.is_stalemate():
            self.result_text = "Ahogado — Tablas"
            self.game_over = True
        elif b.is_insufficient_material():
            self.result_text = "Material insuficiente — Tablas"
            self.game_over = True
        elif b.is_seventyfive_moves():
            self.result_text = "Regla de 75 movimientos — Tablas"
            self.game_over = True
        elif b.is_fivefold_repetition():
            self.result_text = "Repetición quíntuple — Tablas"
            self.game_over = True
