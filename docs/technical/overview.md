# Yeaster — Overview

Yeaster is an **autonomous BNB Smart Chain momentum trading agent**. It watches the
market, reasons in distinct internal passes, sizes and places its own trades behind
a non‑bypassable safety firewall, and records every decision in a tamper‑evident
proof ledger — funds held self‑custodially in a single wallet.

This folder is the canonical technical documentation. It describes the **system as
it is today**. When docs and code disagree, the **code wins**.

## Where to start

| You are a… | Read, in order |
|---|---|
| Judge / PM / new reader | `overview.md` (this file) |
| Engineer | `overview.md` → `architecture.md` → `configuration.md` → `operations.md` |
| Operator | `operations.md` + `configuration.md` |

## Design philosophy

- **One agent, orchestrated stages.** A single mind reasons in sequential passes
  (`screen → grade → vet → commit`) — not a roster of agents.
- **Policy proposes, rails dispose.** The LLM‑backed passes only *select within a
  safe shortlist*; deterministic rails own sizing, safety, and kill‑switches. An
  experimental or AI decision‑maker can never place an unsafe trade or spend real funds.
- **Evidence honesty.** Scores carry *coverage* (how much real data backed them), and
  **safety is a separate, never‑subtracted axis** — an unverifiable token is not
  wrongly treated as unsafe (the "SIREN" lesson).
- **Capital preservation first.** Wide‑but‑real stops, drawdown brakes, "do nothing"
  as a valid outcome.
- **Self‑custody.** Execution rides Trust Wallet; the agent holds its own keys.

## What it can do today

- Run autonomously on a cadence (with auto‑resume) and as **committed timed runs**
  that lock the chat and can be halted only with a **password kill switch**.
- Grade tokens across 8 CMC‑sourced dimensions + a separate safety axis.
- Enforce a 148‑token whitelist, size/slippage/drawdown caps, and token‑safety.
- Place real swaps + native stop/TP/trailing brackets via Trust Wallet.
- Be **PnL‑aware** — realized/unrealized PnL, win‑rate, recent exits feed the decision.
- Expose its stages as **5 reusable Track‑2 skills** (`/api/skills`).
- Drive a Liquid‑Flow control room (terminal + chat + dashboards + market intelligence).

## What it does NOT do (today)

- Trade off‑whitelist tokens (hard‑bounded to the 148).
- Touch mainnet until the operator opens the double‑gate (`YST_MAINNET` + confirm phrase).
- Margin/leverage/derivatives — spot only.
- Guarantee profit — it manages risk, it does not predict.

## Technology at a glance

Python 3.10+ · FastAPI (router‑structured) · pydantic v2 · Next.js 14 + Tailwind v4
(Liquid Flow UI) · CoinMarketCap Agent Hub (data + skills) · Trust Wallet AgentKit
(execution) · BNB Smart Chain · OpenAI **or** Anthropic (swappable, optional).

## Glossary

- **tick** — one cycle of observe → reason → (maybe) act → record.
- **composite** — the coverage‑weighted multi‑dimensional grade in `[-1, 1]`.
- **coverage** — fraction of dimensions that returned real data.
- **safety axis** — token scam/quality read; surfaced, never subtracts from the composite.
- **committed run** — a timed autonomous run with the chat locked + password kill switch.
- **proof block** — one sha256‑chained record of a decision + guard log + outcome.
