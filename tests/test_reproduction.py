"""Golden test: committed per-target fixtures reproduce the committed headline numbers via the
dry-run path (zero cost). Guards against fixture/result drift across the scaled cross-model run."""
import json
from pathlib import Path

from core.model_client import RecordedClient
from core.tracing import TraceStore
from evals.run_gauntlet import assert_not_degraded, build_plan, run_plan, summarize
from redteam.scenarios import SCENARIOS
from redteam.techniques import TECHNIQUES

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "evals" / "fixtures"
MANIFEST = FIXTURES_DIR / "manifest.json"
ASR = ROOT / "evals" / "results" / "asr.json"


def test_committed_fixtures_reproduce_committed_numbers():
    if not MANIFEST.exists() or not ASR.exists():
        import pytest
        pytest.skip("scaled fixtures/results not present yet (run the live gauntlet first)")

    manifest = json.loads(MANIFEST.read_text())
    committed = json.loads(ASR.read_text())   # primary-target summary + cross_model
    primary = list(manifest["targets"])[0]

    fx = json.loads((FIXTURES_DIR / f"{primary}.json").read_text())
    plan = build_plan(SCENARIOS, TECHNIQUES, manifest["replicates"])
    store = TraceStore(":memory:")
    rid = store.new_run("repro")
    raw = run_plan(plan, RecordedClient(fx, strict=True), k=manifest["k"], trace=store,
                   run_id=rid, attacker_model=manifest["attacker_model"], target_model=primary,
                   temperature=manifest["temperature"])
    results = assert_not_degraded(raw, len(plan), manifest["n_techniques"])
    summary = summarize(results, target=primary, mode_k=manifest["k"], live=True)

    cl, gl = summary["adaptation_lift"], committed["adaptation_lift"]
    assert cl["single_asr"] == gl["single_asr"]
    assert cl["adaptive_asr"] == gl["adaptive_asr"]
    assert cl["significance"]["p_value"] == gl["significance"]["p_value"]

    cc, gc = summary["defense_curve"], committed["defense_curve"]
    assert cc["reduction_abs"] == gc["reduction_abs"]
    for cond in committed["meta"]["conditions"]:
        assert cc["by_condition"][cond]["asr"] == gc["by_condition"][cond]["asr"]
