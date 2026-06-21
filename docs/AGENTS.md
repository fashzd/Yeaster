# Yeaster — Build Ledger

Yeaster is an autonomous BNB momentum trading agent — **one mind, orchestrated
stages**. It is a ground-up reimplementation that embeds a proven momentum edge
inside a new architecture, with a "Liquid Flow" terminal + dashboard. It shares
**no internal identifiers** with its predecessor.

---

[Claude Code] — 2026-06-20 — Phases 1–7 (initial build)

**Phase 1 — Scaffold.** Installable `yeaster/` package (`pip install -e .`),
typed `YST_` settings, `.env.example`, Next.js 14 + Tailwind v4 web shell with
the Liquid Flow design system (glass blobs + SVG goo filter). `/api/health` up.

**Phase 2 — Core / market / execution / proof.** Contracts (`core/models.py`);
CMC data client (mock/REST/MCP) + Skill-Hub client + indicators; TWAK two-step
broker (mock/paper/cli) with HMAC approval permits + native brackets; sha256
proof ledger (`commit_record` key). Live wallet read confirmed against the real
on-chain wallet `0xA498…171C`. `/api/wallet`, `/api/market/overview`,
`/api/readiness` live.

**Phase 3 — Guard.** `YeasterGuard` — 7 deterministic checks (allowlist, trade
cap, position cap, slippage, epoch, hard-drawdown, Safe-Mode) with the de-risk
carve-out and Safe-Mode latch; token-safety (whale concentration + liquidity
floor).

**Phase 4 — Brain.** One agent reasoning in stages — `screen → grade → vet →
commit` — driven by the deterministic `cycle` runner. Ported the proven detector
conditions, the 9-dimension coverage-weighted composite with the zero-weight
safety axis (SIREN fix), the LLM critic (vet) and god-trader lead (commit), and
the R-based sizing rails (0.7%R, DD brakes, caps). `/api/agent/tick` + SSE
`/api/agent/tick/stream` stream the reasoning live.

**Phase 5 — Runtime.** Exit reconciliation (stop/TP + trailing), persisted state
(peak equity, drawdown, position book, Safe-Mode latch), and the autonomous
`daemon` loop with auto-resume. Verified: the daemon ran on a cadence and sealed
a chained, verifiable proof of every decision.

**Phase 6 — Liquid Flow UI.** Single fused page: the Agent Terminal (live SSE
reasoning stream + run-tick + autonomous toggle) and dashboard blobs — TWAK
portfolio/PnL, native brackets, CMC regime + movers, the proof chain, and agent
state. Biomorphic glass panels over tinted acrylic.

**Phase 7 — Harden + verify.** 29 pytest green. Identifier audit clean (no
`ryo`/`sentinel`/`aegis` anywhere). Readiness 6/7 live (CMC data + skills + LLM +
persistence + TWAK CLI; bnb_onchain gated by design). `auto` backend respects the
mainnet gate: **paper everywhere until the owner opens the gate** — the agent
never touches the chain while gated. `scripts/testnet_rehearsal.py` is the
owner-runnable live testnet swap harness.

**Verification State:** Full paper cycle end-to-end → proof verified. Autonomous
loop verified. Live CMC data, live Skill-Hub LLM critic, and live wallet read all
exercised. Real mainnet execution remains behind `YST_MAINNET=1` +
`YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS` for the owner to open.

