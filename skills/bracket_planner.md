# yeaster_bracket_planner

Plan native exit brackets for a long entry — stop‑loss, take‑profit, and trailing
stop — using Yeaster's finalized **let‑winners‑run** calibration (default **8%
stop / 16% take‑profit / 3% trailing**, a 2:1 reward:risk). Pure math, instant.

- **Cost:** low (no network, no LLM)
- **Implementation:** `yeaster/skills/catalog.py` → `_brackets()` (preset `yeaster/core/preset.py`)

## Input

```json
{
  "entry_price": 2.40,    // required
  "stop_pct": 0.08,       // optional overrides (default from the finalized preset)
  "tp_pct": 0.16,
  "trailing_pct": 0.03
}
```

## Output (data)

```json
{
  "entry_price": 2.40,
  "stop_price": 2.208,          // -8%
  "take_profit_price": 2.784,   // +16%
  "stop_pct": 0.08, "tp_pct": 0.16, "trailing_pct": 0.03,
  "risk_reward": 2.0,
  "note": "let-winners-run calibration (wide stop, wider target, trailing ratchet)"
}
```

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_bracket_planner \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"entry_price": 2.40}}' | jq
```
