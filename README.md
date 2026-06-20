<div align="center">

# ⚡ YEASTER

### A self-custodial momentum predator for the BNB Smart Chain — it hunts, it reasons, it strikes, and it leaves a receipt for every move.

**Built for [BNB HACK: AI Trading Agent Edition](https://coinmarketcap.com/api/hackathon/)** — BNB Chain × CoinMarketCap × Trust Wallet.

[![Hackathon — CoinMarketCap](https://img.shields.io/badge/BNB_HACK-CoinMarketCap-F0B90B?style=for-the-badge)](https://coinmarketcap.com/api/hackathon/)
[![Submission — DoraHacks](https://img.shields.io/badge/Submit-DoraHacks-7B61FF?style=for-the-badge)](https://dorahacks.io/hackathon/bnbhack-twt-cmc/)
[![Tracks](https://img.shields.io/badge/Tracks-1_Agent_%2B_2_Skills-00D395?style=for-the-badge)](#-track-1--the-autonomous-trading-agent-deep-dive)

</div>

---

Yeaster is **one agent with one wallet** that thinks in disciplined passes, fires its own on-chain swaps, arms its own exits, and seals every decision into a tamper-evident proof chain. No human in the loop while it runs. No way for the thinking layer to outrun the safety rails. No trade that isn't already accounted for the moment it's signed.

It enters **BNB HACK on both tracks at once**: a complete **Track 1 autonomous trading agent**, and the same brain unbundled into **Track 2 strategy skills** any other agent can call.

> **It would rather hold cash than hold a bad bet.** Yeaster does not pretend to see the future. It hunts asymmetric momentum, refuses traps on principle, kills losers without ego, and lets the rare winner run. When the tape is ugly it shrinks itself — or sits flat. **A day with zero trades is a win, not a failure.**

---

## 🔥 Why Yeaster is different

- **A mind, not a swarm.** Most "agent" entries are a committee of bots passing messages. Yeaster is a *single reasoning process* moving through fixed stages — auditable, deterministic in order, impossible to deadlock.
- **The thinker is caged.** The LLM never touches money. It picks *from* a pre-vetted shortlist; sizing, safety, and the kill-switches live in code the model cannot reach or override. **Smarts on top, hard rails underneath.**
- **Safety is its own axis — it never lies about danger.** A token we *can't verify* is flagged, not slandered. Scam risk is surfaced on a separate channel that can veto a trade but can never quietly drag a good grade down (the bug we hunted and killed: "SIREN").
- **Every move is provable.** A SHA-256-linked ledger means anyone can replay the agent's entire history and confirm nothing was edited after the fact.
- **It runs unattended for real.** Launch a committed N-hour mission, the chat **locks**, and the only way to stop it early is a **password-gated kill switch**.

---

## 🎯 Track 1 — The Autonomous Trading Agent (deep dive)

Track 1 is the heart of the submission: a trading agent that operates **end to end with no human in the decision path**. Here is exactly how it works.

### The hunt loop

Yeaster runs in **ticks** — each tick is one full sweep of *observe → reason → (maybe) strike → record*. A background daemon fires ticks on a cadence and **auto-resumes** across restarts, so the agent keeps its posture, positions, and PnL memory even after a crash or redeploy.

```
  LIVE MARKET
      │
      ▼
   SCREEN   ── scout the 148-token universe for momentum candidates
      │        (relative strength · breakouts · extended runners · volume surges · spot scanner)
      ▼
   GRADE    ── score each survivor across 8 CoinMarketCap dimensions
      │        into one coverage-weighted composite ∈ [-1, 1]
      ▼
   VET      ── adversarial trap check: honeypot / rug / scam on a SEPARATE safety axis
      │
      ▼
   COMMIT   ── the LLM lead + critic pick ONE name (or pass) from the safe shortlist;
      │        R-based sizing, braked by current drawdown
      ▼
   GUARD    ── non-bypassable firewall: 7 hard checks, sells-to-cash always allowed
      │
      ▼
   EXECUTE  ── Trust Wallet swap → native stop / take-profit / trailing brackets armed on-chain
      │
      ▼
   PROOF    ── the whole decision + guard log + outcome sealed into the SHA-256 chain
```

### What makes the autonomy trustworthy

1. **Bounded universe.** The agent can only ever touch the **148-token competition whitelist**. This is enforced twice — in the guard firewall *and* in the chat command path — so neither the model nor a human operator can wander off the allowed venue.
2. **Coverage-honest grading.** Each of the 8 dimensions reports not just a score but *how much real data backed it*. The composite is weighted by that coverage, so a thinly-sourced opinion can't masquerade as conviction.
3. **Safety can veto, never poison.** Scam/honeypot risk rides a dedicated axis with **zero weight in the composite**. It can hard-block a trade — but an unverifiable token is never silently scored as "bad." Honesty over fear.
4. **R-based sizing with a drawdown brake.** Bets are sized in units of risk (R), and the size automatically shrinks as drawdown grows. Lose, and Yeaster gets smaller. Keep losing, and it latches into safe mode.
5. **Let-winners-run exits, fired on-chain.** Every fill arms a native bracket — **8% stop · 16% take-profit · 3% trailing** — on the execution layer itself, so protection survives even if the brain goes offline.
6. **PnL-aware reasoning.** Realized + unrealized PnL, win-rate, and recent exit outcomes are fed back into the commit stage. The agent *remembers how it's been doing* and trades accordingly.
7. **Committed, locked missions.** An operator can launch a timed run (run for N hours), at which point the chat **locks**, operator overrides are rejected (HTTP 423), and the run auto-stops on schedule — abortable only via the **password kill switch**.
8. **Paper by default, mainnet behind a double-gate.** No real funds move until both `YST_MAINNET=1` and `YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS` are set. Everything above is exercised on paper / BSC testnet first.

### The three sponsors, fused into one decision

| Sponsor | What Yeaster pulls from it |
|---|---|
| **CoinMarketCap Agent Hub** | Market regime, technicals, derivatives, whale flow, sector rotation, unlock schedules, social signal, Fear & Greed, and scam/honeypot safety — fused into the grade. |
| **Trust Wallet (TWAK)** | Self-custodial on-chain swaps + native auto-brackets (stop / TP / trailing), token-risk reads, trending. x402 micropayments wired and available. |
| **BNB Smart Chain** | The on-chain venue. The 148-token whitelist *is* the hard universe — chain id 56. |

---

## 🧪 Track 2 — Strategy Skills

Yeaster's brain doesn't stay locked inside Yeaster. Each reasoning stage is also shipped as a **standalone, composable skill** — JSON in, evidence-pack out — that any other agent can discover and invoke. Browse them at `GET /api/skills`, call one at `POST /api/skills/{name}`. Full docs in **[`skills/`](skills/)**.

| Skill | What it returns |
|-------|---------|
| `yeaster_conviction_grader` 🏆 | Coverage-weighted multi-dimensional grade + the separate safety axis |
| `yeaster_momentum_screener` | Cross-source momentum candidates from the live universe |
| `yeaster_trap_vetter` | Adversarial rug / honeypot / scam verdict |
| `yeaster_bracket_planner` | Let-winners-run exit brackets (8% / 16% / 3%) |
| `yeaster_risk_sizer` | R-based position size with a drawdown brake |

---

## 🛰️ Liquid Flow — the control room

A single fused **agent terminal + chat**, glass dashboards, and a **Market Intelligence** page (CMC regime · Fear & Greed gauge · readiness screener · TWAK trending · embedded TradingView). Watch the agent reason live, `$SYM` any token for a deep-dive card with inline charts, fire a manual buy/sell, flip the guard or trading mode, or kick a cycle by hand.

---

## 🗺️ Repository layout

```
yeaster/
  core/        contracts · typed YST_ settings · the 148-token whitelist · BSC resolver · the Momentum preset
  market/      CoinMarketCap ingestion (REST / MCP / mock) · Skill-Hub client · indicators
  brain/       screen → grade → vet → commit, driven by the cycle runner (+ the LLM backbone)
  guard/       YeasterGuard firewall + token-safety module
  execution/   Trust Wallet AgentKit: quote → approve → swap → native brackets · x402 middleware
  proof/       SHA-256-chained proof ledger
  runtime/     the autonomous daemon (timed / locked runs) · persisted state · exit reconciliation
  skills/      the 5 Track-2 strategy skills (registry + catalog)
  api/         router-structured FastAPI surface
web/             Next.js "Liquid Flow" control room (terminal + chat + dashboards + /intelligence)
skills/          judge-facing skill docs + machine manifest
docs/technical/  the full documentation set (start here)
tests/           pytest suite (36 tests)
```

## 🚀 Quickstart

```bash
# 1. Python — installable package
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# 2. Config — runs on mock/paper with zero keys; fill in for live data + execution
cp .env.example .env

# 3. Backend — paper by default, no funds at risk
set -a && source .env && set +a
uvicorn yeaster.api.app:app --port 8000
curl -s localhost:8000/api/health

# 4. Control room
cd web && npm install && npm run dev      # http://localhost:3000
```

Drive the whole pipeline offline, end to end, into a verified proof block:

```bash
python scripts/paper_cycle.py
```

## 🔒 Safety: the real-funds gate

Live mainnet execution demands **both** switches, together:

```dotenv
YST_MAINNET=1
YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS
```

Drop either one and the agent stays on paper / BSC testnet no matter what else is set. The firewall, the R-based sizing rails, the drawdown brakes, and the password kill switch are owned by code — **the decision layer cannot reach around any of them.**

## 📚 Documentation

- **[`docs/technical/`](docs/technical/)** — overview · architecture · configuration · operations
- **[`skills/`](skills/)** — the Track-2 strategy skills
- `docs/AGENTS.md` — the build ledger

## 🔗 Hackathon

- **Program:** [CoinMarketCap × BNB Chain × Trust Wallet — BNB HACK](https://coinmarketcap.com/api/hackathon/)
- **Submission:** [DoraHacks — bnbhack-twt-cmc](https://dorahacks.io/hackathon/bnbhack-twt-cmc/)

<div align="center">

**Yeaster** — *it rises when the market does.*

</div>
