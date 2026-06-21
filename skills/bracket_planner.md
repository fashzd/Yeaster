# yeaster_bracket_planner

Plan native exit brackets for a long entry — stop‑loss, take‑profit, and trailing
stop — using Yeaster's finalized **let‑winners‑run** calibration (default **8%
stop / 40% take‑profit**, a 5:1 reward:risk). The live engine trails at **ATR‑3×**
(volatility‑scaled); this pure‑math skill returns the fixed trailing fallback used
when a coin lacks the history for ATR. Instant, no network.

- **Cost:** low (no network, no LLM)
- **Implementation:** `yeaster/skills/catalog.py` → `_brackets()` (preset `yeaster/core/preset.py`)

## Input

```json
{
  "entry_price": 2.40,    // required
  "stop_pct": 0.08,       // optional overrides (default from the finalized preset)
  "tp_pct": 0.40,
  "trailing_pct": 0.03    // fixed fallback; the live engine trails at ATR-3x
}
```

## Output (data)

```json
{
  "entry_price": 2.40,
  "stop_price": 2.208,          // -8%
  "take_profit_price": 3.36,    // +40%
  "stop_pct": 0.08, "tp_pct": 0.40, "trailing_pct": 0.03,
  "risk_reward": 5.0,
  "note": "let-winners-run calibration; the live engine trails at ATR-3x (trailing_pct here is the fixed fallback)"
}
```

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_bracket_planner \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"entry_price": 2.40}}' | jq
```
