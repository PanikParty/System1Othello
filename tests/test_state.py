from s1othello.engine import apply_move, initial_board
from s1othello.state import PromptSet, build_state, move_features, square_kind, state_and_questions


def test_prompt_sets_load():
    for v in ("v1", "v2"):
        ps = PromptSet.load(v)
        assert ps.version == v and "Othello" in ps.rules and "option_template" in ps.spec["move"]


def test_questions_offer_exactly_the_legal_moves(ps):
    state, q, moves = state_and_questions(ps, initial_board(), "B")
    assert list(q["move"]["criteria"]) == moves == ["D3", "C4", "F5", "E6"]
    assert q["move"]["type"] == "choice" and "black" in q["move"]["instructions"]
    assert state["you_play"] == "black" and state["board"]["4"] == "...WB..."
    assert state["rules"] == ps.rules and state["empty_squares"] == 60


def test_v2_features():
    b = initial_board()
    f = move_features(b, "B", "D3")
    assert f == {"move": "D3", "flips": 1, "square": "inner", "opponent_replies": 3,
                 "opponent_gets_corner": False, "opponent_passes": False}
    ps = PromptSet.load("v2")
    _, q, _ = state_and_questions(ps, b, "B")
    assert q["move"]["criteria"]["D3"].startswith("D3: flips=1, square=inner")
    assert "\n" not in q["move"]["criteria"]["D3"]


def test_square_kinds():
    b = initial_board()
    assert square_kind(b, "A1") == "corner"
    assert square_kind(b, "B2") == "x-square"
    assert square_kind(b, "B1") == "c-square"
    assert square_kind(b, "D1") == "edge"
    assert square_kind(b, "D3") == "inner"
    b2 = ("B" + b[0][1:],) + b[1:]  # corner taken: B2 is no longer an x-square
    assert square_kind(b2, "B2") == "inner"
    assert apply_move(b, "B", "D3")
