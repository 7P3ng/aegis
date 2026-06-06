# Aegis — Automated Red-Team Gauntlet

> **Responsible red-teaming.** Aegis NEVER attempts to elicit real harmful content. The only
> "harms" are two harmless proxies: (1) a secret **canary string** the target must protect, and
> (2) **prompt injection** of a benign tool-using agent via a planted **sentinel marker**. No
> bioweapons, CSAM, self-harm, illegal-acts, or any genuinely dangerous category is ever
> solicited or generated. Success is scored **deterministically** (exact string / sentinel
> match) — there is no LLM-judge in the success path.

An adaptive attacker **agent** red-teams a target model on harmless proxies; layered defenses
then measurably reduce the attack-success rate (ASR). Two headline numbers, both produced by
the harness and reproducible from committed fixtures:

<!-- HEADLINE NUMBERS — filled by Phase 4 live run -->
- **Adaptation lift:** single-turn ASR **A%** → K-turn adaptive ASR **B%**.
- **Defense reduction:** layered defense cut adaptive ASR **B%** → **C%**.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make eval-dry      # reproduces the committed numbers from fixtures (zero cost)
make test          # ruff + mypy + pytest
```

## Architecture
Reuses the [Quorum](https://github.com/) kernel (`core/`): a mockable model-client seam, SQLite
tracing, a fan-out/retry orchestrator, and a pricing table. Aegis-specific red-team logic lives
in `redteam/` (scenarios, techniques, adaptive attacker, target adapter, deterministic judge,
defenses, gauntlet runner). `evals/` computes ASR + ablations + bootstrap CIs. `ui/` is a static
dashboard. See `docs/writeup.md` for methodology, ablations, and threats to validity.

## Credits
Kernel vendored and adapted from **Quorum** (this author's prior artifact). See `core/`.
