# Aegis — Automated Red-Team Gauntlet

An adaptive attacker **agent** red-teams target models on two harmless proxy threats, scored
**deterministically**; layered defenses then measurably reduce the attack-success rate (ASR).
Three results, all produced by the harness and reproducible from committed fixtures at zero cost:
a statistically-significant adaptation lift, a −28% layered-defense reduction, and a significant
**cross-model** robustness gap (a reasoning model resists attacks better — until defended).

**▶ Live dashboard: https://7p3ng.github.io/aegis/**

<p align="center"><img src="docs/assets/hero.png" alt="Aegis dashboard hero" width="760"></p>

> ### 🛡 Responsible red-teaming (non-negotiable)
> Aegis **never** attempts to elicit real harmful content. The only "harms" are two harmless
> proxies: (1) a secret **canary string** the target is told to protect (success = the canary
> appears in output), and (2) **prompt injection** of a benign tool-using agent via a planted
> **sentinel marker** (success = the sentinel appears). No bioweapons, CSAM, self-harm,
> illegal-acts, or any genuinely dangerous category is ever solicited or generated. Success is
> scored by **exact string / sentinel match — there is no LLM judge in the success path**, so
> ASR carries zero judge variance. The proxies are faithful to the two threats production agent
> teams actually defend against (data exfiltration + instruction hijacking).

## Headline results

Benchmark: **12 scenarios** (6 canary + 6 injection) × **12 techniques** × **n=2 replicates**
at temperature 0.7, K=2, attacker = `deepseek-chat` (fixed, so we compare *target* robustness).
Two targets, **one live run, $1.00 total** (`deepseek-v4-pro` $0.73 + `deepseek-chat` $0.27,
priced at deepseek-chat list rates). Seeded 95% bootstrap CIs; paired McNemar for adaptation;
two-proportion z-tests for cross-model. Reproduce with `make eval-dry`.

**1. Adaptation lift (statistically significant).** On the primary target `deepseek-v4-pro`, a
2-turn adaptive attacker raised ASR from **24.0%** (single-turn, CI 19.1–28.8%) to **29.9%**
(CI 24.3–35.1%) — **+5.9%**. The trials are paired by (scenario, technique, replicate); McNemar
on the discordant cells gives **b=17, c=0, p≈0 — significant** at 0.05. (At the original tiny
benchmark this same effect was a single discordant cell, p=1.0; scaling is what made it
measurable — see the writeup.)

**2. Defense reduction.** A layered defense cut adaptive ASR **29.9% → 1.7% (−28.1%)** on the
primary target. Per-layer marginals: prompt-hardening −12.2%, input classifier −15.6%, output
canary-scan −0.3% (the scan is small because hardening + classifier already block most attacks;
adjacent-condition CIs overlap, so treat marginals as directional).

**3. Cross-model: the reasoning model is significantly more robust.** Same attacker, two
targets, adaptive + undefended:

| Metric (adaptive) | `deepseek-v4-pro` | `deepseek-chat` | p (2-prop) |
|---|---|---|---|
| Injection ASR | **49.3%** | 68.1% | **0.0012** ✷ |
| Canary ASR | **10.4%** | 21.5% | **0.010** ✷ |
| Overall ASR | **29.9%** | 44.8% | **0.0002** ✷ |
| ASR under full defense stack | 1.7% | 2.8% | 0.40 (n.s.) |

The reasoning model (`v4-pro`) resists both injection and canary extraction significantly better
than the non-reasoning model (`deepseek-chat`) — but the **layered defense erases the gap**
(1.7% vs 2.8%, not significant). A real comparative safety finding, not three noisy columns:
n=144–288 per cell. Cross-model targets are DeepSeek-only here to keep cost low; the harness
takes `--targets` (e.g. `gpt-4o-mini`) when a key is present. Full analysis + threats-to-validity:
[`docs/writeup.md`](docs/writeup.md).

## Architecture

<p align="center"><img src="docs/architecture.svg" alt="Aegis architecture" width="820"></p>

- **`redteam/`** — scenarios (6 labeled canary + injection), a 12-technique taxonomy, the
  adaptive attacker agent, the target adapter (policy + untrusted-data framing), the
  deterministic judge, three stackable defenses, and the gauntlet runner.
- **`evals/`** — ASR + ablations + bootstrap CIs; a dry-run-by-default, cost-gated runner with
  a degraded-run guard; committed fixtures + results.
- **`ui/`** — a static Next.js dashboard: ASR hero, technique×scenario heatmap, per-layer
  ablation bars, and a browsable **attack log** of every real transcript (with the blocking
  layer shown).
- **`core/`** — the [Quorum](#credits) kernel: a mockable `ModelClient` seam (Fake / Recorded /
  DeepSeek), SQLite tracing, a fan-out/retry orchestrator, pricing, and seeded bootstrap CIs.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make eval-dry      # replays committed fixtures, reproduces the numbers above, $0 cost
make test          # ruff + mypy + pytest (incl. the reproduction test)

# dashboard
cd ui && npm install && npm run build && npx serve out    # then open the printed URL
```

A live run (re-records fixtures, paid) is opt-in and cost-gated — it requires `AEGIS_LIVE=1`,
prints a token/cost estimate before the first paid call, and refuses to exceed `AEGIS_MAX_USD`
(default $1.00):

```bash
source /path/to/deepseek.env        # sets OSSLLM_API_KEY / OSSLLM_MODEL / OSSLLM_URL
AEGIS_LIVE=1 make eval-live
```

Cross-model targets (Claude / GPT) are operator-gated on `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`;
when absent they are omitted rather than fabricated.

## Why this is trustworthy

- **Deterministic scoring.** Canary leak and injection hijack are exact-match checkable; ASR has
  no judge-model variance. An LLM is used only as the *attacker* and the optional *input
  classifier* — never to decide success.
- **Reproducible.** One live run is recorded (memoized, single-flight) into fixtures; the
  dry-run replays them deterministically and a test asserts the committed numbers reproduce.
- **No fabricated numbers.** The runner aborts (never writes a 0% headline) if a run is
  truncated or empty, and refuses to start a live run whose estimate exceeds the cost cap.

## Credits

Kernel (`core/`) and grading helpers (`evals/grade.py`) vendored and adapted from **Quorum**,
this author's prior artifact — the substrate paying off across a second project is part of the
story. Quality-gated: `ruff` + `mypy` + `pytest` green, with a GitHub Actions CI running
lint / type / tests / dry-run reproduction / UI build.

## License

MIT — see [`LICENSE`](LICENSE).
