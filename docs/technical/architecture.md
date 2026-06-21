# Yeaster — Architecture

Yeaster runs in **ticks** — one tick is a single sweep of `observe → reason →
(maybe) strike → record`. A single agent walks the passes in order; deterministic
rails own everything that can lose money.

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
   **BSC contract addresses** (`core/addresses.py`, CMC‑sourced, cached). A sell
   **approval is issued at entry** (`ensure_sell_approval`) so the later stop/TP/trail
   sell can't revert on a zero allowance.
4. **brackets** (`brackets.py`) — native stop/TP limit orders selling into the funded
   **USDT** reserve, reconcile on fill, an **ATR‑3× volatility‑scaled trailing ratchet**
   (`runtime/exits.py`), plus `cancel_orphans` / `cancel_all` for the unlock/kill controls.
5. **wallet truth** — the live wallet read merges an on‑chain **Multicall3 `balanceOf`
   sweep** over the resolved universe (`twak.py::_merge_onchain_holdings`), so it shows
   **every held token**, not just TWAK's tracked set; swept tokens are priced from CMC
   (never the mock oracle) or left unvalued.
6. **x402** (`x402.py`) — sells the daily alpha for an on‑chain‑verified USDT
   micropayment (off by default). See **`x402.md`**.

## Proof ledger (`yeaster/proof/ledger.py`)

Append‑only, sha256‑chained. Each block captures the snapshot, the per‑tick
`commit_record`, and the guard log; any later edit invalidates every downstream
hash. `verify_chain()` re‑checks the links.

## Runtime (`yeaster/runtime/`)

- `tick.py` — `run_tick()` (the spine: snapshot → exits → think → guard → execute →
  proof), `_execute_ticket()` (shared entry path), and the **≥1‑trade/day compliance**
  fallback. The commit **LLM is the decisive factor** — it stands down (no silent
  deterministic substitute) when unavailable.
- `daemon.py` — the autonomous loop with cadence (first tick immediate, then **2h live /
  120s paper**), auto‑resume, **timed committed runs**, a password **unlock** (`stop` →
  cleans orphaned automations, keeps brackets) and a password **kill switch** (`kill` →
  `flatten.py` sells all to USDT + cancels all).
- `state.py` — peak equity, drawdown, position book, Safe‑Mode latch, PnL/win‑rate,
  **consecutive‑loss streak + daily realized PnL** (fed to the commit LLM). Paper and
  live are **isolated** into separate files (`agent_state_{paper,live}.json`), keyed by
  the resolved backend — the two books never mix.
- `flatten.py` — emergency flatten‑to‑USDT used by the kill switch.

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
a **settings** modal (committed runs / kill switch), an **/intelligence** page
(regime, readiness screener, TWAK trending, CMC‑backed charts), and judge‑facing
**/learn** and **/alpha** (x402 buy‑alpha) pages.

## Tech stack

Python 3.10+ · FastAPI · pydantic v2 · requests · Next.js 14 / React 18 / Tailwind 4 ·
lightweight‑charts (CMC‑backed) · CoinMarketCap Agent Hub · Trust Wallet AgentKit ·
BNB Smart Chain · OpenAI/Anthropic (swappable).
