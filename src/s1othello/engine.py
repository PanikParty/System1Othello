"""Othello (Reversi) rules engine.

Board is an 8x8 tuple of strings, each row 8 chars from {'.', 'B', 'W'}.
Coordinates use algebraic notation: column letter A-H, row number 1-8 (A1 is
board[0][0], top-left -- matches the example in PLAN.md / the design doc).

Rule: code computes the geometry (legal moves, flips, terminal state).
The model only ever judges between legal options it is handed.
"""
from __future__ import annotations

from dataclasses import dataclass

Board = tuple[str, ...]  # 8 rows of 8 chars
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
COLS = "ABCDEFGH"


def other(player: str) -> str:
    return "W" if player == "B" else "B"


def initial_board() -> Board:
    rows = [["."] * 8 for _ in range(8)]
    rows[3][3], rows[3][4] = "W", "B"
    rows[4][3], rows[4][4] = "B", "W"
    return tuple("".join(r) for r in rows)


def coord_to_rc(coord: str) -> tuple[int, int]:
    col = COLS.index(coord[0].upper())
    row = int(coord[1:]) - 1
    return row, col


def rc_to_coord(r: int, c: int) -> str:
    return f"{COLS[c]}{r + 1}"


def _in_bounds(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8


def _flips_for(board: Board, player: str, r: int, c: int) -> list[tuple[int, int]]:
    if board[r][c] != ".":
        return []
    opp = other(player)
    flips: list[tuple[int, int]] = []
    for dr, dc in DIRS:
        line: list[tuple[int, int]] = []
        rr, cc = r + dr, c + dc
        while _in_bounds(rr, cc) and board[rr][cc] == opp:
            line.append((rr, cc))
            rr, cc = rr + dr, cc + dc
        if line and _in_bounds(rr, cc) and board[rr][cc] == player:
            flips.extend(line)
    return flips


def legal_moves(board: Board, player: str) -> list[str]:
    moves = []
    for r in range(8):
        for c in range(8):
            if _flips_for(board, player, r, c):
                moves.append(rc_to_coord(r, c))
    return sorted(moves, key=lambda m: (m[1], m[0]))


def apply_move(board: Board, player: str, coord: str) -> Board:
    r, c = coord_to_rc(coord)
    flips = _flips_for(board, player, r, c)
    if not flips:
        raise ValueError(f"illegal move {coord} for {player}")
    rows = [list(row) for row in board]
    rows[r][c] = player
    for fr, fc in flips:
        rows[fr][fc] = player
    return tuple("".join(row) for row in rows)


def has_any_legal_move(board: Board, player: str) -> bool:
    for r in range(8):
        for c in range(8):
            if _flips_for(board, player, r, c):
                return True
    return False


def is_terminal(board: Board) -> bool:
    return not has_any_legal_move(board, "B") and not has_any_legal_move(board, "W")


def disc_counts(board: Board) -> tuple[int, int]:
    flat = "".join(board)
    return flat.count("B"), flat.count("W")


def empties(board: Board) -> int:
    return "".join(board).count(".")


def winner(board: Board) -> str | None:
    b, w = disc_counts(board)
    if b > w:
        return "B"
    if w > b:
        return "W"
    return None  # draw


@dataclass(frozen=True)
class Position:
    board: Board
    to_move: str  # "B" or "W", or "" if both must pass (terminal)

    @staticmethod
    def start() -> "Position":
        return Position(initial_board(), "B")

    def legal(self) -> list[str]:
        return legal_moves(self.board, self.to_move)

    def step(self, coord: str) -> "Position":
        """Apply a move, then resolve pass/terminal to find the next mover."""
        new_board = apply_move(self.board, self.to_move, coord)
        nxt = other(self.to_move)
        if has_any_legal_move(new_board, nxt):
            return Position(new_board, nxt)
        if has_any_legal_move(new_board, self.to_move):
            return Position(new_board, self.to_move)  # opponent passes
        return Position(new_board, "")  # terminal, both pass

    def is_terminal(self) -> bool:
        return self.to_move == ""
