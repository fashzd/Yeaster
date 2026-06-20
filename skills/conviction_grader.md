# yeaster_conviction_grader 🏆

Grade a token across multiple signal dimensions into **one coverage‑weighted
composite** in `[-1, 1]`, with a **separate zero‑weight safety axis** (the SIREN
fix — safety is surfaced, never subtracted from the score). This is Yeaster's
flagship skill: a portable "how good is this token, and how sure are we?" scorer.

- **Cost:** high (fans out ~8 live CMC Skill‑Hub reads per call)
- **Implementation:** `yeaster/brain/grade.py` → `grade_candidate()`

## Dimensions

`kline` (technical structure) · `perp` (derivatives positioning) · `dark_flow`
(hidden accumulation) · `transition` (accumulation→breakout state) · `sector`
(rotation) · `whale` (smart‑money flow) · `unlock` (supply pressure) · `sentiment`
(social) — plus a separate `safety` axis (scam/honeypot/tax/holder concentration).

## Input

```json
{
  "symbol": "CAKE",                  // required
  "tags": ["breakout", "vol_surge"], // optional — routes the dimension weights by setup kind
  "posture": "selective"             // optional — hunt | selective | stand_down (regime weighting)
}
```

## Output (data)

```json
{
  "symbol": "CAKE", "kind": "breakout",
  "composite": 0.5230, "coverage": 0.889,
  "dims": { "kline": {"score": 0.45, "coverage": 1, "weight": 1.1, "evidence": {...}}, ... },
  "safety": { "quality_score": 0.1, "coverage": 0.5, "risk_flags": [], "evidence": {...} },
  "detect_tags": ["breakout", "vol_surge"]
}
```

`composite` is the coverage‑weighted mean of the directional dimensions × the
regime multiplier. `coverage` is the fraction of dimensions that returned real
data — surfaced so the caller can demand evidence depth. `safety` never moves the
composite.

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_conviction_grader \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"symbol": "CAKE", "tags": ["breakout"]}}' | jq
```
