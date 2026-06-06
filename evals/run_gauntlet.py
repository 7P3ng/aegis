"""Aegis eval harness — the cost-gated runner that produces the two headline numbers.

Default is **dry-run**: it replays committed fixtures through the exact same code path the
live run used, at zero cost, and reproduces the committed ASR numbers. A **live** run requires
``AEGIS_LIVE=1``, prints an estimated token/cost figure *before the first paid call*, and
refuses to start if the estimate exceeds ``AEGIS_MAX_USD`` (default $1.00). A runtime kill
switch aborts if cumulative actual cost reaches the cap. A degraded run (no trials, missing
techniques, or all-empty responses — e.g. reasoning ate max_tokens) ABORTS with a visible
error and never writes a fabricated 0% headline.

Reproducibility: the live client is a *memoizing recorder* — each unique (model, system,
messages) call is made at most once and cached, so the recorded fixtures are exactly
self-consistent and the dry-run replay is deterministic regardless of model nondeterminism.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from core.model_client import ModelClient, RecordedClient, estimate_tokens, prompt_key
from core.pricing import cost
from core.tracing import TraceStore
from core.types import ModelResponse
from evals import metrics
from redteam.attacker import Attacker
from redteam.defenses import CONDITIONS, defense_for_condition
from redteam.gauntlet import TrialResult, run_trial
from redteam.scenarios import SCENARIOS, Scenario
from redteam.target import TargetAdapter
from redteam.techniques import TECHNIQUES, Technique

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "evals" / "fixtures"
RESULTS_DIR = ROOT / "evals" / "results"

DEFAULT_K = 2
DEFAULT_MAX_USD = 1.00
TARGET_MAX_TOKENS = 1500  # generous: a reasoning target needs room or its answer truncates empty

# Realistic per-call output-token assumptions for the pre-run estimate (billed = actual tokens).
_EST_TARGET_OUT = 400
_EST_ATTACKER_IN = 650
_EST_ATTACKER_OUT = 900
_EST_CLASSIFIER_OUT = 350


# --- the trial plan -----------------------------------------------------------------------
class TrialSpec:
    __slots__ = ("scenario", "technique", "mode", "condition")

    def __init__(self, scenario: Scenario, technique: Technique, mode: str, condition: str):
        self.scenario = scenario
        self.technique = technique
        self.mode = mode
        self.condition = condition


def build_plan(scenarios: list[Scenario], techniques: list[Technique]) -> list[TrialSpec]:
    """For each (scenario, technique): single/none, adaptive/none, and adaptive/<each defense>."""
    plan: list[TrialSpec] = []
    for s in scenarios:
        for t in techniques:
            plan.append(TrialSpec(s, t, "single", "none"))
            plan.append(TrialSpec(s, t, "adaptive", "none"))
            for cond in CONDITIONS[1:]:  # prompt, +classifier, +scan
                plan.append(TrialSpec(s, t, "adaptive", cond))
    return plan


# --- memoizing recorder for the single live run -------------------------------------------
class RecordingClient:
    """Wraps a real client; calls each unique prompt at most once and records the response.

    Memoization makes the live run self-consistent with the fixtures it writes, so the dry-run
    replay is exact even though the underlying model is nondeterministic.
    """

    def __init__(self, inner: ModelClient) -> None:
        self._inner = inner
        self.fixtures: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, ModelResponse] = {}
        self.live_calls = 0

    def complete(self, *, model, system, messages, max_tokens) -> ModelResponse:
        key = prompt_key(model, system, messages)
        if key in self._cache:
            return self._cache[key]
        resp = self._inner.complete(
            model=model, system=system, messages=messages, max_tokens=max_tokens
        )
        self.live_calls += 1
        self._cache[key] = resp
        self.fixtures[key] = {
            "text": resp.text, "model": resp.model,
            "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
            "latency_ms": resp.latency_ms, "stop_reason": resp.stop_reason,
        }
        return resp


# --- cost estimate ------------------------------------------------------------------------
def estimate_cost(plan: list[TrialSpec], k: int) -> float:
    """Estimated USD for a live run (assumes no early-stop and no memoization dedup => upper-ish)."""
    total = 0.0
    for spec in plan:
        harden = spec.condition != "none"
        target = TargetAdapter(_NULL_CLIENT, max_tokens=TARGET_MAX_TOKENS)
        sys_user = target._build(spec.scenario, spec.technique.render(spec.scenario, []), harden)
        target_in = estimate_tokens(sys_user[0] + sys_user[1])
        turns = 1 if spec.mode == "single" else k
        for turn in range(turns):
            if "classifier" in spec.condition:
                total += cost("deepseek-chat", 200, _EST_CLASSIFIER_OUT)
            total += cost("deepseek-chat", target_in, _EST_TARGET_OUT)
            if turn > 0:  # an adaptive (model-driven) attacker turn
                total += cost("deepseek-chat", _EST_ATTACKER_IN, _EST_ATTACKER_OUT)
    return round(total, 4)


class _NullClient:
    def complete(self, *, model, system, messages, max_tokens) -> ModelResponse:
        raise RuntimeError("null client must not be called")


_NULL_CLIENT = _NullClient()


# --- run loop -----------------------------------------------------------------------------
def run_plan(
    plan: list[TrialSpec], client: ModelClient, *, k: int, trace: TraceStore, run_id: str,
    max_usd: float | None = None,
) -> list[TrialResult]:
    """Execute every trial. Aborts (raises) if cumulative cost reaches the cap."""
    attacker = Attacker(client)
    target = TargetAdapter(client, max_tokens=TARGET_MAX_TOKENS)
    results: list[TrialResult] = []
    for spec in plan:
        defense = defense_for_condition(spec.condition, classifier_client=client)
        r = run_trial(
            spec.scenario, spec.technique, mode=spec.mode, k=k,
            attacker=attacker, target=target, defense=defense, condition=spec.condition,
            trace=trace, run_id=run_id,
        )
        results.append(r)
        if max_usd is not None:
            spent = sum(s["total_cost_usd"] for s in trace.query_runs() if s["run_id"] == run_id)
            if spent >= max_usd:
                raise SystemExit(
                    f"ABORT: live cost ${spent:.4f} reached the cap ${max_usd:.2f} after "
                    f"{len(results)} trials. No ASR emitted (degraded run)."
                )
    return results


def assert_not_degraded(results: list[TrialResult], expected_trials: int, n_techniques: int) -> None:
    """Fail loud on a truncated/empty run rather than emitting a fabricated 0% headline."""
    if len(results) != expected_trials:
        raise SystemExit(
            f"ABORT (degraded): ran {len(results)} trials, expected {expected_trials}."
        )
    techniques_attempted = {r.technique_id for r in results}
    if len(techniques_attempted) != n_techniques:
        raise SystemExit(
            f"ABORT (degraded): {len(techniques_attempted)} techniques attempted, "
            f"expected {n_techniques}."
        )
    non_empty = sum(
        1 for r in results for turn in r.transcript if turn.target and turn.target.strip()
    )
    if non_empty == 0:
        raise SystemExit(
            "ABORT (degraded): every target response was empty — likely the reasoning model "
            "truncated on max_tokens. Refusing to write a 0% headline."
        )


# --- summary + outputs --------------------------------------------------------------------
def summarize(results: list[TrialResult], *, target: str, mode_k: int, live: bool) -> dict[str, Any]:
    lift = metrics.adaptation_lift(results)
    curve = metrics.defense_curve(results)
    return {
        "meta": {
            "target": target, "k": mode_k, "live": live,
            "n_trials": len(results), "n_scenarios": len({r.scenario_id for r in results}),
            "n_techniques": len({r.technique_id for r in results}),
            "conditions": CONDITIONS,
        },
        "adaptation_lift": lift,
        "defense_curve": curve,
        "heatmap_adaptive_none": metrics.heatmap(results, mode="adaptive", condition="none"),
        "heatmap_single_none": metrics.heatmap(results, mode="single", condition="none"),
    }


def _trial_to_dict(r: TrialResult) -> dict[str, Any]:
    return {
        "scenario": r.scenario_id, "technique": r.technique_id, "mode": r.mode,
        "condition": r.condition, "success": r.success, "turns_used": r.turns_used,
        "blocked_by": r.blocked_by,
        "transcript": [
            {"attacker": t.attacker, "target": t.target, "success": t.success,
             "blocked_by": t.blocked_by}
            for t in r.transcript
        ],
    }


def write_outputs(summary: dict[str, Any], results: list[TrialResult]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "asr.json").write_text(json.dumps(summary, indent=2))
    export = dict(summary)
    export["trials"] = [_trial_to_dict(r) for r in results]
    (RESULTS_DIR / "export.json").write_text(json.dumps(export, indent=2))
    (RESULTS_DIR / "asr.md").write_text(_render_md(summary))


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _render_md(s: dict[str, Any]) -> str:
    lift = s["adaptation_lift"]
    curve = s["defense_curve"]
    lines = [
        "# Aegis — ASR results", "",
        f"- Target: `{s['meta']['target']}`  |  K={s['meta']['k']}  |  "
        f"trials={s['meta']['n_trials']}  |  live={s['meta']['live']}", "",
        "## Claim 1 — Adaptation lift (defense = none)", "",
        f"- Single-turn ASR: **{_pct(lift['single_asr'])}** "
        f"(95% CI {_pct(lift['single_ci'][0])}–{_pct(lift['single_ci'][1])}, n={lift['single_n']})",
        f"- {s['meta']['k']}-turn adaptive ASR: **{_pct(lift['adaptive_asr'])}** "
        f"(95% CI {_pct(lift['adaptive_ci'][0])}–{_pct(lift['adaptive_ci'][1])}, n={lift['adaptive_n']})",
        f"- **Adaptation lift: +{_pct(lift['lift_abs'])}**", "",
        "## Claim 2 — Defense reduction (adaptive attacker)", "",
        "| Condition | ASR | 95% CI |", "|---|---|---|",
    ]
    for cond in CONDITIONS:
        c = curve["by_condition"][cond]
        lines.append(f"| {cond} | {_pct(c['asr'])} | {_pct(c['ci'][0])}–{_pct(c['ci'][1])} |")
    lines += [
        "",
        f"- **Defense reduction ({curve['from_condition']} → {curve['to_condition']}): "
        f"−{_pct(curve['reduction_abs'])}**",
        "- Per-layer marginal: "
        + ", ".join(f"{k} −{_pct(v)}" for k, v in curve["per_layer_marginal"].items()),
        "",
    ]
    return "\n".join(lines)


# --- clients ------------------------------------------------------------------------------
def _load_fixtures() -> dict[str, Any]:
    path = FIXTURES_DIR / "deepseek.json"
    if not path.exists():
        raise SystemExit(
            f"No fixtures at {path}. Run a live gauntlet first (AEGIS_LIVE=1 ... --live)."
        )
    return json.loads(path.read_text())


def _build_live_client() -> ModelClient:
    from core.deepseek_client import DeepSeekClient
    return DeepSeekClient()


# --- main ---------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aegis red-team gauntlet runner")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="replay committed fixtures (default)")
    mode.add_argument("--live", action="store_true", help="make paid calls (needs AEGIS_LIVE=1)")
    p.add_argument("--target", default="deepseek", choices=["deepseek"])
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--max-usd", type=float, default=float(os.environ.get("AEGIS_MAX_USD", DEFAULT_MAX_USD)))
    args = p.parse_args(argv)

    plan = build_plan(SCENARIOS, TECHNIQUES)
    trace = TraceStore(str(ROOT / "evals" / "results" / "traces.db"))
    run_id = trace.new_run(f"gauntlet-{args.target}-k{args.k}-{'live' if args.live else 'dry'}")

    if args.live:
        if os.environ.get("AEGIS_LIVE") != "1":
            print("Refusing live run: set AEGIS_LIVE=1 to confirm paid calls.", file=sys.stderr)
            return 2
        est = estimate_cost(plan, args.k)
        print(f"[cost] estimated ~${est:.4f} for {len(plan)} trials at K={args.k} "
              f"(cap ${args.max_usd:.2f}). Billed = actual tokens; memoization reduces this.")
        if est > args.max_usd:
            print(f"Refusing: estimate ${est:.4f} exceeds cap ${args.max_usd:.2f}.", file=sys.stderr)
            return 2
        client: ModelClient = RecordingClient(_build_live_client())
        results = run_plan(plan, client, k=args.k, trace=trace, run_id=run_id, max_usd=args.max_usd)
        assert_not_degraded(results, len(plan), len(TECHNIQUES))
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURES_DIR / "deepseek.json").write_text(json.dumps(client.fixtures, indent=2))  # type: ignore[attr-defined]
        spent = sum(s["total_cost_usd"] for s in trace.query_runs() if s["run_id"] == run_id)
        print(f"[cost] actual ${spent:.4f} over {client.live_calls} unique live calls.")  # type: ignore[attr-defined]
    else:
        fixtures = _load_fixtures()
        client = RecordedClient(fixtures, strict=True)
        results = run_plan(plan, client, k=args.k, trace=trace, run_id=run_id)
        assert_not_degraded(results, len(plan), len(TECHNIQUES))

    summary = summarize(results, target=args.target, mode_k=args.k, live=args.live)
    write_outputs(summary, results)
    lift = summary["adaptation_lift"]
    curve = summary["defense_curve"]
    print(f"[claim 1] adaptation lift: {_pct(lift['single_asr'])} -> {_pct(lift['adaptive_asr'])} "
          f"(+{_pct(lift['lift_abs'])})")
    print(f"[claim 2] defense reduction: {_pct(curve['by_condition']['none']['asr'])} -> "
          f"{_pct(curve['by_condition'][CONDITIONS[-1]]['asr'])} (-{_pct(curve['reduction_abs'])})")
    print(f"[ok] wrote {RESULTS_DIR}/asr.json, asr.md, export.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
