"""Small checks on the scoring code. Run with: python3 -m pytest tests (or python3 tests/test_metrics.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dmc.common import OOS, UNWORDED, REWORDED, brier_item, descriptions, pick_threshold, policy_outcome  # noqa: E402
from dmc.evaluate import holm, mcnemar_exact, tie_groups, wilson  # noqa: E402


def row(i, label, pred, p, kind="in"):
    return {"id": i, "label": label, "pred": pred, "kind": kind, "probs": {pred: p, label: 1 - p} if pred != label else {pred: p}}


def test_brier_on_chosen_answer():
    assert abs(brier_item(row(1, "balance", "balance", 0.9)) - 0.01) < 1e-9
    assert abs(brier_item(row(2, "balance", "routing", 0.9)) - 0.81) < 1e-9


def test_threshold_never_automates_out_of_scope():
    rows = [row(1, OOS, OOS, 0.99, "near"), row(2, "balance", "balance", 0.95), row(3, OOS, "balance", 0.6, "near")]
    t = pick_threshold(rows)
    out = policy_outcome(rows, t)
    assert out["n_wrong"] == 0 and out["n_auto"] == 1 and 0.6 < t <= 0.95


def test_reworded_names_round_trip():
    shown = descriptions("base", reworded=True)
    assert [UNWORDED[k] for k in shown] == list(descriptions("base"))
    assert len(set(REWORDED.values())) == len(REWORDED)


def test_reversed_order():
    assert list(descriptions("base", reverse=True))[0] == OOS


def test_stats():
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(10, 2) - 0.0386) < 1e-3
    lo, hi = wilson(8, 400)
    assert lo < 0.02 < hi
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}


def test_tie_groups_split_a_clear_gap():
    good = [row(i, "balance", "balance", 0.9) for i in range(200)]
    bad = [row(i, "balance", "balance" if i < 100 else "routing", 0.9) for i in range(200)]
    groups = tie_groups({"good": good, "same": list(good), "bad": bad}, "all")
    assert groups[0][0] in ("good", "same") and set(groups[0]) == {"good", "same"} and groups[1] == ["bad"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
