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
import threading
from pathlib import Path
from typing import Any

from core.model_client import ModelClient, RecordedClient, estimate_tokens, prompt_key
from core.orchestrator import fan_out, retry
from core.pricing import cost
from core.tracing import TraceStore
from core.types import ModelResponse, RateLimitError
from evals import metrics
from redteam.attacker import Attacker
from redteam.defenses import CONDITIONS, defense_for_condition
from redteam.gauntlet import TrialResult, run_trial
from redteam.scenarios import SCENARIOS, Scenario
from redteam.target import TargetAdapter
from redteam.techniques import TECHNIQUES, Technique

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "evals" / "fixtures"
PROVENANCE = FIXTURES_DIR / "provenance.json"
RESULTS_DIR = ROOT / "evals" / "results"

DEFAULT_K = 2
DEFAULT_MAX_USD = 1.00
TARGET_MAX_TOKENS = 2000  # generous: a reasoning target needs room or its answer truncates empty

# Realistic per-call output-token assumptions for the pre-run estimate (billed = actual tokens).
_EST_TARGET_OUT = 400
_EST_ATTACKER_IN = 650
_EST_ATTACKER_OUT = 900
_EST_CLASSIFIER_OUT = 350


# --- the trial plan -----------------------------------------------------------------------
class TrialSpec:
    __slots__ = ("scenario", "technique", "mode", "condition", "replicate")

    def __init__(self, scenario: Scenario, technique: Technique, mode: str, condition: str,
                 replicate: int = 0):
        self.scenario = scenario
        self.technique = technique
        self.mode = mode
        self.condition = condition
        self.replicate = replicate


def build_plan(
    scenarios: list[Scenario], techniques: list[Technique], replicates: int = 1
) -> list[TrialSpec]:
    """For each (scenario, technique, replicate): single/none, adaptive/none, adaptive/<defense>.

    Replicates (independent samples at temperature > 0) tighten the ASR CIs and let cross-model
    comparisons be statistically powered rather than coin-flips on one sample per cell."""
    plan: list[TrialSpec] = []
    for s in scenarios:
        for t in techniques:
            for r in range(max(1, replicates)):
                plan.append(TrialSpec(s, t, "single", "none", r))
                plan.append(TrialSpec(s, t, "adaptive", "none", r))
                for cond in CONDITIONS[1:]:  # prompt, +classifier, +scan
                    plan.append(TrialSpec(s, t, "adaptive", cond, r))
    return plan


# --- memoizing recorder for the single live run -------------------------------------------
class RecordingClient:
    """Wraps a real client; calls each unique prompt at most once and records the response.

    Thread-safe single-flight: concurrent calls with the same key collapse into one live call,
    so the recorded fixtures stay exactly consistent with what every trial saw and the dry-run
    replay is exact even under parallelism and model nondeterminism. Rate limits are retried.
    """

    def __init__(self, inner: ModelClient, *, max_usd: float | None = None) -> None:
        self._inner = inner
        self._max_usd = max_usd
        self.fixtures: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, ModelResponse] = {}
        self._inflight: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self.live_calls = 0
        self.total_cost = 0.0

    def complete(self, *, model, system, messages, max_tokens,
                 temperature=0.0, salt="") -> ModelResponse:
        key = prompt_key(model, system, messages, salt)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            # Atomic per-call cost gate: bounds spend to ~concurrency x one-call cost over the
            # cap, far tighter than a per-trial check (a trial is many calls).
            if self._max_usd is not None and self.total_cost >= self._max_usd:
                raise RuntimeError(
                    f"cost cap ${self._max_usd:.2f} reached (spent ${self.total_cost:.4f})"
                )
            ev = self._inflight.get(key)
            owner = ev is None
            if owner:
                ev = threading.Event()
                self._inflight[key] = ev
        assert ev is not None  # owner created it; non-owner read an existing one
        if not owner:
            ev.wait()
            with self._lock:
                if key in self._cache:
                    return self._cache[key]
            # The owner's call failed; don't deadlock or KeyError -- surface a clean error so
            # fan_out degrades this trial and the degraded guard aborts the run.
            raise RuntimeError("coalesced upstream call failed")
        try:
            resp = retry(
                lambda: self._inner.complete(
                    model=model, system=system, messages=messages, max_tokens=max_tokens,
                    temperature=temperature, salt=salt,
                ),
                attempts=4, backoff=1.0, exceptions=(RateLimitError,),
            )
        except BaseException:
            # Always release waiters and drop the reservation, then re-raise.
            with self._lock:
                self._inflight.pop(key, None)
            ev.set()
            raise
        with self._lock:
            self._cache[key] = resp
            self.fixtures[key] = {
                "text": resp.text, "model": resp.model,
                "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
                "latency_ms": resp.latency_ms, "stop_reason": resp.stop_reason,
            }
            self._inflight.pop(key, None)
            self.live_calls += 1
            self.total_cost += resp.cost_usd
        ev.set()
        return resp


