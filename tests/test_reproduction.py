"""Golden test: the committed fixtures reproduce the committed headline ASR numbers via the
dry-run path (zero cost). Guards against fixture/result drift — if either changes without the
other, this fails."""
import json
from pathlib import Path

from core.model_client import RecordedClient
from core.tracing import TraceStore
from evals.run_gauntlet import (
    assert_not_degraded,
    build_plan,
    run_plan,
    summarize,
)
from redteam.scenarios import SCENARIOS
from redteam.techniques import TECHNIQUES

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures" / "deepseek.json"
RESULTS = ROOT / "evals" / "results" / "asr.json"


def test_committed_fixtures_reproduce_committed_numbers():
    if not FIXTURES.exists() or not RESULTS.exists():
        import pytest
        pytest.skip("live fixtures/results not present yet (run the live gauntlet first)")

    fixtures = json.loads(FIXTURES.read_text())
    committed = json.loads(RESULTS.read_text())
    k = committed["meta"]["k"]

    client = RecordedClient(fixtures, strict=True)
    plan = build_plan(SCENARIOS, TECHNIQUES)
    store = TraceStore(":memory:")
    rid = store.new_run("repro")
    raw = run_plan(plan, client, k=k, trace=store, run_id=rid)
    results = assert_not_degraded(raw, len(plan), len(TECHNIQUES))
    summary = summarize(results, target=committed["meta"]["target"], mode_k=k, live=False)

    cl, gl = summary["adaptation_lift"], committed["adaptation_lift"]
    assert cl["single_asr"] == gl["single_asr"]
    assert cl["adaptive_asr"] == gl["adaptive_asr"]
    assert cl["lift_abs"] == gl["lift_abs"]

    cc, gc = summary["defense_curve"], committed["defense_curve"]
    assert cc["reduction_abs"] == gc["reduction_abs"]
    for cond in committed["meta"]["conditions"]:
        assert cc["by_condition"][cond]["asr"] == gc["by_condition"][cond]["asr"]