**Run:** `uvicorn yeaster.api.app:app --port 8000` · `cd web && npm run dev`
(http://localhost:3000) · `python scripts/paper_cycle.py`.

---

[Claude Code] — 2026-06-20 — Phase 8 (whitelist + preset + chat + CMC dashboards)

**148-token whitelist.** `core/whitelist.json` is the hard tradeable universe
(loaded by `core/universe.py` → 147 unique allowlist, 135 momentum after removing
stables/gold/refs). The firewall allowlist is the full whitelist; the screen
scouts only the momentum set. The agent can never target an off-list token.

**Finalized momentum preset.** `core/preset.py` — the exact backtested config:
detectors `[rel_strength, breakout, extended_runner, vol_surge, scanner_spot]`,
all 8 grade dims, bold lead (aggressive), **exit 8% stop / 16% TP / 3% trail**,
slippage 100 bps. Fixed a real bug: bracket stops were 3.5%/12% (I had conflated
the sizing risk-divisor with the bracket stop) — now correctly 8%/16%.

**Agent chat (ported all capabilities).** `brain/chat.py` + `/api/chat`:
conversational Q&A (LLM persona + live market context), `$SYM` token deep-dive
cards, `buy N% SYM` / `sell SYM` manual swaps, guard on/off, live/paper, run a
cycle, market overview. Manual swaps go through `runtime.run_manual` (quote →
firewall → execute → proof) via `/api/agent/manual`. Token charts from
`/api/market/series` (price path + 8%/16% bracket markers) and
`/api/market/token/{sym}`.

**UI upgrade.** Header now has live/paper + guard on/off + autonomous toggles.
Workspace tabs: **Terminal** (SSE reasoning) | **Chat** (talk + trade). Dashboard
blobs: TWAK wallet/PnL, native brackets, CMC market movers, **Fear & Greed gauge**,
regime/agent state, proof chain. Chat "run a cycle" drives the terminal; charts
render inline on `$SYM`.

**Verification State:** 29 pytest green; identifier audit clean; chat/manual/
series/token endpoints exercised live (e.g. `$ETH` card, `buy 5% CAKE` →
EXECUTED + proof, series markers confirm 8%/16% brackets). Web build green.

---

[Claude Code] — 2026-06-20 — Phase 9 (polish, settings/kill-switch, intelligence page, live mainnet test)

**UI polish.** Terminal + Chat now side-by-side (both visible, fixed 540px,
internal scroll). Uniform stat strip + fixed-height dashboard panels (no more
unbounded growth). Glass-themed scrollbars. Copy-to-clipboard wallet address.
**Agent Wallet · self-custody** panel shows the REAL on-chain wallet (cli) +
balance; clicking **live** shows the live balance as the book.

**Settings + committed runs.** Settings modal: commit live trading, set a
**timed autonomous run** (run N hours — the chat LOCKS for the window, agent
trades unattended, loop auto-stops on expiry), and a **password-protected kill
switch** to halt early. Daemon gained run_until / locked / kill_hash; operator
actions (manual/tick) are rejected (423) while locked; stop requires the password.

**PnL feedback loop.** State tracks wins/losses/recent exits + realized &
unrealized PnL; `book_for_llm` feeds win-rate + recent outcomes to the commit
lead so the agent is PnL-aware. Surfaced in agent status + stat strip.

**Market Intelligence page (/intelligence).** CMC regime + Fear&Greed gauge +
readiness screener (click a row to chart it), TWAK **top trending tokens**
(`/api/market/trending`), breakout scanner chips, and a **TradingView** advanced
chart. New endpoints: `/api/market/intelligence`, `/api/market/trending`.

**Chat strengthened.** Now LLM-driven with live context (real wallet, posture,
positions) returning {reply, pack, action} — desk-analyst cards (e.g. ETH →
6-row technical/derivatives/whale/sector/unlock/safety card). Fast deterministic
paths for explicit commands; toggles flip the header.

**LIVE MAINNET TEST (honest result).** Gate opens correctly (chains 97+56);
**real mainnet quotes succeed** (0.5 USDT → 0.00084653 BNB via TWAK cli) — the
live path reaches the chain. Fixed the quote parser to TWAK's real JSON
(`output`/`minReceived`/`priceImpact`). **An actual fill is blocked by TWO items,
both owner-actionable:** (1) the wallet holds $1.91 USDT and **0 BNB** — BSC
swaps need BNB for gas; (2) TWAK resolves majors by symbol but **alt tokens like
CAKE need a contract address** (`--decimals`/address) — Yeaster needs a
whitelist→BSC-address map for live alt swaps. No real trade was executed.

**Verification State:** 29 pytest green; identifier audit clean; web build green
(/ + /intelligence). Next: fund ~$2 BNB for gas + add the symbol→address map to
enable a real live fill.

---

## 2026-06-21 — Exit re-tune, native backtester, first live fill, operator controls

**Backtester (new, native):** `yeaster/backtest/` + `scripts/backtest.py` — real CMC daily OHLC
(`/v2/ohlcv/historical`), point-in-time walk-forward, true-OHLC exit sim, `--run` / `--sweep-trailing`
/ `--sweep-brackets`. Honest by construction (OHLCV-only; the live GRADE composite is out of scope).

**Exit bracket re-tuned (real-OHLC, 135 tokens):** fixed-3% trail → **ATR-3× volatility-scaled**;
16% TP → **40% wide backstop** (a tight TP strangled the runners; a no-TP variant only "won" by breaching
the 30% DQ via 5× concentration, so rejected). Stop 8%, sizing, drawdown governor unchanged. Reserve
**USDC → USDT** (matches the funded wallet).

**FIRST REAL FILL:** `0.5 USDT → 0.3627 CAKE` (tx `0xa3cba2…6618`), native ATR stop armed on-chain.
Live test caught + fixed a bracket-chain bug (`build_bracket_specs` defaulted to testnet).

**Operator controls (UI-driven):** lock button doubles as a password **unlock** (`/api/daemon/stop` →
cleans orphaned automations, keeps protective brackets); separate **kill switch** (`/api/daemon/kill` →
`flatten.py` sells all to USDT + `cancel_all`). **≥1 trade/day** compliance fallback (det_safety, min size,
after `YST_DAILY_CUTOFF_HOUR`). **LLM is the decisive factor** — stands down (no silent deterministic
substitute) when unavailable. **PnL teeth** — consecutive-loss streak + daily realized PnL fed to the LLM
(prompt instructed to act) + a deterministic size haircut after 3 losses. Guard re-confirmed relevant.

**Verification:** 56 pytest green; web typechecks; `/api/daemon/{kill,stop,start}` registered; identifier
audit clean. Docs (README, technical/*, bracket skill, .env.example) updated + a server deploy guide added.

---

## 2026-06-21b — Hackathon hardening: kill password, BNB manual, x402 alpha, lock UI, Learn page

- **Kill switch always authenticated:** `YST_OPERATOR_PASSWORD` gates unlock + kill (`daemon._check_password`
  accepts the run kill-hash OR the operator password). Kill flattens + sweeps orphans on paper AND live.
- **BNB manual swaps + approval:** chat returns `manual_trade_pending` → UI Approve/Cancel card → `/api/agent/manual`.
  Manual mandate allows BNB (native); autonomous can't (BNB not in UNIVERSE). All manual swaps need approval.
- **x402 alpha sales (real on-chain):** `POST /api/x402/alpha` → 402 + USDT price/pay-to until a verified, unredeemed
  on-chain USDT payment (BSC RPC receipt decode, anti-replay) unlocks the daily alpha (`brain/alpha.py` from the
  proof chain). `GET /api/x402/alpha/teaser`; `scripts/buy_alpha.py` demo. Off by default (`YST_X402=0`).
- **UI:** big live-ticking `HH:MM:SS` lock countdown + AGENT LOCKED banner; chat locked when committed; new judge-
  facing **/learn** page (brain, guardrails+why, exits, controls, sponsors, x402, proof). Next build green.
- **Docs:** README "Guardrails — and why" (12 points) + x402 row; technical config/operations + `.env.example`.
- **Verification:** 72 pytest green; web tsc + `next build` clean.

---

## 2026-06-21c — Paper/live isolation, gate open, live wallet truth, dust + reserve fixes

- **Paper/live state isolated:** per-mode files `data/state/agent_state_{paper,live}.json` via
  `state.state_mode(twak_backend)`; read endpoints (`/agent`, `/positions`, `/activity`, `market/series`)
  and the frontend take an explicit `mode`/`backend` (no more `auto`, which now always = live with the gate
  open). Verified zero bleed-through across book/positions/brackets/activity.
- **Mainnet gate kept open** in `.env` (`YST_MAINNET=1`); live = the control-room toggle + operator password.
  Safety rests on explicit backend resolution (paper sends `twak_backend:"paper"`), not the gate.
- **Live wallet shows ALL holdings:** `twak._merge_onchain_holdings` merges an on-chain **Multicall3
  `balanceOf` sweep** over the 142 resolved contracts (TWAK CLI only reports its tracked set, hiding
  swapped-in tokens like the first-fill CAKE). Priced from **CMC only** (never the mock oracle — that gave a
  FLOKI dust bag a ~$50k pseudo-value); un-priceable tokens shown unvalued. Cached 45s; `YST_WALLET_SWEEP`.
- **Bug fixes from the readiness audit:** (1) `build_bracket_specs` reserve default `USDC → USDT` so on-chain
  stop/TP legs sell into the funded reserve; (2) new `YST_MIN_NOTIONAL_USD` (**$1.20 contest minimum**) — a hard
  guard on the actual USDT spent blocks any sub-minimum trade; the mandatory ≥1/day compliance trade **sizes up**
  to clear it (~$1.56) regardless of wallet size, instead of the old tiny conviction-floor size.
- **Live cadence** 2h (7200s) after an immediate first tick; paper 120s. Chat persists across refresh
  (localStorage, memory-aware) + clear button; trade cards across autonomous/tick/manual; blinking online dot.
- **Docs:** new `docs/technical/x402.md` (full alpha-sale payment spec); configuration.md (min-notional,
  wallet sweep, paper/live state, cadence, gate posture); architecture.md (wallet truth, isolation, x402 link).
- **Verification:** 78 pytest green; live E2E green (gate, isolation, x402 402-gate, kill-switch password 403).
