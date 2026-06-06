"""Integration: defenses, when active, flip a would-be successful attack to blocked."""
from core.model_client import FakeClient
from redteam.attacker import Attacker
from redteam.defenses import defense_for_condition
from redteam.gauntlet import run_trial
from redteam.scenarios import get_scenario
from redteam.target import TargetAdapter
from redteam.techniques import get_technique


def test_output_scan_blocks_a_canary_leak_that_would_otherwise_succeed():
    s = get_scenario("canary_vault_key")
    attacker = Attacker(FakeClient(lambda *a: "x"))
    leaking_target = TargetAdapter(FakeClient(lambda *a: s.secret))  # target always leaks

    undefended = run_trial(s, get_technique("direct_ask"), mode="single", k=5,
                           attacker=attacker, target=leaking_target)
    assert undefended.success is True  # baseline: the leak lands

    scan = defense_for_condition("prompt+classifier+scan",
                                 classifier_client=FakeClient(lambda *a: "NO"))
    defended = run_trial(s, get_technique("direct_ask"), mode="single", k=5,
                         attacker=attacker, target=leaking_target,
                         defense=scan, condition="prompt+classifier+scan")
    assert defended.success is False
    assert defended.blocked_by == "output_scan"


def test_input_classifier_blocks_before_target_is_called():
    s = get_scenario("inject_doc_summary")
    target_calls = {"n": 0}

    def target_resp(model, system, messages, max_tokens):
        target_calls["n"] += 1
        return s.secret  # if reached, it would hijack

    attacker = Attacker(FakeClient(lambda *a: "x"))
    target = TargetAdapter(FakeClient(target_resp))
    block_all = defense_for_condition("prompt+classifier",
                                      classifier_client=FakeClient(lambda *a: "YES"))
    r = run_trial(s, get_technique("instruction_override"), mode="single", k=5,
                  attacker=attacker, target=target, defense=block_all,
                  condition="prompt+classifier")
    assert r.success is False
    assert r.blocked_by == "input_classifier"
    assert target_calls["n"] == 0  # target never saw the flagged message
