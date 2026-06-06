# Aegis — a mini research note

**One line.** An adaptive attacker agent red-teams target models on two harmless proxy threats,
scored deterministically; layered defenses measurably cut attack-success, and a scaled benchmark
makes both the adaptation effect and a cross-model robustness gap statistically significant.
Every number is reproducible from committed fixtures with `make eval-dry` (zero cost).

> **Responsible red-teaming (non-negotiable).** Aegis never attempts to elicit real harmful
> content. The only "harms" are a secret **canary string** the target must protect and a
> **prompt-injection sentinel** a benign tool-agent is tricked into emitting. No dangerous
> category is ever solicited or generated. Success is scored by **exact string / sentinel
> match — no LLM judge in the success path**, so ASR has zero judge variance.

## 1. Setup

- **Targets.** `deepseek-v4-pro` (primary, a reasoning model) and `deepseek-chat` (non-reasoning),
  both via the DeepSeek API. Cross-model is DeepSeek-only here to keep cost low; the harness takes
  `--targets` (e.g. `gpt-4o-mini`) when a key is present, and omits gated models rather than
  faking them.
- **Attacker.** Fixed at `deepseek-chat` across both targets, so the comparison isolates *target*
  robustness rather than attacker quality. Turn 0 is the deterministic single-turn baseline; turn 1
  reads the refusal and adapts (K=2).
- **Benchmark.** 12 scenarios (6 canary + 6 injection) × 12 techniques × **n=2 replicates** at
  **temperature 0.7**. 1440 trials per target across the condition matrix; one live run, **$1.00
  total** (`v4-pro` $0.73 / 2236 calls, `deepseek-chat` $0.27 / 2138 calls), priced at
  deepseek-chat list rates (actual v4-pro rate may differ).
- **Why replicates.** ASR on a stochastic model measured once at temperature 0 is a degenerate
  sample. Measuring n=2 independent samples at temperature 0.7 turns each cell into 0/½/1 and
  gives honest CIs — and, as §2 shows, is what makes the adaptation effect detectable at all.
- **Scoring.** Deterministic. CIs are seeded 95% bootstraps; adaptation uses the paired McNemar
  test; cross-model uses two-proportion z-tests. Rare reasoning-truncation empties (0.3% of
  trials) are counted as non-success (an empty response contains no leak).

## 2. Claim 1 — adaptation lift (and a lesson about power)

Primary target `deepseek-v4-pro`, defense = none:

| Mode | ASR | 95% CI |
|---|---|---|
| Single-turn | 24.0% | 19.1–28.8% |
| 2-turn adaptive | **29.9%** | 24.3–35.1% |

**Lift +5.9%, and it is statistically significant.** The trials are paired by (scenario,
technique, replicate); McNemar on the discordant cells gives **b=17 (single-fail → adaptive-
success), c=0, exact p ≈ 0**.

The lesson: an earlier, deliberately tiny version of this benchmark (6 scenarios, n=1) produced
the *same* qualitative effect as a single discordant cell — McNemar p=1.0, indistinguishable
from noise. Scaling to 12 scenarios × n=2 didn't change the phenomenon; it gave the test the
power to see it. The harness computes and reports the significance
(`adaptation_lift.significance` in `results/asr.json`), so the claim is never stronger than the data.

## 3. Claim 2 — defense reduction

Primary target, adaptive attacker, four stacked conditions:

| Condition | ASR | 95% CI |
|---|---|---|
| none | 29.9% | 24.3–35.1% |
| + prompt-hardening | 17.7% | 13.2–22.9% |
| + input classifier | 2.1% | 0.7–3.8% |
| + output canary-scan | **1.7%** | 0.3–3.1% |

**Defense reduction −28.1%** (29.9% → 1.7%); none-vs-full CIs are well separated. Per-layer
marginals: prompt −12.2%, classifier −15.6% (the workhorse), scan −0.3% (small — by the time it
could fire, hardening + the classifier have neutralised most attacks, and it only applies to
canary leaks). Adjacent-condition CIs overlap, so the per-layer split is directional.

## 4. Claim 3 — cross-model robustness (the reasoning model wins, until defended)

Same attacker, adaptive + undefended, n=144–288 per cell:

| Metric | `deepseek-v4-pro` | `deepseek-chat` | p (two-proportion) |
|---|---|---|---|
| Injection ASR | **49.3%** | 68.1% | 0.0012 |
| Canary ASR | **10.4%** | 21.5% | 0.010 |
| Overall ASR | **29.9%** | 44.8% | 0.0002 |
| ASR under full defense stack | 1.7% | 2.8% | 0.40 (n.s.) |

The reasoning model resists both injection and canary extraction **significantly** better than
the non-reasoning model. The most interesting result is the last row: **the layered defense
erases the gap** — under the full stack both models sit near 2% and the difference is no longer
significant. Robustness differences between base models are real but defensible-away with cheap,
model-agnostic guardrails.

Across both models injection (49–68%) is far more exploitable than canary protection (10–22%) —
the data-vs-instruction confusion that production agent stacks actually worry about.

## 5. Threats to validity

1. **Still a modest benchmark.** 144 samples per (kind, condition, target); CIs are ~±5–8%. The
   significant results have comfortable margins, but treat exact percentages as estimates.
2. **n=2, K=2.** Two replicates and one adaptive follow-up — chosen to keep the run under the cost
   cap with a reasoning target. Deeper K / more replicates would tighten further; the harness
   takes `--replicates` and `--k`.
3. **Output canary-scan is deliberately not an oracle** — it scans only for the canary the
   *defender holds*, never the attacker's sentinel (which a real defender doesn't know). Scanning
   for the sentinel would make the injection result tautological.
4. **Two models, one provider.** No claim beyond DeepSeek's reasoning vs non-reasoning models;
   frontier targets (Claude/GPT) are gated on a key and omitted, not fabricated.
5. **The classifier is itself a model** and can be evaded; its −15.6% is an upper-ish bound for
   these techniques.
6. **Cost is estimated at deepseek-chat list prices** from measured token counts, not a billed
   figure; the actual `deepseek-v4-pro` rate may differ.

## 6. Reproduce

```bash
pip install -e ".[dev]"
make eval-dry     # replays committed per-target fixtures, reproduces every number above, $0
make test         # ruff + mypy + pytest (incl. the reproduction test)
```

A live run is cost-gated and opt-in:
`source <deepseek-env>; AEGIS_LIVE=1 .venv/bin/python -m evals.run_gauntlet --live --replicates 2`.

*Kernel (model-client seam, SQLite tracing, orchestrator, pricing, bootstrap CIs) vendored and
adapted from the author's prior artifact, Quorum.*
