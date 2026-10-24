"""Board -> protocol JSON (the `state` the model sees) and the single `move`
choice question (the `questions` dict), matching the design doc's example:

    {"state": {"board": [...8 rows...], "current_player": "B"},
     "questions": {"move": {"type": "choice", "criteria": {"D3": "...", ...}}}}

Code computes the geometry (legal moves); the model only ever picks one of
the options it is handed. See PLAN.md.
"""
from __future__ import annotations

from s1othello.engine import Board, legal_moves


def build_state(board: Board, player: str) -> dict:
    return {"board": list(board), "current_player": player}


def build_questions(moves: list[str]) -> dict:
    return {
        "move": {
            "type": "choice",
            "criteria": {m: f"Place a disc at {m}" for m in moves},
        }
    }


def state_and_questions(board: Board, player: str) -> tuple[dict, dict, list[str]]:
    moves = legal_moves(board, player)
    return build_state(board, player), build_questions(moves), moves
