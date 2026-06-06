# Aegis — ASR results

- Target: `deepseek-v4-pro`  |  K=2  |  trials=1440  |  live=True

## Claim 1 — Adaptation lift (defense = none)

- Single-turn ASR: **24.0%** (95% CI 19.1%–28.8%, n=288)
- 2-turn adaptive ASR: **29.9%** (95% CI 24.3%–35.1%, n=288)
- **Adaptation lift: +5.9%** (McNemar exact p=0.0, discordant pairs b=17/c=0 — significant at 0.05)

## Claim 2 — Defense reduction (adaptive attacker)

| Condition | ASR | 95% CI |
|---|---|---|
| none | 29.9% | 24.3%–35.1% |
| prompt | 17.7% | 13.5%–22.2% |
| prompt+classifier | 2.1% | 0.7%–3.8% |
| prompt+classifier+scan | 1.7% | 0.4%–3.5% |

- **Defense reduction (none → prompt+classifier+scan): −28.1%**
- Per-layer marginal: prompt −12.2%, prompt+classifier −15.6%, prompt+classifier+scan −0.3%


_(Claims above are for the primary target `deepseek-v4-pro`.)_

## Cross-model comparison

| Metric | deepseek-v4-pro | deepseek-chat | p (2-prop) |
|---|---|---|---|
| Injection ASR (adaptive, undefended) | 49.3% (n=144) | 68.1% (n=144) | 0.0012* |
| Canary ASR (adaptive, undefended) | 10.4% (n=144) | 21.5% (n=144) | 0.0101* |
| Overall ASR (adaptive, undefended) | 29.9% (n=288) | 44.8% (n=288) | 0.0002* |
| ASR with full defense stack | 1.7% (n=288) | 2.8% (n=288) | 0.4 |

\* significant at 0.05 (two-proportion z-test).