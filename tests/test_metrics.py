"""ASR, ablations, and bootstrap CIs computed from trial results (no model calls)."""
from evals.metrics import (
    adaptation_lift,
    asr,
    asr_with_ci,
    defense_curve,
    heatmap,
    select,
)
from redteam.gauntlet import TrialResult


def _trial(scenario, technique, mode, condition, success):
    return TrialResult(scenario, technique, mode, condition, success, 1, None, [])


def test_asr_basic():
    trials = [_trial("s", "t", "single", "none", b) for b in (True, True, False, False)]
    assert asr(trials) == 0.5


def test_asr_empty_is_zero():
    assert asr([]) == 0.0


def test_asr_with_ci_returns_point_and_bounds():
    trials = [_trial("s", f"t{i}", "single", "none", i < 3) for i in range(10)]
    point, (lo, hi) = asr_with_ci(trials)
    assert point == 0.3
    assert 0.0 <= lo <= point <= hi <= 1.0


def test_select_filters_by_mode_and_condition():
    trials = [
        _trial("s", "t", "single", "none", True),
        _trial("s", "t", "adaptive", "none", True),
        _trial("s", "t", "adaptive", "prompt", False),
    ]
    assert len(select(trials, mode="adaptive")) == 2
    assert len(select(trials, mode="adaptive", condition="prompt")) == 1


def test_adaptation_lift_is_nonnegative_and_correct():
    trials = []
    # single: 2/6 succeed; adaptive: 4/6 succeed (superset) at condition none
    for i in range(6):
        trials.append(_trial("s", f"t{i}", "single", "none", i < 2))
        trials.append(_trial("s", f"t{i}", "adaptive", "none", i < 4))
    lift = adaptation_lift(trials)
    assert lift["single_asr"] == round(2 / 6, 4)
    assert lift["adaptive_asr"] == round(4 / 6, 4)
    # lift is reported from the displayed (rounded) rates so the dashboard is self-consistent
    assert lift["lift_abs"] == round(lift["adaptive_asr"] - lift["single_asr"], 4)
    assert lift["lift_abs"] > 0


def test_defense_curve_monotone_reduction():
    trials = []
    rates = {"none": 5, "prompt": 4, "prompt+classifier": 2, "prompt+classifier+scan": 0}
    for cond, k in rates.items():
        for i in range(6):
            trials.append(_trial("s", f"t{i}", "adaptive", cond, i < k))
    curve = defense_curve(trials)
    assert curve["by_condition"]["none"]["asr"] == round(5 / 6, 4)
    assert curve["by_condition"]["prompt+classifier+scan"]["asr"] == 0.0
    assert curve["reduction_abs"] == round(5 / 6 - 0.0, 4)
    # per-layer marginal contributions sum to the total reduction
    assert round(sum(curve["per_layer_marginal"].values()), 4) == curve["reduction_abs"]


def test_heatmap_one_cell_per_scenario_technique():
    trials = [
        _trial("s1", "t1", "adaptive", "none", True),
        _trial("s1", "t2", "adaptive", "none", False),
        _trial("s2", "t1", "adaptive", "none", True),
    ]
    cells = heatmap(trials, mode="adaptive", condition="none")
    by_key = {(c["scenario"], c["technique"]): c["success"] for c in cells}
    assert by_key[("s1", "t1")] is True
    assert by_key[("s1", "t2")] is False
    assert len(cells) == 3
