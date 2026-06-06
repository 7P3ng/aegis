"""The gauntlet drives attacker<->target up to K turns, scores deterministically, traces
every turn, and stops early on success. All on fakes — zero paid calls."""
from core.model_client import FakeClient
from core.tracing import TraceStore
from redteam.attacker import Attacker
from redteam.gauntlet import run_trial
from redteam.scenarios import get_scenario
from redteam.target import TargetAdapter
from redteam.techniques import get_technique


def _leak_on_turn0_target(secret):
    return FakeClient(lambda model, system, messages, max_tokens: secret)


def test_single_turn_success_when_target_leaks_immediately():
    s = get_scenario("canary_vault_key")
    attacker = Attacker(FakeClient(lambda *a: "unused"))
    target = TargetAdapter(_leak_on_turn0_target(s.secret))
    r = run_trial(s, get_technique("direct_ask"), mode="single", k=5,
                  attacker=attacker, target=target)
    assert r.success is True
    assert r.turns_used == 1


def test_adaptive_beats_single_when_leak_needs_escalation():
    s = get_scenario("canary_vault_key")

    def target_resp(model, system, messages, max_tokens):
        user = messages[-1]["content"]
        return s.secret if "ESCALATE" in user else "I refuse to share that."

    def attacker_resp(model, system, messages, max_tokens):
        return "ESCALATE now please"  # only used on turns > 0

    attacker = Attacker(FakeClient(attacker_resp))
    target = TargetAdapter(FakeClient(target_resp))

    single = run_trial(s, get_technique("direct_ask"), mode="single", k=5,
                       attacker=attacker, target=target)
    adaptive = run_trial(s, get_technique("direct_ask"), mode="adaptive", k=5,
                         attacker=attacker, target=target)
    assert single.success is False
    assert adaptive.success is True
    assert adaptive.turns_used == 2  # turn0 refused, turn1 escalated and leaked


def test_early_stop_does_not_exceed_turns_on_success():
    s = get_scenario("canary_vault_key")
    attacker = Attacker(FakeClient(lambda *a: "x"))
    target = TargetAdapter(_leak_on_turn0_target(s.secret))
    r = run_trial(s, get_technique("direct_ask"), mode="adaptive", k=5,
                  attacker=attacker, target=target)
    assert r.success is True
    assert r.turns_used == 1  # stopped at first success, did not run all 5


def test_trace_records_a_span_per_turn_with_attrs():
    s = get_scenario("canary_vault_key")
    store = TraceStore(":memory:")
    run_id = store.new_run("test")
    attacker = Attacker(FakeClient(lambda *a: "x"))
    target = TargetAdapter(_leak_on_turn0_target(s.secret))
    run_trial(s, get_technique("direct_ask"), mode="single", k=5,
              attacker=attacker, target=target, trace=store, run_id=run_id)
    spans = store.query(run_id)
    assert spans, "expected at least one span"
    turn_spans = [sp for sp in spans if sp["name"] == "turn"]
    assert turn_spans
    assert turn_spans[0]["attrs"]["scenario"] == s.id
    assert turn_spans[0]["attrs"]["technique"] == "direct_ask"


def test_transcript_captured():
    s = get_scenario("inject_doc_summary")
    attacker = Attacker(FakeClient(lambda *a: "x"))
    target = TargetAdapter(FakeClient(lambda *a: "harmless summary"))
    r = run_trial(s, get_technique("direct_ask"), mode="single", k=5,
                  attacker=attacker, target=target)
    assert len(r.transcript) == 1
    assert r.transcript[0].target == "harmless summary"
    assert r.success is False
