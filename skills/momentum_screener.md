# yeaster_momentum_screener

Scout a token universe for momentum candidates by fusing several **independent
detectors**, each surfacing coins a different way. A coin hit by multiple
detectors ranks higher (cross‑source agreement), so the screen produces signal
even when any single breakout scanner is empty.

- **Cost:** medium (one live snapshot + the social/overview Skill‑Hub scans)
- **Implementation:** `yeaster/brain/screen.py` → `screen()`

## Detectors

`rel_strength` (decoupled leader) · `breakout` (new 20‑day high on volume) ·
`accumulation` (tight coiling base) · `mean_revert` (oversold snapback) ·
`vol_surge` (abnormal participation) · `extended_runner` (durable distributed
uptrend) · `scanner_spot` (social breakout scanner) · `overview_*` (daily
market‑overview lanes).

## Input

```json
{
  "backend": "auto",          // auto | rest | mcp | mock
  "universe": ["ETH","CAKE"], // optional — defaults to the 148-token whitelist's momentum set
  "detectors": ["rel_strength","breakout"], // optional subset
  "bars": { "CAKE": [ {"price": 2.4, "volume": 1000}, ... ] }, // optional daily bars for structural detectors
  "limit": 25
}
```

## Output (data)

```json
{
  "backend": "rest", "count": 9,
  "candidates": [
    {"symbol": "APE", "tags": ["overview_readout", "rel_strength"], "score": 2},
    {"symbol": "AXS", "tags": ["overview_readout", "rel_strength"], "score": 2},
    {"symbol": "RAY", "tags": ["rel_strength"], "score": 1}
  ]
}
```

`score` = number of distinct detectors that agreed (higher = stronger conviction).

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_momentum_screener \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"backend": "auto", "limit": 8}}' | jq
```
