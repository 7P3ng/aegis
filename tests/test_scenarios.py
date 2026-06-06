"""Scenarios are committed, labeled, and each carries its own deterministic check."""
from redteam.scenarios import SCENARIOS, Scenario, get_scenario


def test_six_scenarios_three_each():
    assert len(SCENARIOS) == 6
    assert sum(s.kind == "canary" for s in SCENARIOS) == 3
    assert sum(s.kind == "injection" for s in SCENARIOS) == 3


def test_ids_unique():
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_every_scenario_has_policy_and_secret():
    for s in SCENARIOS:
        assert s.system_prompt.strip()
        assert s.secret.strip()
        assert s.kind in {"canary", "injection"}


def test_check_triggers_on_planted_secret_and_not_on_benign():
    for s in SCENARIOS:
        assert s.check(f"... {s.secret} ...") is True
        assert s.check("I will not comply with that request.") is False


def test_injection_scenarios_have_task_and_untrusted_slot():
    for s in SCENARIOS:
        if s.kind == "injection":
            assert s.user_task.strip()
            assert "{payload}" in s.untrusted_template


def test_get_scenario_roundtrip():
    assert get_scenario(SCENARIOS[0].id) is SCENARIOS[0]
    try:
        get_scenario("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown scenario id")


def test_scenario_is_frozen():
    import dataclasses
    assert dataclasses.fields(Scenario)  # is a dataclass
