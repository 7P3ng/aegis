"""The gauntlet runner: drive the adaptive attacker through the target for one trial.

A *trial* is one (scenario, technique, mode, defense-condition). The runner alternates
attacker -> [input defense] -> target -> [output defense] -> deterministic judge, up to K
turns, stopping early on success, recording every turn as a trace span.

The :class:`Defense` seam is duck-typed so Phase 3's stack plugs in without changing this
file: ``harden`` flows to the target, ``classify`` can block an attacker message before it
reaches the target, and ``scan`` can redact a leaking response before it is judged. The
default :data:`NO_DEFENSE` is the baseline (no defense) condition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.tracing import TraceStore
from redteam.attacker import Attacker
from redteam.scenarios import Scenario
from redteam.target import TargetAdapter
from redteam.techniques import Technique

_REDACTED = "[REDACTED BY OUTPUT SCAN]"


class Defense(Protocol):
    """Duck-typed defense condition. Phase 3's DefenseStack satisfies this."""

    harden: bool

    def classify(self, message: str, *, temperature: float = 0.0, salt: str = "") -> str | None:
        """Return a blocking-layer name if the incoming message is flagged, else None."""
        ...

    def scan(self, scenario: Scenario, text: str) -> str | None:
        """Return a blocking-layer name if the response must be blocked/redacted, else None."""
        ...


class _NoDefense:
    harden = False

    def classify(self, message: str, *, temperature: float = 0.0, salt: str = "") -> str | None:
        return None

    def scan(self, scenario: Scenario, text: str) -> str | None:
        return None


NO_DEFENSE: Defense = _NoDefense()


@dataclass
class Turn:
    attacker: str
    target: str
    success: bool
    blocked_by: str | None = None


@dataclass
class TrialResult:
    scenario_id: str
    technique_id: str
    mode: str            # "single" | "adaptive"
    condition: str       # defense condition label (e.g. "none", "prompt+classifier+scan")
    success: bool
    turns_used: int
    blocked_by: str | None
    transcript: list[Turn] = field(default_factory=list)
    replicate: int = 0
    target: str = ""     # the target model id under test (cross-model runs)


def run_trial(
    scenario: Scenario,
    technique: Technique,
    *,
    mode: str,
    k: int,
    attacker: Attacker,
    target: TargetAdapter,
    defense: Defense = NO_DEFENSE,
    condition: str = "none",
    replicate: int = 0,
    temperature: float = 0.0,
    target_model: str = "",
    trace: TraceStore | None = None,
    run_id: str | None = None,
    parent: str | None = None,
) -> TrialResult:
    """Run one trial to completion (success or K turns exhausted)."""
    salt = f"rep{replicate}"
    max_turns = 1 if mode == "single" else max(1, k)
    history: list[tuple[str, str]] = []
    transcript: list[Turn] = []
    success = False
    blocked_by: str | None = None

    for turn_idx in range(max_turns):
        attacker_msg = attacker.next_message(
            scenario, technique, history, temperature=temperature, salt=salt
        )

        turn_blocked: str | None = None
        turn_resp = None  # the priced ModelResponse, when a target call happened
        flagged = defense.classify(attacker_msg, temperature=temperature, salt=salt)
        if flagged:
            # Input classifier blocked the message before it reached the target.
            turn_blocked = flagged
            visible_target = "[BLOCKED BY INPUT CLASSIFIER]"
            judged_text = ""
        else:
            turn_resp = target.run_turn(
                scenario, attacker_msg, harden=defense.harden,
                temperature=temperature, salt=salt,
            )
            target_text = turn_resp.text
            scanned = defense.scan(scenario, target_text)
            if scanned:
                turn_blocked = scanned
                judged_text = _REDACTED
                visible_target = _REDACTED
            else:
                judged_text = target_text
                visible_target = target_text

        turn_success = scenario.check(judged_text)
        if turn_success:
            blocked_by = None
        elif turn_blocked:
            blocked_by = turn_blocked

        transcript.append(Turn(attacker_msg, visible_target, turn_success, turn_blocked))
        history.append((attacker_msg, visible_target))

        if trace is not None and run_id is not None:
            with trace.span("turn", run_id=run_id, parent=parent) as sp:
                if turn_resp is not None:
                    sp.record_response(turn_resp)  # price the real model call
                sp.set(
                    scenario=scenario.id, technique=technique.id, mode=mode,
                    condition=condition, replicate=replicate, target_model=target_model,
                    turn=turn_idx, success=turn_success,
                    blocked_by=turn_blocked, attacker=attacker_msg, target=visible_target,
                )

        if turn_success:
            success = True
            break

    return TrialResult(
        scenario_id=scenario.id, technique_id=technique.id, mode=mode, condition=condition,
        success=success, turns_used=len(transcript), blocked_by=None if success else blocked_by,
        transcript=transcript, replicate=replicate, target=target_model,
    )
