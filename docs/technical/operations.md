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
- **Autonomous loop:** `POST /api/daemon/start {"cadence_seconds":120}`; `…/status`
- **Committed timed run:** `POST /api/daemon/start {"run_hours":4,"lock":true,"kill_password":"…","live":true}`
  → the chat locks (overrides → HTTP 423).
- **Unlock (graceful):** `POST /api/daemon/stop {"password":"…"}` → halts the loop, **sweeps orphaned
  automations, and keeps protective brackets** on open positions (they stay live on-chain).
- **Kill switch (emergency):** `POST /api/daemon/kill {"password":"…"}` → halts, **flattens every
  position to USDT, and cancels all automations**.
- All of the above are wired into the UI (lock button doubles as unlock; a separate red kill button). When
  `YST_OPERATOR_PASSWORD` is set, **unlock and kill always require it** — the kill switch is never unprotected.
- **Manual swaps need approval:** chat `buy 5% CAKE` / `sell CAKE` returns a *trade intent*; the operator approves
  it in the UI before it executes. **BNB** is allowed for manual swaps only (never an autonomous trade).
- **x402 alpha sales:** with `YST_X402=1`, `POST /api/x402/alpha` returns HTTP 402 + payment requirements until a
  buyer pays `YST_X402_PRICE_USD` USDT to `YST_X402_PAYTO` on BSC and submits the tx hash (verified on-chain,
  anti-replay). `GET /api/x402/alpha/teaser` shows the locked preview; `scripts/buy_alpha.py` is a buyer demo.
- **Skills:** `GET /api/skills` · `POST /api/skills/{name} {"parameters":{…}}`

### ≥1 trade/day & LLM-required
- The commit **LLM is the decisive factor** — if it's unavailable the tick **stands down** (surfaced in
  `last_error`), never silently substituting a deterministic pick.
- A **daily compliance** fallback (`YST_DAILY_COMPLIANCE`, after `YST_DAILY_CUTOFF_HOUR` UTC) places ONE
  safe, minimum-size trade if none happened that day — so the contest's ≥1-trade/day gate is never missed.

## Tests

```bash
pytest -q                 # indicators, approval permits, guard, brain, runtime/exits, skills,
                          # proof-chain, backtester, operator controls (orphan/kill/PnL/LLM-required)
```

## Going live (mainnet) — deliberate, gated

1. Fund the agent wallet with a little **BNB for gas** + **USDT** (the reserve entries/exits route through).
2. Set `YST_APPROVAL_SECRET` and `YST_X402_SECRET` to real secrets.
3. Open the gate: `YST_MAINNET=1` + `YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS`.
4. Start small: a single manual swap, confirm the tx + proof, then enable the loop.
5. Prefer a **committed run** with a kill‑switch password for unattended trading.

The mainnet path is **verified live** — a real fill (`0.5 USDT → CAKE`) executed through the guard, with a
native ATR-trailing bracket armed on-chain.

## Deploy on a server (always-on)

The native stop/TP **brackets are on-chain** — they fire via TWAK even if the host is offline. But the
**trailing ratchet, new entries, and the daily compliance trade run in the daemon loop**, so for the contest
the agent should live on an **always-on machine** (a cheap cloud VM), not a laptop that sleeps.

```bash
# on the server
git clone <repo> && cd yeaster
python -m venv venv && . venv/bin/activate && pip install -e .
cp .env.example .env       # fill keys + (when ready) the YST_MAINNET gate
set -a; . ./.env; set +a
uvicorn yeaster.api.app:app --host 0.0.0.0 --port 8000      # API + auto_resume of the daemon
# web UI (separate process): cd web && npm ci && npm run build && npm run start
```

Keep it alive with **systemd / pm2 / nohup** (the daemon `auto_resume`s its last committed run on restart).
Then drive everything from the UI: start + lock a run, unlock (password) to stop safely, or hit the kill
switch to flatten. The mainnet gate is read from the **server's** environment.

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
