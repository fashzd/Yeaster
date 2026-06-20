# yeaster_trap_vetter

Adversarial safety check on a token. Hard‑blocks **genuine rug/scam signals**
(honeypot, punitive buy/sell tax, unlocked liquidity, extreme whale
concentration) and returns a decisive **CLEAR / BLOCK** verdict plus the
token‑quality read. Soft signals (e.g. proxy contract, medium risk) are surfaced
as evidence but never block — they false‑flag bridged majors.

- **Cost:** medium (token‑quality + safety reads)
- **Implementation:** `yeaster/brain/vet.py` + `yeaster/guard/token_safety.py`

## Hard‑block flags

`security_flagged` · `honeypot_detected` · `tax_high` · `liquidity_unlocked`
(plus the guard's whale‑concentration + liquidity floor in the live trade path).

## Input

```json
{ "symbol": "ETH", "tags": [], "posture": "selective" }
```

## Output (data)

```json
{
  "symbol": "ETH", "tradeable": true, "verdict": "CLEAR",
  "hard_block_flags": [], "all_flags": [],
  "safety_quality": 0.0, "safety_coverage": 0.5,
  "reason": "no hard safety flags"
}
```

## Example

```bash
curl -s -X POST localhost:8000/api/skills/yeaster_trap_vetter \
  -H 'Content-Type: application/json' \
  -d '{"parameters": {"symbol": "ETH"}}' | jq
```
