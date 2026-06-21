# Yeaster — Technical Documentation

This is the engineering reference for **Yeaster**, the self-custodial BNB Smart
Chain momentum agent. It documents the system **as it actually runs today** — if a
doc and the code ever disagree, trust the code.

## Read in this order

1. **[`overview.md`](./overview.md)** — what Yeaster is, the principles it's built on,
   what it can and can't do. Start here whether you're a judge, a PM, or an engineer.
2. **[`architecture.md`](./architecture.md)** — the `screen → grade → vet → commit`
   brain, the firewall, execution, the proof ledger, the runtime daemon, the API,
   the skills, and the web control room.
3. **[`configuration.md`](./configuration.md)** — the `YST_` knobs, third-party
   credentials, the mainnet double-gate, the Momentum preset, the 148-token universe,
   and the backend matrix.
4. **[`operations.md`](./operations.md)** — install, run, drive it, test it, and take
   it live safely; observability.
5. **[`x402.md`](./x402.md)** — how the agent **sells its daily alpha** for an
   on-chain-verified USDT micropayment (the x402 paywall).

Also worth a look: **[`../../skills/`](../../skills/)** for the Track-2 strategy
skills, and `../AGENTS.md` for the build ledger.

## Naming & provenance

Everything is branded **Yeaster**, top to bottom. Internal identifiers, package
modules, and environment variables carry a `yeaster*` / `YST_*` prefix —
`YeasterGuard`, `YST_MAINNET`, the proof record key `commit_record`. The codebase
shares **no identifiers with any predecessor**: it is audit-clean by design.
Third-party prefixes (`CMC_`, `TWAK_`, `OPENAI_`, `BSC_`, …) are kept deliberately —
those authenticate to the services they name.
