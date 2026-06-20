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
