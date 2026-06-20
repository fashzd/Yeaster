# Yeaster Strategy Skills — BNB HACK Track 2

Five composable, JSON-in / evidence-pack-out **strategy skills**, each a thin
wrapper over a stage of Yeaster's trading brain. They are pure and read-only —
they compute and return evidence; they never trade, mutate state, or touch a
wallet — so any agent or builder can reuse them safely.

> Implementation: [`../yeaster/skills/catalog.py`](../yeaster/skills/catalog.py)
> · contract: [`../yeaster/skills/base.py`](../yeaster/skills/base.py)
> · machine manifest: [`manifest.json`](manifest.json)

## The skills

| Skill | What it does | Cost |
|-------|--------------|------|
| [`yeaster_conviction_grader`](conviction_grader.md) 🏆 | Grade a token across 8 signal dimensions into one coverage‑weighted composite, with a **separate zero‑weight safety axis** | high |
| [`yeaster_momentum_screener`](momentum_screener.md) | Scout a universe for momentum candidates by fusing independent detectors (cross‑source agreement) | medium |
| [`yeaster_trap_vetter`](trap_vetter.md) | Adversarial safety check — hard‑blocks genuine rug/scam signals; CLEAR / BLOCK verdict | medium |
| [`yeaster_bracket_planner`](bracket_planner.md) | Plan native exit brackets (stop / take‑profit / trailing) with the proven let‑winners‑run calibration | low |
| [`yeaster_risk_sizer`](risk_sizer.md) | Size a position from conviction + equity + drawdown (R‑based, drawdown‑braked) | low |

## Discover & invoke

```bash
# discover (manifest with JSON Schemas)
curl -s localhost:8000/api/skills | jq

# invoke a skill
curl -s -X POST localhost:8000/api/skills/yeaster_bracket_planner \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"entry_price": 2.40}}' | jq
```

Every invocation returns the uniform envelope:

```json
{ "skill": "<unique_name>", "ok": true, "summary": "", "data": { ... } }
```

## Why these are good skills

- **Composable** — drop any one into another agent's loop; they don't assume Yeaster.
- **Honest about evidence** — the grader surfaces *coverage* (how much real data backed the
  score) and keeps **safety as a separate, never‑subtracted axis** (so an unverifiable token
  isn't wrongly treated as unsafe — the "SIREN" lesson).
- **Self‑custody friendly** — read‑only; they inform decisions, they never move funds.
- **Same edge as the live agent** — these wrap the exact modules Yeaster trades with.
