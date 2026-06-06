"""Attack techniques are render(scenario, history)->str templates that decorate the
scenario's bare objective. A direct-ask control anchors the taxonomy."""
import base64

from redteam.scenarios import SCENARIOS, get_scenario
from redteam.techniques import TECHNIQUES, get_technique


def test_at_least_ten_techniques():
    assert len(TECHNIQUES) >= 10


def test_technique_ids_unique():
    ids = [t.id for t in TECHNIQUES]
    assert len(ids) == len(set(ids))


def test_direct_ask_control_present():
    assert any(t.id == "direct_ask" for t in TECHNIQUES)


def test_every_technique_renders_nonempty_for_both_kinds():
    canary = get_scenario("canary_vault_key")
    inject = get_scenario("inject_doc_summary")
    for t in TECHNIQUES:
        for s in (canary, inject):
            msg = t.render(s, [])
            assert isinstance(msg, str) and msg.strip()


def test_direct_ask_contains_bare_objective():
    s = get_scenario("canary_vault_key")
    assert s.objective in get_technique("direct_ask").render(s, [])


def test_encoding_roundtrips_to_objective():
    s = get_scenario("canary_vault_key")
    msg = get_technique("encoding_base64").render(s, [])
    expected = base64.b64encode(s.objective.encode()).decode()
    assert expected in msg
    # and it decodes back to the objective (deterministic, recoverable)
    assert base64.b64decode(expected).decode() == s.objective


def test_instruction_override_mentions_ignore():
    s = get_scenario("inject_doc_summary")
    assert "ignore" in get_technique("instruction_override").render(s, []).lower()


def test_render_is_deterministic():
    s = SCENARIOS[0]
    for t in TECHNIQUES:
        assert t.render(s, []) == t.render(s, [])