# --- cost estimate ------------------------------------------------------------------------
_REASONING_MODELS = {"deepseek-v4-pro"}


def _priced(model: str) -> str:
    from core.pricing import PRICING
    return model if model in PRICING else "deepseek-chat"


def estimate_cost(plan: list[TrialSpec], k: int, *, target_model: str = "deepseek-v4-pro",
                  attacker_model: str = "deepseek-chat") -> float:
    """Model-aware upper-ish estimate (no early-stop, no dedup). Reasoning targets/attackers
    emit far more output tokens, so the per-call output budget depends on the model."""
    tgt_out = 700 if target_model in _REASONING_MODELS else 250
    atk_out = 900 if attacker_model in _REASONING_MODELS else 300
    cls_out = 900 if attacker_model in _REASONING_MODELS else 300
    tp, ap = _priced(target_model), _priced(attacker_model)
    total = 0.0
    for spec in plan:
        harden = spec.condition != "none"
        target = TargetAdapter(_NULL_CLIENT, max_tokens=TARGET_MAX_TOKENS)
        sys_user = target._build(spec.scenario, spec.technique.render(spec.scenario, []), harden)
        target_in = estimate_tokens(sys_user[0] + sys_user[1])
        turns = 1 if spec.mode == "single" else k
        for turn in range(turns):
            if "classifier" in spec.condition:
                total += cost(ap, 200, cls_out)
            total += cost(tp, target_in, tgt_out)
            if turn > 0:  # an adaptive (model-driven) attacker turn
                total += cost(ap, _EST_ATTACKER_IN, atk_out)
    return round(total, 4)


class _NullClient:
    def complete(self, *, model, system, messages, max_tokens,
                 temperature=0.0, salt="") -> ModelResponse:
        raise RuntimeError("null client must not be called")


_NULL_CLIENT = _NullClient()


# --- run loop -----------------------------------------------------------------------------
def run_plan(
    plan: list[TrialSpec], client: ModelClient, *, k: int, trace: TraceStore, run_id: str,
    attacker_model: str = "deepseek-chat", target_model: str = "deepseek-chat",
    temperature: float = 0.0, max_usd: float | None = None, concurrency: int = 8,
) -> list[TrialResult | None]:
    """Execute every trial concurrently. A trial that breaches the cost cap or errors becomes
    ``None`` (the degraded guard then aborts cleanly). Single-flight recording keeps the run
    reproducible despite parallelism. ``client`` routes calls to the right model by the ``model``
    arg, so attacker (cheap, fixed) and target (under test) can differ within one recorder."""
    attacker = Attacker(client, model=attacker_model)
    target = TargetAdapter(client, model=target_model, max_tokens=TARGET_MAX_TOKENS)

    def one(spec: TrialSpec) -> TrialResult:
        if max_usd is not None and getattr(client, "total_cost", 0.0) >= max_usd:
            raise RuntimeError(f"cost cap ${max_usd:.2f} reached before trial")
        defense = defense_for_condition(spec.condition, classifier_client=client)
        return run_trial(
            spec.scenario, spec.technique, mode=spec.mode, k=k,
            attacker=attacker, target=target, defense=defense, condition=spec.condition,
            replicate=spec.replicate, temperature=temperature, target_model=target_model,
            trace=trace, run_id=run_id,
        )

    return fan_out(plan, one, max_concurrency=concurrency)


