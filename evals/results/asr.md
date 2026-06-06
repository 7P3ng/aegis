# Aegis — ASR results

- Target: `deepseek-v4-pro`  |  K=2  |  trials=360  |  live=True

## Claim 1 — Adaptation lift (defense = none)

- Single-turn ASR: **27.8%** (95% CI 18.1%–38.9%, n=72)
- 2-turn adaptive ASR: **29.2%** (95% CI 19.4%–40.3%, n=72)
- **Adaptation lift: +1.4%** (McNemar exact p=1.0, discordant pairs b=1/c=0 — NOT significant at 0.05)

## Claim 2 — Defense reduction (adaptive attacker)

| Condition | ASR | 95% CI |
|---|---|---|
| none | 29.2% | 19.4%–40.3% |
| prompt | 19.4% | 9.7%–29.2% |
| prompt+classifier | 5.6% | 1.4%–11.1% |
| prompt+classifier+scan | 4.2% | 0.0%–8.3% |

- **Defense reduction (none → prompt+classifier+scan): −25.0%**
- Per-layer marginal: prompt −9.7%, prompt+classifier −13.9%, prompt+classifier+scan −1.4%
