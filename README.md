# 🌊 Yeaster

**An autonomous BNB Smart Chain momentum trading agent — one mind, orchestrated stages.**

Built for **BNB HACK: AI Trading Agent Edition** (BNB Chain × CoinMarketCap × Trust Wallet).
Yeaster reads the market, reasons about it in distinct internal passes, sizes and places its own
trades behind a non‑bypassable safety firewall, and records every decision in a tamper‑evident proof
ledger — with funds held **self‑custodially** in a single wallet. It competes in **both tracks**:
an **Autonomous Trading Agent** and a set of reusable **Strategy Skills**.

> **Capital preservation first.** Yeaster avoids traps, trades deliberately, cuts losers fast, lets
> winners run, and automatically shrinks or halts its own risk when losing. "Do nothing today" is a
> valid, frequent, intended outcome.

---

## Three sponsors, one loop

- **CoinMarketCap Agent Hub** — market regime, technicals, derivatives, whale flow, sector rotation,
  unlocks, social, and scam/honeypot safety, fused into the agent's grade.
- **Trust Wallet (TWAK)** — self‑custodial execution: real on‑chain swaps + native auto‑brackets
  (stop / take‑profit / trailing), token‑risk reads, and trending. x402 micropayments available.
- **BNB Smart Chain** — the on‑chain venue; the 148‑token competition whitelist is the hard universe.

## How it thinks — one agent, reasoning in stages

```
 THE MARKET ─▶ SCREEN ─▶ GRADE ─▶ VET ─▶ COMMIT ─▶ GUARD ─▶ EXECUTE ─▶ PROOF
              (scout)   (grade)  (scrutiny)(size  (firewall)(TWAK swap (tamper-
              candidates every    + safety) + pick)         + brackets) evident)
```

Yeaster is **one agent**. Its brain is not a roster of separate agents — it is a single mind that
reasons in sequential passes, driven by a deterministic `cycle` runner. **Policy proposes, rails
dispose:** the LLM‑backed passes only *select within a safe shortlist*; deterministic rails own
sizing, safety, and the kill‑switches, so even an experimental decision‑maker can never place an
unsafe trade or spend real funds.

## What it does

- **Autonomous operation** — a background daemon runs the full cycle on a cadence, with auto‑resume.
- **Committed runs** — set a runtime (N hours); the agent trades unattended, the chat **locks**, and a
  **password‑protected kill switch** can halt it early.
- **Multi‑signal grading** across 8 dimensions with a coverage‑weighted composite and a **separate,
  never‑subtracted safety axis** (the "SIREN" fix).
- **PnL‑aware feedback loop** — realized/unrealized PnL, win‑rate, and recent outcomes feed the decision.
- **Non‑bypassable firewall** — allow‑list (148 tokens), size/slippage/drawdown caps, token‑safety,
  with a "sell back to cash is always allowed" carve‑out.
- **Native self‑firing exits** — stop / take‑profit / trailing on the execution layer.
- **Tamper‑evident proof chain** of every decision and trade.
- **Liquid Flow control room** — a fused agent **terminal + chat**, dashboards, and a **Market
  Intelligence** page (CMC regime + Fear&Greed + readiness screener + TWAK trending + TradingView).
- **Safe by default** — paper/testnet until a human opens the mainnet double‑gate.

## Track 2 — Strategy Skills

Five composable, JSON‑in / evidence‑pack‑out skills (the brain's stages, reusable by any agent).
Discover at `GET /api/skills`, invoke at `POST /api/skills/{name}`. See **[`skills/`](skills/)**.

| Skill | Purpose |
|-------|---------|
| `yeaster_conviction_grader` 🏆 | Coverage‑weighted multi‑dimensional token grade + separate safety axis |
| `yeaster_momentum_screener` | Cross‑source momentum candidate discovery |
| `yeaster_trap_vetter` | Adversarial rug/scam safety verdict |
| `yeaster_bracket_planner` | Let‑winners‑run exit brackets (8% / 16% / 3%) |
| `yeaster_risk_sizer` | R‑based, drawdown‑braked position sizing |

## Repository layout

```
yeaster/
  core/        contracts, typed YST_ settings, the 148-token whitelist, BSC address resolver, preset
  market/      CoinMarketCap data (REST/MCP/mock) + Skill-Hub client + indicators
  brain/       screen → grade → vet → commit, driven by the cycle runner (+ the LLM backbone)
  guard/       YeasterGuard firewall + token safety
  execution/   Trust Wallet AgentKit: quote → approval → swap → native brackets; x402 middleware
  proof/       sha256-chained proof ledger
  runtime/     the autonomous daemon (timed/locked runs) + persisted state + exits
  skills/      the 5 Track-2 strategy skills (registry + catalog)
  api/         router-structured FastAPI surface
web/           Next.js "Liquid Flow" control room (terminal + chat + dashboards + /intelligence)
skills/        judge-facing skill docs + machine manifest
docs/technical/ the documentation set (start here)
tests/         pytest suite (36 tests)
```

## Quickstart

```bash
# 1. Python
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# 2. Config (runs on mock/paper with no keys; fill in for live)
cp .env.example .env

# 3. Backend (paper by default — no funds at risk)
set -a && source .env && set +a
uvicorn yeaster.api.app:app --port 8000
curl -s localhost:8000/api/health

# 4. Control room
cd web && npm install && npm run dev      # http://localhost:3000
```

Prove the whole pipeline offline → a verified proof block:

```bash
python scripts/paper_cycle.py
```

## Safety

Real mainnet execution is gated behind **both** `YST_MAINNET=1` **and**
`YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS`. By default the agent runs on paper / BSC testnet.
The firewall, sizing rails, drawdown brakes, and the password kill switch cannot be bypassed by the
decision layer.

## Documentation

- **[`docs/technical/`](docs/technical/)** — overview, architecture, configuration, operations
- **[`skills/`](skills/)** — the Track‑2 strategy skills
- `docs/AGENTS.md` — the build ledger
