# Yeaster — Overview

Yeaster is a **self-custodial BNB Smart Chain momentum agent**. It hunts the tape,
reasons through ordered internal passes, sizes and fires its own trades behind a
non-bypassable firewall, and seals every decision into a tamper-evident proof
ledger — keys and funds held in a single wallet it controls.

This folder is the engineering reference. It documents the **system as it runs
today**; where these pages and the code ever diverge, the code is authoritative.

## Where to start

| You are a… | Read, in order |
|---|---|
| Judge / PM / new reader | `overview.md` (this file) |
| Engineer | `overview.md` → `architecture.md` → `configuration.md` → `operations.md` |
| Operator | `operations.md` + `configuration.md` |

## Design philosophy

- **One mind, fixed stages.** A single reasoning process advances through ordered
  passes (`screen → grade → vet → commit`) — never a committee of agents trading
  messages. Auditable in order, impossible to deadlock.
- **Smarts on top, hard rails underneath.** The LLM‑backed passes only *choose from a
  pre‑vetted shortlist*. Sizing, safety, and the kill‑switches live in deterministic
  code the model cannot reach or override — so even an experimental decision‑maker
  cannot place an unsafe trade or move real funds.
- **Honest about danger.** Every score carries its *coverage* (how much real data
  backed it), and scam/honeypot risk rides a **separate axis with zero weight in the
  grade** — it can veto a trade, but it can never quietly poison a good token we
  simply couldn't verify (the "SIREN" lesson, hunted and killed).
- **It would rather hold cash than a bad bet.** Wide‑but‑real stops, drawdown brakes
  that shrink the agent as it loses, and sitting flat as a first‑class outcome — a
  zero‑trade day is a win, not a miss.
- **It holds its own keys.** Execution rides Trust Wallet; custody never leaves the
  agent's wallet.

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
