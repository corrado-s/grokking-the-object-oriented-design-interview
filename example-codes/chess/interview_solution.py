"""
Design Chess -- Interview-Feasible Solution
============================================

Assumptions / Reduced Scope:
    - Two-player, local (non-networked) chess on a standard 8x8 board.
    - White always moves first; players alternate turns.
    - No account system, admin roles, or player registration.

Main Use Cases Implemented:
    1. Initialize the board with all 32 pieces in standard positions.
    2. Players take turns entering moves (algebraic notation, e.g. "e2 e4").
    3. Validate that a move is legal for the selected piece type.
    4. Enforce turn alternation and prevent moving the opponent's pieces.
    5. Detect check -- a move that leaves your own king in check is rejected.
    6. Detect checkmate and stalemate to end the game.
    7. Allow a player to resign.

What Was Left Out:
    - Castling, en passant, pawn promotion.
    - Full console rendering with ANSI colors (simple text board instead).
    - Move history / undo / replay.
    - Timers, logging, GameView / GameController separation.
    - Network play, accounts, persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class Color(Enum):
    WHITE = "white"
    BLACK = "black"


class GameStatus(Enum):
    ACTIVE_WHITE = "white_to_move"
    ACTIVE_BLACK = "black_to_move"
    WHITE_WINS = "white_wins"
    BLACK_WINS = "black_wins"
    STALEMATE = "stalemate"
    FORFEIT = "forfeit"


class PieceType(Enum):
    KING = "K"
    QUEEN = "Q"
    ROOK = "R"
    BISHOP = "B"
    KNIGHT = "N"
    PAWN = "P"


BOARD_SIZE = 8


# ---------------------------------------------------------------------------
# Position & Move
# ---------------------------------------------------------------------------

class Position:
    """A square on the board, 0-indexed (col=x, row=y)."""

    __slots__ = ("col", "row")

    def __init__(self, col: int, row: int) -> None:
        self.col = col
        self.row = row

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.col == other.col and self.row == other.row

    def __hash__(self) -> int:
        return hash((self.col, self.row))

    def __repr__(self) -> str:
        return f"{chr(ord('a') + self.col)}{self.row + 1}"

    def in_bounds(self) -> bool:
        return 0 <= self.col < BOARD_SIZE and 0 <= self.row < BOARD_SIZE

    @staticmethod
    def from_algebraic(s: str) -> Optional[Position]:
        if len(s) < 2:
            return None
        col = ord(s[0]) - ord("a")
        try:
            row = int(s[1:]) - 1
        except ValueError:
            return None
        pos = Position(col, row)
        return pos if pos.in_bounds() else None


class Move:
    """Represents a single move from src to dst."""

    def __init__(self, src: Position, dst: Position) -> None:
        self.src = src
        self.dst = dst

    def __repr__(self) -> str:
        return f"{self.src} -> {self.dst}"

    @staticmethod
    def from_string(text: str) -> Optional[Move]:
        tokens = text.strip().split()
        if len(tokens) != 2:
            return None
        src = Position.from_algebraic(tokens[0])
        dst = Position.from_algebraic(tokens[1])
        if src is None or dst is None:
            return None
        return Move(src, dst)


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player:
    def __init__(self, name: str, color: Color) -> None:
        self.name = name
        self.color = color

    def __repr__(self) -> str:
        return f"{self.name} ({self.color.value})"


# ---------------------------------------------------------------------------
# Piece hierarchy
# ---------------------------------------------------------------------------

class Piece(ABC):
    """Abstract base for all chess pieces."""

    def __init__(self, color: Color, piece_type: PieceType) -> None:
        self.color = color
        self.piece_type = piece_type

    @abstractmethod
    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        """Return every square this piece could move to (pseudo-legal)."""

    def symbol(self) -> str:
        s = self.piece_type.value
        return s if self.color == Color.WHITE else s.lower()

    def __repr__(self) -> str:
        return f"{self.color.value[0].upper()}{self.piece_type.value}"

    # -- helpers used by sliding pieces (Rook, Bishop, Queen) --

    def _slide(self, pos: Position, board: Board,
               directions: list[tuple[int, int]]) -> list[Position]:
        targets: list[Position] = []
        for dc, dr in directions:
            c, r = pos.col + dc, pos.row + dr
            while 0 <= c < BOARD_SIZE and 0 <= r < BOARD_SIZE:
                dest = Position(c, r)
                occupant = board.get_piece(dest)
                if occupant is None:
                    targets.append(dest)
                else:
                    if occupant.color != self.color:
                        targets.append(dest)  # capture
                    break  # blocked
                c += dc
                r += dr
        return targets

    def _spot(self, pos: Position, board: Board,
              offsets: list[tuple[int, int]]) -> list[Position]:
        targets: list[Position] = []
        for dc, dr in offsets:
            dest = Position(pos.col + dc, pos.row + dr)
            if not dest.in_bounds():
                continue
            occupant = board.get_piece(dest)
            if occupant is None or occupant.color != self.color:
                targets.append(dest)
        return targets


class King(Piece):
    OFFSETS = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]

    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.KING)

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        return self._spot(pos, board, self.OFFSETS)


class Queen(Piece):
    DIRECTIONS = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]

    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.QUEEN)

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        return self._slide(pos, board, self.DIRECTIONS)


class Rook(Piece):
    DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.ROOK)

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        return self._slide(pos, board, self.DIRECTIONS)


class Bishop(Piece):
    DIRECTIONS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.BISHOP)

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        return self._slide(pos, board, self.DIRECTIONS)


class Knight(Piece):
    OFFSETS = [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2),
    ]

    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.KNIGHT)

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        return self._spot(pos, board, self.OFFSETS)


class Pawn(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.PAWN)
        self.has_moved = False

    def get_valid_targets(self, pos: Position, board: Board) -> list[Position]:
        targets: list[Position] = []
        direction = 1 if self.color == Color.WHITE else -1

        # one square forward
        one = Position(pos.col, pos.row + direction)
        if one.in_bounds() and board.get_piece(one) is None:
            targets.append(one)
            # two squares forward from starting row
            if not self.has_moved:
                two = Position(pos.col, pos.row + 2 * direction)
                if two.in_bounds() and board.get_piece(two) is None:
                    targets.append(two)

        # diagonal captures
        for dc in (-1, 1):
            diag = Position(pos.col + dc, pos.row + direction)
            if diag.in_bounds():
                occupant = board.get_piece(diag)
                if occupant is not None and occupant.color != self.color:
                    targets.append(diag)

        return targets


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class Board:
    """8x8 grid.  squares[row][col] holds an Optional[Piece]."""

    def __init__(self) -> None:
        self.squares: list[list[Optional[Piece]]] = [
            [None] * BOARD_SIZE for _ in range(BOARD_SIZE)
        ]
        self._setup_pieces()

    # -- query --

    def get_piece(self, pos: Position) -> Optional[Piece]:
        return self.squares[pos.row][pos.col]

    def find_king(self, color: Color) -> Position:
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = self.squares[r][c]
                if p and p.piece_type == PieceType.KING and p.color == color:
                    return Position(c, r)
        raise RuntimeError(f"No {color.value} king on the board")

    # -- mutation --

    def apply_move(self, move: Move) -> Optional[Piece]:
        """Move piece from src to dst. Returns captured piece or None."""
        piece = self.get_piece(move.src)
        captured = self.get_piece(move.dst)
        self.squares[move.dst.row][move.dst.col] = piece
        self.squares[move.src.row][move.src.col] = None
        if isinstance(piece, Pawn):
            piece.has_moved = True
        return captured

    # -- check detection --

    def is_in_check(self, color: Color) -> bool:
        king_pos = self.find_king(color)
        opponent = Color.BLACK if color == Color.WHITE else Color.WHITE
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = self.squares[r][c]
                if p and p.color == opponent:
                    if king_pos in p.get_valid_targets(Position(c, r), self):
                        return True
        return False

    def has_any_legal_move(self, color: Color) -> bool:
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = self.squares[r][c]
                if p and p.color == color:
                    src = Position(c, r)
                    for dst in p.get_valid_targets(src, self):
                        if self._is_legal(Move(src, dst), color):
                            return True
        return False

    def _is_legal(self, move: Move, color: Color) -> bool:
        """A move is legal if it does not leave one's own king in check."""
        sim = deepcopy(self)
        sim.apply_move(move)
        return not sim.is_in_check(color)

    # -- display --

    def display(self) -> str:
        lines: list[str] = []
        for r in reversed(range(BOARD_SIZE)):
            row_str = f"{r + 1} "
            for c in range(BOARD_SIZE):
                p = self.squares[r][c]
                row_str += p.symbol() if p else "."
                row_str += " "
            lines.append(row_str)
        lines.append("  " + " ".join("abcdefgh"))
        return "\n".join(lines)

    # -- initial setup --

    def _setup_pieces(self) -> None:
        back_rank = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]
        for col, cls in enumerate(back_rank):
            self.squares[0][col] = cls(Color.WHITE)
            self.squares[7][col] = cls(Color.BLACK)
        for col in range(BOARD_SIZE):
            self.squares[1][col] = Pawn(Color.WHITE)
            self.squares[6][col] = Pawn(Color.BLACK)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    """Orchestrates turns, validation, and win/draw detection."""

    def __init__(self, white: Player, black: Player) -> None:
        self.board = Board()
        self.players = {Color.WHITE: white, Color.BLACK: black}
        self.status = GameStatus.ACTIVE_WHITE
        self.move_count = 0

    @property
    def current_color(self) -> Color:
        return Color.WHITE if self.status == GameStatus.ACTIVE_WHITE else Color.BLACK

    @property
    def current_player(self) -> Player:
        return self.players[self.current_color]

    def is_over(self) -> bool:
        return self.status not in (GameStatus.ACTIVE_WHITE, GameStatus.ACTIVE_BLACK)

    # -- core move logic --

    def make_move(self, move: Move) -> tuple[bool, str]:
        """Attempt a move. Returns (success, message)."""
        if self.is_over():
            return False, f"Game is already over: {self.status.value}"

        color = self.current_color
        piece = self.board.get_piece(move.src)

        if piece is None:
            return False, "No piece at source square."
        if piece.color != color:
            return False, "That piece belongs to your opponent."
        if move.dst not in piece.get_valid_targets(move.src, self.board):
            return False, "Illegal move for this piece."

        # simulate to check legality (must not leave own king in check)
        sim_board = deepcopy(self.board)
        sim_board.apply_move(move)
        if sim_board.is_in_check(color):
            return False, "Move leaves your king in check."

        # commit the move
        captured = self.board.apply_move(move)
        self.move_count += 1
        cap_msg = f" Captures {captured}!" if captured else ""

        # switch turn and evaluate position
        self._switch_turn()
        result_msg = self._evaluate_position()

        return True, f"{color.value.capitalize()} plays {move}.{cap_msg}{result_msg}"

    def resign(self) -> str:
        winner = Color.BLACK if self.current_color == Color.WHITE else Color.WHITE
        self.status = GameStatus.FORFEIT
        return f"{self.current_player.name} resigns. {self.players[winner].name} wins!"

    # -- internals --

    def _switch_turn(self) -> None:
        if self.status == GameStatus.ACTIVE_WHITE:
            self.status = GameStatus.ACTIVE_BLACK
        else:
            self.status = GameStatus.ACTIVE_WHITE

    def _evaluate_position(self) -> str:
        """Check for checkmate or stalemate after the turn switches."""
        color = self.current_color
        in_check = self.board.is_in_check(color)
        has_moves = self.board.has_any_legal_move(color)

        if in_check and not has_moves:
            winner = Color.BLACK if color == Color.WHITE else Color.WHITE
            self.status = (GameStatus.WHITE_WINS
                           if winner == Color.WHITE else GameStatus.BLACK_WINS)
            return f" Checkmate! {self.players[winner].name} wins!"
        if not in_check and not has_moves:
            self.status = GameStatus.STALEMATE
            return " Stalemate -- game is a draw."
        if in_check:
            return f" {color.value.capitalize()} is in check!"
        return ""


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    white_player = Player("Alice", Color.WHITE)
    black_player = Player("Bob", Color.BLACK)
    game = Game(white_player, black_player)

    print("=== Chess (interview demo) ===\n")
    print(game.board.display())
    print()

    # Scholar's Mate sequence to demonstrate checkmate detection
    scripted_moves = [
        "e2 e4",   # White pawn
        "e7 e5",   # Black pawn
        "f1 c4",   # White bishop
        "b8 c6",   # Black knight
        "d1 h5",   # White queen
        "g8 f6",   # Black knight (fails to block)
        "h5 f7",   # White queen delivers checkmate
    ]

    for move_str in scripted_moves:
        move = Move.from_string(move_str)
        if move is None:
            print(f"Bad input: {move_str}")
            continue
        print(f"{game.current_player} tries {move_str}")
        ok, msg = game.make_move(move)
        print(f"  {'OK' if ok else 'FAIL'}: {msg}")
        if ok:
            print()
            print(game.board.display())
            print()
        if game.is_over():
            print(f"\nFinal status: {game.status.value}")
            break