class RouterClient:
    """Dispatches complete() to a per-model inner client by the ``model`` argument, so one
    recorder can drive a cheap fixed attacker and a distinct target model in the same run."""

    def __init__(self, by_model: dict[str, ModelClient]) -> None:
        self._by_model = by_model

    def complete(self, *, model, system, messages, max_tokens,
                 temperature=0.0, salt="") -> ModelResponse:
        inner = self._by_model.get(model)
        if inner is None:
            raise KeyError(f"no client configured for model {model!r}")
        return inner.complete(model=model, system=system, messages=messages,
                              max_tokens=max_tokens, temperature=temperature, salt=salt)



def assert_not_degraded(
    results: list[TrialResult | None], expected_trials: int, n_techniques: int
) -> list[TrialResult]:
    """Fail loud on a truncated/empty run rather than emitting a fabricated 0% headline."""
    failed = sum(1 for r in results if r is None)
    if failed:
        raise SystemExit(
            f"ABORT (degraded): {failed} trials failed (cost cap or API error). No ASR emitted."
        )
    ok = [r for r in results if r is not None]
    if len(ok) != expected_trials:
        raise SystemExit(
            f"ABORT (degraded): ran {len(ok)} trials, expected {expected_trials}."
        )
    techniques_attempted = {r.technique_id for r in ok}
    if len(techniques_attempted) != n_techniques:
        raise SystemExit(
            f"ABORT (degraded): {len(techniques_attempted)} techniques attempted, "
            f"expected {n_techniques}."
        )
    # Per-trial (not global) liveness: a truncation symptom is a trial whose every target turn
    # came back empty. Even a refusal or a defense block is non-empty, so a fully-empty trial
    # means the model produced nothing -- refuse rather than score it.
    empty_trials = [
        r for r in ok if not any(turn.target and turn.target.strip() for turn in r.transcript)
    ]
    empty_frac = len(empty_trials) / len(ok) if ok else 0.0
    if empty_frac > 0.05:
        raise SystemExit(
            f"ABORT (degraded): {len(empty_trials)}/{len(ok)} ({empty_frac:.1%}) trials had only "
            "empty target responses — systemic truncation (reasoning ate max_tokens). Refusing to "
            "write a fabricated headline."
        )
    if empty_trials:
        # Rare truncation is tolerated and counted as non-success: an empty response contains no
        # leak, so labeling it a non-success is correct regardless of why it was empty.
        print(f"[warn] {len(empty_trials)}/{len(ok)} ({empty_frac:.1%}) trials had only-empty "
              "target responses (rare reasoning truncation); counted as non-success.",
              file=sys.stderr)
    return ok


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
        f"- **Adaptation lift: +{_pct(lift['lift_abs'])}** "
        f"(McNemar exact p={lift['significance']['p_value']}, "
        f"discordant pairs b={lift['significance']['b_single_fail_adaptive_success']}/"
        f"c={lift['significance']['c_single_success_adaptive_fail']} — "
        f"{'significant' if lift['significance']['significant_at_05'] else 'NOT significant'} at 0.05)", "",
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
MANIFEST = FIXTURES_DIR / "manifest.json"
DEFAULT_TARGETS = ["deepseek-v4-pro", "deepseek-chat"]
DEFAULT_ATTACKER = "deepseek-chat"
DEFAULT_REPLICATES = 3
DEFAULT_TEMPERATURE = 0.7


def _fixtures_path(target: str) -> Path:
    return FIXTURES_DIR / f"{target}.json"


def _make_client(model: str) -> ModelClient:
    if model.startswith("gpt-"):
        from core.openai_client import OpenAIClient
        return OpenAIClient(model=model)
    from core.deepseek_client import DeepSeekClient
    return DeepSeekClient(model=model)


def _recorder_for(target: str, attacker_model: str, max_usd: float | None) -> RecordingClient:
    inners: dict[str, ModelClient] = {attacker_model: _make_client(attacker_model)}
    if target not in inners:
        inners[target] = _make_client(target)
    return RecordingClient(RouterClient(inners), max_usd=max_usd)


