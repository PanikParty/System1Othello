from s1othello.analysis import auc, calibration, gate_curve, pareto


def test_auc():
    assert auc([0.9, 0.8, 0.2, 0.1], [True, True, False, False]) == 1.0
    assert auc([0.1, 0.2, 0.8, 0.9], [True, True, False, False]) == 0.0
    assert auc([0.5, 0.5], [True, False]) == 0.5
    assert auc([0.5], [True]) is None


def _row(conf, best, regret, exact=True):
    return {"confidence": conf, "is_best": best, "regret": regret, "exact": exact, "source": "model"}


def test_gate_curve_routes_low_confidence_to_search():
    model = {"a": _row(0.9, True, 0), "b": _row(0.3, False, 6), "c": _row(0.2, False, 4)}
    search = {k: _row(None, True, 0) for k in model}
    curve = {round(c["threshold"], 2): c for c in gate_curve(model, search)}
    assert curve[0.0]["search_share"] == 0 and abs(curve[0.0]["best_rate"] - 1 / 3) < 1e-9
    assert curve[0.9]["search_share"] == 2 / 3 and curve[0.9]["best_rate"] == 1.0
    front = pareto(list(curve.values()))
    assert front[0]["search_share"] == 0 and front[-1]["best_rate"] == 1.0
    cal = calibration(list(model.values()))
    assert cal["auc_best"] == 1.0
