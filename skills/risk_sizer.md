# yeaster_risk_sizer

Size a position from **conviction + equity + drawdown** using Yeaster's R‑based
risk rails: 0.7% R, a 3.5% stop divisor, drawdown brakes (halve risk at 9%, halt
new entries at 15%), and a 30% per‑name cap. Pure math, instant.

- **Cost:** low (no network, no LLM)
- **Implementation:** `yeaster/brain/commit.py` → `size_amount_pct()`

## Input

```json
{
  "conviction": 0.70,    // required, 0..1
  "equity_usd": 1000.0,  // required
  "drawdown_pct": 0.0    // optional, 0..1
}
```

## Output (data)

```json
{
  "amount_pct": 0.14,            // portfolio fraction to deploy (null if halted)
  "notional_usd": 140.0,
  "halted": false, "halt_reason": null,
  "dd_halfsize_applied": false,
  "params": { "risk_per_trade": 0.007, "stop_pct": 0.035, "dd_halfsize": 0.09,
              "dd_halt": 0.15, "max_position_pct": 0.30 }
}
```

At `drawdown_pct >= 0.15` the sizer returns `halted: true` / `amount_pct: null`
(the hard brake); between 0.09 and 0.15 it halves the risk.

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_risk_sizer \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"conviction": 0.7, "equity_usd": 1000, "drawdown_pct": 0.0}}' | jq
```