# --- markdown + combined export -----------------------------------------------------------
def _render_md_multi(per_summary: dict[str, dict[str, Any]],
                     cross: dict[str, Any], primary: str) -> str:
    md = [_render_md(per_summary[primary]),
          "", f"_(Claims above are for the primary target `{primary}`.)_", "",
          "## Cross-model comparison", "",
          "| Metric | " + " | ".join(cross["targets"]) + " | p (2-prop) |",
          "|---" * (len(cross["targets"]) + 2) + "|"]
    for row in cross["rows"]:
        cells = " | ".join(
            f"{_pct(row['by_target'][t]['asr'])} (n={row['by_target'][t]['n']})"
            for t in cross["targets"]
        )
        p = row.get("p_value")
        ptxt = f"{p}{'*' if row.get('significant_at_05') else ''}" if p is not None else "—"
        md.append(f"| {row['label']} | {cells} | {ptxt} |")
    md.append("")
    md.append("\\* significant at 0.05 (two-proportion z-test).")
    return "\n".join(md)


def write_outputs_multi(
    per_summary: dict[str, dict[str, Any]], per_results: dict[str, list[TrialResult]],
    *, primary: str, cross_model: dict[str, Any], manifest: dict[str, Any],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # export.json — primary single-target views (backwards compatible) + cross-model block
    export = dict(per_summary[primary])
    export["trials"] = [_trial_to_dict(r) for r in per_results[primary]]
    export["cross_model"] = cross_model
    export["targets_available"] = list(per_summary)
    (RESULTS_DIR / "export.json").write_text(json.dumps(export, indent=2))
    # asr.json — primary summary + cross-model (the reproduction test checks this)
    primary_summary = dict(per_summary[primary])
    primary_summary["cross_model"] = cross_model
    (RESULTS_DIR / "asr.json").write_text(json.dumps(primary_summary, indent=2))
    # crossmodel.json — every target's full summary
    (RESULTS_DIR / "crossmodel.json").write_text(
        json.dumps({"meta": manifest, "cross_model": cross_model, "targets": per_summary}, indent=2)
    )
    (RESULTS_DIR / "asr.md").write_text(_render_md_multi(per_summary, cross_model, primary))


# --- main ---------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aegis red-team gauntlet runner (multi-target)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="replay committed fixtures (default)")
    mode.add_argument("--live", action="store_true", help="make paid calls (needs AEGIS_LIVE=1)")
    p.add_argument("--targets", default=",".join(DEFAULT_TARGETS),
                   help="comma-separated target model ids; first is the primary")
    p.add_argument("--attacker-model", default=DEFAULT_ATTACKER)
    p.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--max-usd", type=float,
                   default=float(os.environ.get("AEGIS_MAX_USD", DEFAULT_MAX_USD)))
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--limit", type=int, default=0,
                   help="cheap smoke: cap the plan to the first N (scenario,technique) cells")
    args = p.parse_args(argv)

    scenarios, techniques = SCENARIOS, TECHNIQUES
    if args.limit:
        # subset for a cheap live smoke of the full pipeline
        techniques = TECHNIQUES[: max(1, args.limit)]
        scenarios = SCENARIOS[: max(1, args.limit)]

    trace = TraceStore(str(RESULTS_DIR / "traces.db"))
    per_results: dict[str, list[TrialResult]] = {}

    if args.live:
        if os.environ.get("AEGIS_LIVE") != "1":
            print("Refusing live run: set AEGIS_LIVE=1 to confirm paid calls.", file=sys.stderr)
            return 2
        targets = [t.strip() for t in args.targets.split(",") if t.strip()]
        plan = build_plan(scenarios, techniques, args.replicates)
        total_est = sum(
            estimate_cost(plan, args.k, target_model=t, attacker_model=args.attacker_model)
            for t in targets
        )
        print(f"[cost] estimated worst-case ~${total_est:.2f} for {len(targets)} target(s) x "
              f"{len(plan)} trials (n={args.replicates}, cap ${args.max_usd:.2f}). "
              "Actual is materially lower (early-stop + memoization).")
        if total_est > args.max_usd:
            print(f"Refusing: estimate ${total_est:.2f} exceeds cap ${args.max_usd:.2f}.",
                  file=sys.stderr)
            return 2
        manifest: dict[str, Any] = {
            "source": "live", "attacker_model": args.attacker_model, "k": args.k,
            "replicates": args.replicates, "temperature": args.temperature,
            "n_scenarios": len(scenarios), "n_techniques": len(techniques),
            "pricing_basis": "deepseek-chat list ($0.27/$1.10 per MTok); actual rate may differ",
            "targets": {},
        }
        spent = 0.0
        for t in targets:
            run_id = trace.new_run(f"gauntlet-{t}-n{args.replicates}-live")
            rec = _recorder_for(t, args.attacker_model, max_usd=args.max_usd - spent)
            raw = run_plan(plan, rec, k=args.k, trace=trace, run_id=run_id,
                           attacker_model=args.attacker_model, target_model=t,
                           temperature=args.temperature, max_usd=args.max_usd - spent,
                           concurrency=args.concurrency)
            per_results[t] = assert_not_degraded(raw, len(plan), len(techniques))
            FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
            _fixtures_path(t).write_text(json.dumps(rec.fixtures, indent=2))
            in_tok = sum(int(f["input_tokens"]) for f in rec.fixtures.values())
            out_tok = sum(int(f["output_tokens"]) for f in rec.fixtures.values())
            manifest["targets"][t] = {
                "live_calls": rec.live_calls, "input_tokens": in_tok,
                "output_tokens": out_tok, "cost_usd": round(rec.total_cost, 4),
            }
            spent += rec.total_cost
            print(f"[cost] {t}: ${rec.total_cost:.4f} over {rec.live_calls} calls "
                  f"({in_tok} in + {out_tok} out tok). cumulative ${spent:.4f}/{args.max_usd:.2f}")
        manifest["total_cost_usd"] = round(spent, 4)
        MANIFEST.write_text(json.dumps(manifest, indent=2))
    else:
        if not MANIFEST.exists():
            raise SystemExit(f"No manifest at {MANIFEST}. Run a live gauntlet first.")
        manifest = json.loads(MANIFEST.read_text())
        targets = list(manifest["targets"])
        args.k = manifest["k"]
        plan = build_plan(SCENARIOS, TECHNIQUES, manifest["replicates"])
        for t in targets:
            fx = json.loads(_fixtures_path(t).read_text())
            run_id = trace.new_run(f"gauntlet-{t}-dry")
            raw = run_plan(plan, RecordedClient(fx, strict=True), k=manifest["k"],
                           trace=trace, run_id=run_id, attacker_model=manifest["attacker_model"],
                           target_model=t, temperature=manifest["temperature"],
                           concurrency=args.concurrency)
            per_results[t] = assert_not_degraded(raw, len(plan), manifest["n_techniques"])

    per_summary: dict[str, dict[str, Any]] = {}
    for t in targets:
        summ = summarize(per_results[t], target=t, mode_k=args.k, live=True)
        summ["meta"]["provenance"] = manifest["targets"].get(t)
        per_summary[t] = summ
    cross = metrics.cross_model_compare(per_results)
    primary = targets[0]
    write_outputs_multi(per_summary, per_results, primary=primary,
                        cross_model=cross, manifest=manifest)

    for t in targets:
        lift = per_summary[t]["adaptation_lift"]
        curve = per_summary[t]["defense_curve"]
        print(f"[{t}] adaptation {_pct(lift['single_asr'])}->{_pct(lift['adaptive_asr'])} "
              f"(p={lift['significance']['p_value']}) | defense "
              f"{_pct(curve['by_condition']['none']['asr'])}->"
              f"{_pct(curve['by_condition'][CONDITIONS[-1]]['asr'])}")
    inj = next(r for r in cross["rows"] if "Injection" in r["label"])
    print("[cross-model] injection ASR: "
          + ", ".join(f"{t}={_pct(inj['by_target'][t]['asr'])}" for t in targets)
          + (f" (p={inj.get('p_value')})" if "p_value" in inj else ""))
    print(f"[ok] wrote {RESULTS_DIR}/export.json, asr.json, asr.md, crossmodel.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
