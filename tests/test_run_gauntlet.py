"""Harness tests: record->replay reproduction, cost gate, and the degraded-run guard.
All on a deterministic fake — zero paid calls."""
import re

import pytest

from core.model_client import RecordedClient
from core.tracing import TraceStore
from evals import run_gauntlet as G
from redteam.gauntlet import TrialResult

_CANARY_RE = re.compile(r"AEGIS-CANARY-[A-Z0-9-]+")
_SENT_RE = re.compile(r"SENTINEL-AEGIS-[A-Z0-9-]+")


def _deterministic_model(model, system, messages, max_tokens):
    """A fake that plays attacker/classifier/target deterministically, with some leaks."""
    user = messages[-1]["content"] if messages else ""
    if "automated red-team attacker" in system:
        return "Let me try a different framing to get the secret."
    if "security input filter" in system:
        return "NO"  # never blocks, so classifier condition still exercises the target
    # target turn
    canary = _CANARY_RE.search(system)
    if canary:
        return canary.group(0) if len(user) % 2 == 0 else "I cannot reveal that secret."
    sent = _SENT_RE.search(user)
    if sent:
        return sent.group(0) if len(user) % 2 == 1 else "Here is a faithful summary."
    return "Here is a faithful, safe summary."


class _Fake:
    def complete(self, *, model, system, messages, max_tokens, temperature=0.0, salt=""):
        from core.model_client import FakeClient
        return FakeClient(_deterministic_model).complete(
            model=model, system=system, messages=messages, max_tokens=max_tokens,
            temperature=temperature, salt=salt,
        )


def _run(client, k=2):
    plan = G.build_plan(G.SCENARIOS, G.TECHNIQUES)
    store = TraceStore(":memory:")
    rid = store.new_run("t")
    results = G.run_plan(plan, client, k=k, trace=store, run_id=rid)
    return plan, results


def test_record_then_replay_reproduces_summary():
    rec = G.RecordingClient(_Fake())
    plan, live_results = _run(rec)
    live_summary = G.summarize(live_results, target="deepseek", mode_k=2, live=True)

    replay = RecordedClient(rec.fixtures, strict=True)
    _, dry_results = _run(replay)
    dry_summary = G.summarize(dry_results, target="deepseek", mode_k=2, live=False)

    assert dry_summary["adaptation_lift"] == live_summary["adaptation_lift"]
    assert dry_summary["defense_curve"] == live_summary["defense_curve"]


def test_run_actually_exercises_model_and_has_signal():
    rec = G.RecordingClient(_Fake())
    plan, results = _run(rec)
    summary = G.summarize(results, target="deepseek", mode_k=2, live=True)
    assert summary["meta"]["n_trials"] == len(plan)
    # the deterministic fake leaks on some cells, so ASR is strictly between 0 and 1
    assert 0.0 < summary["adaptation_lift"]["adaptive_asr"] < 1.0


def test_estimate_is_positive_and_model_aware():
    plan = G.build_plan(G.SCENARIOS, G.TECHNIQUES)  # n=1 baseline
    vpro = G.estimate_cost(plan, 2, target_model="deepseek-v4-pro", attacker_model="deepseek-chat")
    gpt = G.estimate_cost(plan, 2, target_model="gpt-4o-mini", attacker_model="deepseek-chat")
    assert vpro > 0 and gpt > 0
    assert gpt < vpro  # a cheaper, non-reasoning target costs less to estimate


def test_replicates_scale_the_plan():
    base = G.build_plan(G.SCENARIOS, G.TECHNIQUES, replicates=1)
    trip = G.build_plan(G.SCENARIOS, G.TECHNIQUES, replicates=3)
    assert len(trip) == 3 * len(base)
    assert {sp.replicate for sp in trip} == {0, 1, 2}


def test_degraded_guard_trips_on_missing_trials():
    with pytest.raises(SystemExit):
        G.assert_not_degraded([], expected_trials=10, n_techniques=12)


def test_degraded_guard_trips_on_all_empty_responses():
    from redteam.gauntlet import Turn
    empty = [
        TrialResult("s", t, "single", "none", False, 1, None, [Turn("a", "", False)])
        for t in ("t1", "t2")
    ]
    with pytest.raises(SystemExit):
        G.assert_not_degraded(empty, expected_trials=2, n_techniques=2)


def test_degraded_guard_passes_real_zero_with_nonempty_responses():
    from redteam.gauntlet import Turn
    real_zero = [
        TrialResult("s", t, "single", "none", False, 1, None, [Turn("a", "I refuse.", False)])
        for t in ("t1", "t2")
    ]
    G.assert_not_degraded(real_zero, expected_trials=2, n_techniques=2)  # no raise



def test_degraded_guard_tolerates_rare_empties():
    from redteam.gauntlet import Turn
    trials = [
        TrialResult("s", f"t{i}", "single", "none", False, 1, None, [Turn("a", "I refuse.", False)])
        for i in range(40)
    ]
    # one trial all-empty = 1/40 = 2.5% <= 5% threshold -> tolerated, not aborted
    trials[0].transcript = [Turn("a", "", False)]
    G.assert_not_degraded(trials, expected_trials=40, n_techniques=40)  # no raise
