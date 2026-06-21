# Yeaster — Configuration

All Yeaster‑owned knobs use the `YST_` prefix; everything else authenticates to a
third‑party service (and keeps its vendor prefix). Config is loaded once into a
typed object — `yeaster/core/settings.py` (`get_settings()`). See `.env.example`.

## Third‑party credentials (kept as‑is)

| Var | Purpose |
|---|---|
| `CMC_API_KEY` / `CMC_MCP_API_KEY` | CoinMarketCap data + Skill Hub |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | LLM backbone (one is enough; OpenAI default) |
| `TWAK_CLI_BIN`, `TWAK_MCP_URL`, `TWAK_*`, `TW_*` | Trust Wallet AgentKit |
| `TWAK_WALLET_PASSWORD` | wallet keychain (read by `twak`, never passed on the CLI) |
| `BSC_TESTNET_RPC_URL` / `BSC_TESTNET_WALLET_ADDRESS` / `BSC_TESTNET_PRIVATE_KEY` | BNB testnet |

## Yeaster knobs (`YST_`)

| Var | Default | Effect |
|---|---|---|
| `YST_USE_SKILLS` | `1` | enable the CMC Skill‑Hub grade dimensions |
| `YST_SKILLS_BACKEND` | `auto` | `auto` / `mcp` / `rest` / `mock` |
| `YST_LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `YST_LLM_MODEL` | (provider default) | `gpt-5-mini` / `claude-haiku-4-5-…` |
| `YST_COMMIT_ARM` | `llm_lead` | commit policy arm (`llm_lead` / `det_top` / `det_safety`) |
| `YST_COMMIT_STYLE` | `aggressive` | `aggressive` or `disciplined` lead |
| `YST_EXIT_MODE` | `native` | native TWAK brackets vs emulated |
| `YST_GRADE_CAP` | `12` | max candidates graded per tick (caps skill calls) |
| `YST_DAILY_COMPLIANCE` | `1` | force ≥1 trade/day (contest gate): a safe min-size trade if none happened |
| `YST_DAILY_CUTOFF_HOUR` | `21` | UTC hour after which the compliance trade may fire |
| `YST_WIDE_SNAPSHOT` | `1` | snapshot the full universe |
| `YST_WHALE_CONCENTRATION_LIMIT_PCT` | `30.0` | token‑safety whale cap |
| `YST_TRADE_CHAIN_ID` | `56` | target chain (97 testnet / 56 mainnet) |
| `YST_PORTFOLIO_CHAIN` | `bsc` | chain the live wallet is read from |
| `YST_APPROVAL_SECRET` | dev default | HMAC permit key — **set in prod** |
| `YST_OPERATOR_PASSWORD` | (unset) | master password for **unlock + kill switch** — set in prod so the kill switch is always authenticated |
| `YST_SWAP_SPENDER` | LiquidMesh router | the router approved at entry so exits/stops/TP can sell (override if TWAK routes elsewhere) |
| `YST_MIN_NOTIONAL_USD` | `1.2` | **contest minimum trade size.** No trade executes below this (hard guard on the actual USDT spent, organic + compliance). The mandatory ≥1/day compliance trade **sizes up** to clear it with margin (~`floor × 1.30`), so it always fires at the minimum regardless of wallet size. |
| `YST_WALLET_SWEEP` | `1` | on the live wallet read, merge an on-chain Multicall3 `balanceOf` sweep so **every held token shows** (not just TWAK's tracked set) |
| `YST_X402` / `YST_X402_SECRET` | `0` / dev | x402 micropayments + **alpha sales** (off by default) — see `x402.md` |
| `YST_X402_PRICE_USD` / `YST_X402_PAYTO` | `0.10` / agent wallet | price (USDT) + recipient for buying the daily alpha |

## The real‑funds gate (mainnet)

Real mainnet execution requires **both**:

```bash
YST_MAINNET=1
YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS
```

With the gate closed, `auto` backends resolve to **paper** everywhere and the agent
never touches the chain. With it open, `auto` → live CLI and chain 56 is permitted.

**Operating posture (gate kept open).** In this deployment the gate is left open so
the operator flips between paper and live from the control room's **live toggle**, with
the **operator password** guarding the kill switch. Safety does not rest on the gate —
it rests on backend resolution: the UI sends an **explicit** `twak_backend` (`paper`
for paper, `auto` for live), so a paper run stays virtual even with the gate open. A
non-UI caller MUST pass an explicit `twak_backend` — do not rely on the daemon's
cosmetic `live` flag, which is metadata, not an execution gate.

**Paper / live state are isolated.** Position book, realized PnL, loss streak and the
safe-mode latch live in **separate files** — `data/state/agent_state_paper.json` vs
`agent_state_live.json` — keyed by the resolved backend (`state.state_mode()`). Paper
and live never bleed into each other; read endpoints take a `mode`/`backend` argument.
Do not hand-edit these files; reset paper state by deleting its file (a fresh `_DEFAULT`
is created on next read).

**Autonomous cadence.** The daemon runs the first tick **immediately**, then waits the
cadence. The control room sets it by mode: **7200s (2h)** for live, **120s** for paper.
The library default (`DEFAULT_CADENCE_SECONDS`, non-UI callers) is 300s.

## The strategy preset

`yeaster/core/preset.py` holds the finalized **Yeaster Momentum** config: detectors
`[rel_strength, breakout, extended_runner, vol_surge, scanner_spot]`, all 8 grade
dims, bold LLM lead, exit **8% stop / 40% TP / ATR-3× volatility-scaled trailing**
(`trailing_mode:"atr"`, `atr_k:3.0`; a fixed `trailing_pct` is the fallback when a
coin has too little history for ATR), guard slippage 100 bps. The funded reserve is
**USDT** (`DEFAULT_RESERVE`). The exit bracket was re-tuned on a 135-token real-OHLC
backtest (`yeaster/backtest/`, `scripts/backtest.py`); change only with fresh validation.

## The universe

`yeaster/core/whitelist.json` = the official **148‑token** competition whitelist
(the hard tradeable bound). `core/universe.py` derives the momentum set (minus
stables/gold/refs) and the firewall allowlist.

## Backends

- **cmc**: `mock` (keyless), `rest` (Pro API), `mcp` (Data MCP) — `auto` picks by key.
- **twak**: `mock`, `paper` (virtual wallet), `cli` (real wallet) — `auto` honors the gate.
