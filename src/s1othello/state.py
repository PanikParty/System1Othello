"""Board -> the protocol `state` the model sees, and the single `move` choice question.

    {"state": {"rules": "...", "you_play": "black", "board": {"1": "........", ...}, ...},
     "questions": {"move": {"type": "choice", "instructions": "...",
                            "criteria": {"D3": "Place a black disc at D3", ...}}}}

Code computes the geometry (legal moves, and in prompt v2 per-move facts); the model only
ever picks one of the options it is handed. Text lives in prompts/<version>/questions.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from s1othello.engine import Board, apply_move, coord_to_rc, disc_counts, empties, legal_moves, other

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
COLOUR = {"B": "black", "W": "white"}
CORNERS = {"A1", "H1", "A8", "H8"}
# x-square / c-squares -> the corner they sit next to
X_SQUARES = {"B2": "A1", "G2": "H1", "B7": "A8", "G7": "H8"}
C_SQUARES = {"B1": "A1", "A2": "A1", "G1": "H1", "H2": "H1",
             "A7": "A8", "B8": "A8", "H7": "H8", "G8": "H8"}


@dataclass(frozen=True)
class PromptSet:
    version: str
    rules: str
    spec: dict

    @classmethod
    def load(cls, version: str = "v1") -> "PromptSet":
        d = yaml.safe_load((PROMPTS_DIR / version / "questions.yaml").read_text())
        return cls(d["version"], d["rules"].strip(), d["questions"])


def _empty(board: Board, coord: str) -> bool:
    r, c = coord_to_rc(coord)
    return board[r][c] == "."


def square_kind(board: Board, move: str) -> str:
    if move in CORNERS:
        return "corner"
    if move in X_SQUARES and _empty(board, X_SQUARES[move]):
        return "x-square"
    if move in C_SQUARES and _empty(board, C_SQUARES[move]):
        return "c-square"
    if move[0] in "AH" or move[1] in "18":
        return "edge"
    return "inner"


def move_features(board: Board, player: str, move: str) -> dict:
    """Facts about one legal move, computed by the engine (prompt v2's option text)."""
    after = apply_move(board, player, move)
    mine_before = disc_counts(board)[0 if player == "B" else 1]
    mine_after = disc_counts(after)[0 if player == "B" else 1]
    replies = legal_moves(after, other(player))
    return {
        "move": move,
        "flips": mine_after - mine_before - 1,
        "square": square_kind(board, move),
        "opponent_replies": len(replies),
        "opponent_gets_corner": any(m in CORNERS for m in replies),
        "opponent_passes": not replies,
    }


def build_state(ps: PromptSet, board: Board, player: str, include_rules: bool = True) -> dict:
    b, w = disc_counts(board)
    state: dict = {}
    if include_rules:
        state["rules"] = ps.rules
    state.update({
        "you_play": COLOUR[player],
        "board": {str(i + 1): row for i, row in enumerate(board)},
        "discs": {"black": b, "white": w},
        "empty_squares": empties(board),
    })
    return state


def build_questions(ps: PromptSet, board: Board, player: str, moves: list[str]) -> dict:
    spec = ps.spec["move"]
    colour = COLOUR[player]
    tpl = spec["option_template"]
    criteria = {m: tpl.format(colour=colour, **move_features(board, player, m)).strip() for m in moves}
    return {"move": {"type": "choice", "instructions": spec["instructions"].format(colour=colour).strip(),
                     "criteria": criteria}}


def state_and_questions(ps: PromptSet, board: Board, player: str) -> tuple[dict, dict, list[str]]:
    moves = legal_moves(board, player)
    return build_state(ps, board, player), build_questions(ps, board, player, moves), moves
