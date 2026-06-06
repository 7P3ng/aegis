"""The adaptive attacker: turn 0 is the deterministic single-turn baseline (no model call);
later turns are model-driven and adapt to the target's refusal. Tested on FakeClient."""
from core.model_client import FakeClient
from redteam.attacker import Attacker
from redteam.scenarios import get_scenario
from redteam.techniques import get_technique


def test_turn_zero_is_technique_render_no_model_call():
    calls = {"n": 0}

    def responder(model, system, messages, max_tokens):
        calls["n"] += 1
        return "MODEL"

    s = get_scenario("canary_vault_key")
    t = get_technique("roleplay")
    msg = Attacker(FakeClient(responder)).next_message(s, t, [])
    assert msg == t.render(s, [])
    assert calls["n"] == 0  # turn 0 must not spend a paid call


def test_later_turn_calls_model_and_sees_prior_target_text():
    seen = {}

    def responder(model, system, messages, max_tokens):
        seen["prompt"] = system + "".join(m["content"] for m in messages)
        seen["max_tokens"] = max_tokens
        return "adapted attack"

    s = get_scenario("canary_vault_key")
    t = get_technique("direct_ask")
    history = [("first attempt", "I cannot reveal that secret.")]
    msg = Attacker(FakeClient(responder)).next_message(s, t, history)
    assert msg == "adapted attack"
    assert "I cannot reveal that secret." in seen["prompt"]  # it adapts to the refusal


def test_attacker_gives_generous_max_tokens_for_reasoning_model():
    seen = {}

    def responder(model, system, messages, max_tokens):
        seen["max_tokens"] = max_tokens
        return "x"

    s = get_scenario("canary_vault_key")
    t = get_technique("direct_ask")
    Attacker(FakeClient(responder)).next_message(s, t, [("a", "no")])
    # DeepSeek-v4 is a reasoning model: hidden CoT eats max_tokens, so we budget generously
    assert seen["max_tokens"] >= 2000


def test_attacker_system_states_harmless_proxy():
    seen = {}

    def responder(model, system, messages, max_tokens):
        seen["system"] = system
        return "x"

    s = get_scenario("canary_vault_key")
    Attacker(FakeClient(responder)).next_message(s, get_technique("direct_ask"), [("a", "no")])
    assert "proxy" in seen["system"].lower() or "canary" in seen["system"].lower()
