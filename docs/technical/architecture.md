# Yeaster — Architecture

The unit of work is a **tick**: `observe → reason → (maybe) act → record`. One
agent reasons in sequential passes; deterministic rails own everything that can
lose money.

```
 THE MARKET ─▶ SCREEN ─▶ GRADE ─▶ VET ─▶ COMMIT ─▶ GUARD ─▶ EXECUTE ─▶ PROOF
              (scout)   (grade)  (scrutiny)(size  (firewall)(TWAK swap (tamper-
              candidates every    + safety) + pick)         + brackets) evident)
```

## The brain (`yeaster/brain/`)

Driven by `cycle.py` (`think()` / `think_events()` — the deterministic stage runner
that also streams each reasoning pass to the UI). LLM use is confined to the
grade/vet/commit passes where it adds edge, with deterministic fallbacks so an LLM
outage degrades to NO_TRADE, never a bad trade.

1. **screen** (`screen.py`) — fuses independent detectors (rel_strength, breakout,
   accumulation, mean_revert, vol_surge, extended_runner) + skill detectors
   (social scanner, daily overview) into a tagged candidate list. Cross‑source
   agreement = higher rank.
2. **grade** (`grade.py` + `dimensions.py`) — scores every candidate across 8
   directional dimensions (kline, perp, dark_flow, transition, sentiment, sector,
   whale, unlock) into a **coverage‑weighted composite**, plus a **separate
   zero‑weight safety axis** (`token_quality`). Regime + detector‑kind routing
   weight the dimensions. Never discards.
3. **vet** (`vet.py`) — deterministic hard‑block on genuine rug/scam flags +
   optional LLM critic that refutes survivors.
4. **commit** (`commit.py`) — the policy arm (LLM "lead" / deterministic) picks one
   survivor; the **rails** turn conviction into notional under R‑based sizing,
   drawdown brakes, and caps. Emits an `OrderTicket` or stands down.

## Safety firewall (`yeaster/guard/`)

`YeasterGuard.evaluate()` runs seven deterministic checks — allowlist, single‑trade
cap, position cap, slippage, epoch, hard‑drawdown, Safe‑Mode — with a **de‑risk
carve‑out** (a risk→stable exit is never trapped) and a **Safe‑Mode latch** on a
drawdown breach. `token_safety.py` adds whale‑concentration + liquidity floors.

## Execution (`yeaster/execution/`)

Two‑step, self‑custodial, via Trust Wallet AgentKit:
1. **quote** (`twak.py`) → `SwapQuote{quote_hash, slippage}`. The `SwapRequest`
   validator enforces the **mainnet double‑gate**.
2. **approval** (`approval.py`) → an HMAC‑signed, quote‑bound permit, mintable only
   from an EXECUTED guard decision (replay/forgery/expiry‑proof).
3. **execute** → real swap (CLI) or paper sim. Token symbols resolve to canonical
   **BSC contract addresses** (`core/addresses.py`, CMC‑sourced, cached).
4. **brackets** (`brackets.py`) — native stop/TP limit orders, reconcile on fill,
   trailing ratchet (`runtime/exits.py`).
5. **x402** (`x402.py`) — HMAC‑signed micropayment middleware (off by default).

## Proof ledger (`yeaster/proof/ledger.py`)

Append‑only, sha256‑chained. Each block captures the snapshot, the per‑tick
`commit_record`, and the guard log; any later edit invalidates every downstream
hash. `verify_chain()` re‑checks the links.

## Runtime (`yeaster/runtime/`)

- `tick.py` — `run_tick()` (the spine: snapshot → exits → think → guard → execute →
  proof) and `run_manual()` (operator swaps).
- `daemon.py` — the autonomous loop with cadence, auto‑resume, **timed committed
  runs**, lock, and a password kill switch.
- `state.py` — peak equity, drawdown, position book, Safe‑Mode latch, PnL/win‑rate.

## API (`yeaster/api/`)

Router‑structured FastAPI: `health` (+ readiness), `agent` (tick + SSE stream +
manual + status/positions), `wallet` (+ brackets), `market` (overview, snapshot,
token, series, trending, intelligence), `proof`, `daemon`, `x402`, `skills`.

## Skills (`yeaster/skills/`)

The brain's stages wrapped as 5 composable, read‑only Track‑2 skills behind a
registry + `/api/skills`. The internal pipeline calls the modules **in‑process** —
it never HTTP‑calls the skill endpoints, so they add no latency to the trade loop.

## Web (`web/`)

Next.js "Liquid Flow" control room: a fused **terminal** (live SSE reasoning) +
**chat**, dashboard blobs (TWAK wallet/PnL, brackets, CMC movers, Fear&Greed, proof),
a **settings** modal (committed runs / kill switch), and a **/intelligence** page
(regime, readiness screener, TWAK trending, TradingView).

## Tech stack

Python 3.10+ · FastAPI · pydantic v2 · requests · Next.js 14 / React 18 / Tailwind 4 ·
lightweight‑charts + TradingView · CoinMarketCap Agent Hub · Trust Wallet AgentKit ·
BNB Smart Chain · OpenAI/Anthropic (swappable).
