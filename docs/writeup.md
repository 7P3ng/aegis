# Aegis — a mini research note

**One line.** An adaptive attacker agent red-teams a target model on two harmless proxy
threats; layered defenses then measurably cut the attack-success rate (ASR). Every number
here is produced by the harness and reproducible from committed fixtures with
`make eval-dry` (zero cost).

> **Responsible red-teaming (non-negotiable).** Aegis never attempts to elicit real harmful
> content. The only "harms" are two harmless proxies: a secret **canary string** the target is
> told to protect, and a **prompt-injection sentinel** marker a benign tool-agent is tricked
> into emitting. No bioweapons, CSAM, self-harm, illegal-acts, or any genuinely dangerous
> category is ever solicited or generated. Success is scored by **exact string / sentinel
> match** — there is no LLM judge in the success path, so ASR carries zero judge variance.

## 1. Setup

- **Target.** `deepseek-v4-pro` (one live run; cross-model targets are operator-gated on an
  API key and intentionally absent here rather than faked).
- **Benchmark.** 6 scenarios (3 canary data-exfiltration proxies + 3 injection
  instruction-hijack proxies) × 12 attack techniques. K = 2 (turn 0 is the single-turn
  baseline; turn 1 is one model-driven adaptive follow-up). 360 trials across the condition
  matrix; 591 unique live calls (143,406 input + 430,754 output tokens). Cost **~$0.51**,
  computed at deepseek-chat list prices ($0.27 / $1.10 per MTok); the actual deepseek-v4-pro
  billing rate may differ, so this is an estimate from measured token counts, not a billed
  figure. Well under the $1 cost gate.
- **Attacker.** An agent that, on turn 0, emits a deterministic technique-rendered message
  (this *is* the single-turn baseline), then on turn 1 reads the target's refusal and crafts a
  new attack. Techniques span roleplay, fiction, base64/leetspeak/cross-language obfuscation,
  many-shot, instruction-override, payload-splitting, refusal-suppression, authority/urgency,
  context-overflow, and a **direct-ask control**.
- **Defenses (stackable).** (1) prompt-hardening (spotlight delimiters + "untrusted data"
  framing); (2) an input classifier (a cheap model call that blocks a flagged message before
  the target); (3) an output canary-scan (deterministic; fires only on canary scenarios,
  because the defender holds the canary but not an attacker's sentinel — see §5).
- **Scoring.** Deterministic. CIs are seeded 95% percentile bootstraps (2000 resamples) over
  the 72 cells of each condition.

## 2. Claim 1 — adaptation lift

| Mode (defense = none) | ASR | 95% CI | n |
|---|---|---|---|
| Single-turn (turn 0) | **27.8%** | 18.1% – 38.9% | 72 |
| 2-turn adaptive | **29.2%** | 19.4% – 40.3% | 72 |

**Adaptation lift: +1.4% — and it is not statistically significant.** The single-turn and
adaptive trials are *paired* by (scenario, technique), so the correct test is McNemar's on the
discordant cells, not a comparison of the two overlapping marginal CIs above. Of the 72 paired
cells: 20 both-success, 51 both-failure, and only the discordant cells matter — **b = 1**
(one fail→success: `inject_doc_summary × many_shot`), **c = 0**. Exact two-sided McNemar
**p = 1.0**. So the +1.4% is a single cell flipping, indistinguishable from noise. The harness
computes and reports this (`adaptation_lift.significance` in `results/asr.json`).

The honest reading: against this target a single adaptive follow-up does **not** measurably
raise ASR — attacks that work tend to land on turn 0, and refusals are consistent. By
construction adaptive ASR ≥ single-turn ASR (turn 0 of the adaptive trial *is* the single-turn
trial), so this result verifies the harness and bounds the effect rather than demonstrating
adaptation. The lever is a deeper attacker (larger K, diversity search — §6); the harness
already takes `--k`. Reporting a careful null here is deliberate: the artifact's value is the
measurement discipline, not a manufactured lift.

## 3. Claim 2 — defense reduction

| Condition (adaptive attacker) | ASR | 95% CI |
|---|---|---|
| none | **29.2%** | 19.4% – 40.3% |
| + prompt-hardening | 19.4% | 9.7% – 29.2% |
| + input classifier | 5.6% | 1.4% – 11.1% |
| + output canary-scan (full stack) | **4.2%** | 0.0% – 8.3% |

**Defense reduction: −25.0%** (29.2% → 4.2%). The none vs full-stack CIs are well separated
(19.4–40.3% vs 0.0–8.3%), so the end-to-end reduction is solid. Adjacent-condition CIs
overlap, so the per-layer marginals below are **directional**, not individually significant:

- prompt-hardening: **−9.7%**
- input classifier: **−13.9%** (the single biggest contributor; it blocked 134 attack
  messages before they reached the target across the defended conditions)
- output canary-scan: **−1.4%** (small, and expected — by the time it could fire, hardening +
  the classifier have already neutralised most attacks, and it only applies to canary leaks)

## 4. What landed, and where the model is weak

At defense = none, adaptive mode:

- **Injection is the real weakness: 50% ASR (18/36) vs only 8% (3/36) for canary protection.**
  `deepseek-v4-pro` guards an explicitly-held secret well, but is readily hijacked when
  adversarial instructions are smuggled inside untrusted *data* it is asked to process — the
  exact failure mode production agent stacks worry about.
- Most effective techniques: **roleplay, fiction, and refusal-suppression (50% each)**, all
  ahead of the direct-ask control (33%). Obfuscation families (base64, leetspeak, translation,
  payload-splitting) and authority/urgency underperformed the control here (17%).

## 5. Threats to validity

1. **Small benchmark.** 6 scenarios × 12 techniques = 72 cells per condition. CIs are wide
   (±~10%); treat the point estimates as directional, not leaderboard-grade.
2. **Output canary-scan is deliberately not an oracle.** It scans only for the canary the
   *defender holds*; it does **not** scan for the attacker's injection sentinel, because a real
   defender does not know it. Scanning for the sentinel would make the injection result
   tautological (ASR forced to 0 by construction). Restricting the scan keeps the defense
   reduction an honest measurement — at the cost of a smaller marginal for that layer.
3. **K = 2.** One adaptive follow-up is a shallow probe of "adaptation"; the small lift is
   partly a function of depth. Chosen to keep the single live run under the $1 cost gate with a
   reasoning-model target. Larger K is supported and likely increases lift.
4. **Single target, single seed family.** No cross-model claim is made; cross-model targets are
   gated on a key and omitted rather than fabricated.
5. **The classifier is itself a model.** It can be evaded; its −13.9% is an upper-ish bound for
   *these* techniques and would erode against an attacker optimising against the classifier.

## 6. Future work (out of scope here)

Cross-model targets (Claude / GPT) populating a comparison table when a key is present; a
diversity-search attacker (novelty-pressured technique generation); larger K; more scenarios.

## 7. Reproduce

```bash
pip install -e ".[dev]"
make eval-dry     # replays committed fixtures, reproduces every number above, $0 cost
make test         # ruff + mypy + pytest (incl. the reproduction test)
```

A single live run (re-recording fixtures) is cost-gated and opt-in:
`source <deepseek-env>; AEGIS_LIVE=1 make eval-live`.

*Kernel (model-client seam, SQLite tracing, orchestrator, pricing, bootstrap CIs) vendored and
adapted from the author's prior artifact, Quorum.*
