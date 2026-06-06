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
    by_key = {(c["scenario"], c["technique"]): c for c in cells}
    assert by_key[("s1", "t1")]["asr"] == 1.0
    assert by_key[("s1", "t2")]["asr"] == 0.0
    assert all(c["n"] == 1 for c in cells)
    assert len(cells) == 3


def test_mcnemar_one_flip_is_not_significant():
    from evals.metrics import mcnemar
    trials = []
    # 5 both-success, 1 fail->success (the single discordant pair), rest both-fail
    for i in range(6):
        single = i < 5
        adaptive = i < 6  # cell 5 flips fail(single)->success(adaptive)
        trials.append(_trial("s", f"t{i}", "single", "none", single))
        trials.append(_trial("s", f"t{i}", "adaptive", "none", adaptive))
    m = mcnemar(trials)
    assert m["b_single_fail_adaptive_success"] == 1
    assert m["c_single_success_adaptive_fail"] == 0
    assert m["discordant"] == 1
    assert m["p_value"] == 1.0
    assert m["significant_at_05"] is False


def test_mcnemar_strong_effect_is_significant():
    from evals.metrics import mcnemar
    trials = []
    for i in range(12):
        # single all fail; adaptive succeeds on 10 of them -> b=10, c=0, p<0.05
        trials.append(_trial("s", f"t{i}", "single", "none", False))
        trials.append(_trial("s", f"t{i}", "adaptive", "none", i < 10))
    m = mcnemar(trials)
    assert m["b_single_fail_adaptive_success"] == 10
    assert m["c_single_success_adaptive_fail"] == 0
    assert m["significant_at_05"] is True


def test_adaptation_lift_includes_significance():
    trials = []
    for i in range(6):
        trials.append(_trial("s", f"t{i}", "single", "none", i < 2))
        trials.append(_trial("s", f"t{i}", "adaptive", "none", i < 4))
    lift = adaptation_lift(trials)
    assert "significance" in lift
    assert "p_value" in lift["significance"]



def test_heatmap_aggregates_replicates():
    from evals.metrics import heatmap
    # same cell, 3 replicates: 2 success -> asr 0.667
    trials = [
        _trial("s1", "t1", "adaptive", "none", r < 2) for r in range(3)
    ]
    for r, tr in enumerate(trials):
        tr.replicate = r
    cells = heatmap(trials, mode="adaptive", condition="none")
    assert len(cells) == 1
    assert cells[0]["n"] == 3
    assert cells[0]["successes"] == 2
    assert cells[0]["asr"] == round(2 / 3, 4)


def test_mcnemar_pairs_within_replicate():
    from evals.metrics import mcnemar
    # one cell, 2 replicates. rep0: single F, adaptive T (discordant b). rep1: both T.
    trials = []
    for r, (sg, ad) in enumerate([(False, True), (True, True)]):
        trials.append(_trial("s", "t", "single", "none", sg))
        trials.append(_trial("s", "t", "adaptive", "none", ad))
        trials[-1].replicate = r
        trials[-2].replicate = r
    m = mcnemar(trials)
    assert m["b_single_fail_adaptive_success"] == 1
    assert m["c_single_success_adaptive_fail"] == 0
    assert m["discordant"] == 1


def test_two_proportion_p_significant_and_not():
    from evals.metrics import two_proportion_p
    # 30/36 vs 3/36 -> clearly different
    assert two_proportion_p(30, 36, 3, 36) < 0.05
    # 18/36 vs 17/36 -> not different
    assert two_proportion_p(18, 36, 17, 36) > 0.05


def test_cross_model_compare_shape():
    from evals.metrics import cross_model_compare
    A = [_trial("inject_x", "t", "adaptive", "none", True) for _ in range(6)]
    B = [_trial("inject_x", "t", "adaptive", "none", False) for _ in range(6)]
    cmp = cross_model_compare({"model_a": A, "model_b": B})
    assert cmp["targets"] == ["model_a", "model_b"]
    inj = next(r for r in cmp["rows"] if "Injection" in r["label"])
    assert inj["by_target"]["model_a"]["asr"] == 1.0
    assert inj["by_target"]["model_b"]["asr"] == 0.0
    assert "p_value" in inj
