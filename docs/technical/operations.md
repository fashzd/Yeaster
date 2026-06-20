# Yeaster — Operations

## Install

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # runs on mock/paper with no keys
```

## Run

```bash
# backend (load env first)
set -a && source .env && set +a
uvicorn yeaster.api.app:app --port 8000
curl -s localhost:8000/api/health
curl -s localhost:8000/api/readiness    # per-layer live check

# control room
cd web && npm install && npm run dev     # http://localhost:3000
```

## Prove the pipeline (offline → verified proof)

```bash
python scripts/paper_cycle.py            # snapshot → think → guard → paper exec → proof
```

## Drive it

- **Run one tick:** `POST /api/agent/tick {"cmc_backend":"mock","twak_backend":"paper","arm":"det_safety"}`
- **Watch it think (SSE):** `POST /api/agent/tick/stream`
- **Manual swap:** `POST /api/agent/manual {"to_asset":"CAKE","amount_pct":0.05}`
- **Autonomous loop:** `POST /api/daemon/start {"cadence_seconds":120}`; `…/stop`; `…/status`
- **Committed timed run:** `POST /api/daemon/start {"run_hours":4,"lock":true,"kill_password":"…","live":true}`
  → the chat locks; halt early with `POST /api/daemon/stop {"password":"…"}`.
- **Skills:** `GET /api/skills` · `POST /api/skills/{name} {"parameters":{…}}`

## Tests

```bash
pytest -q                 # 36 tests: indicators, approval permits, guard, brain,
                          # runtime/exits, skills, proof-chain integrity
```

## Going live (mainnet) — deliberate, gated

1. Fund the agent wallet with a little **BNB for gas** + the stable you trade from.
2. Set `YST_APPROVAL_SECRET` and `YST_X402_SECRET` to real secrets.
3. Open the gate: `YST_MAINNET=1` + `YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS`.
4. Start small: a single manual swap, confirm the tx + proof, then enable the loop.
5. Prefer a **committed run** with a kill‑switch password for unattended trading.

The mainnet quote/execute path is verified live (real quotes resolve via canonical
BSC contract addresses); a real fill needs gas in the wallet.

## Observability

- `GET /api/agent` — equity, drawdown, PnL, win‑rate, positions, recent exits.
- `GET /api/wallet` (book) · `GET /api/wallet?backend=cli` (real self‑custody wallet) · `GET /api/wallet/brackets`.
- `GET /api/proof` — the chain tail + `verified` flag.
- `GET /api/x402` — micropayment settlement trail (when enabled).
- `data/` (gitignored): `state/` (agent + daemon), `proof/` (chain), `wallet/` (paper + caches), `snapshots/`.

## Safety notes

- The firewall, sizing rails, drawdown brakes, and kill switch cannot be bypassed by the decision layer.
- De‑risk exits (risk→stable) are always permitted, even under Safe Mode.
- A drawdown breach latches Safe Mode (persisted across restarts) until an operator unwinds.
