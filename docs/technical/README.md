# Yeaster — Technical Documentation

The canonical, product‑facing documentation for **Yeaster**, an autonomous BNB
Smart Chain momentum trading agent. It describes the system **as it is today**.

## Document map

| Document | Audience | Contents |
|---|---|---|
| [`overview.md`](./overview.md) | Judges / PM / everyone | Purpose, design philosophy, capabilities, what it does *not* do, glossary |
| [`architecture.md`](./architecture.md) | Engineers | screen→grade→vet→commit brain, firewall, execution, proof chain, runtime, API, skills, web |
| [`configuration.md`](./configuration.md) | Engineers / operators | `YST_` knobs, credentials, the mainnet gate, the preset, the universe, backends |
| [`operations.md`](./operations.md) | Operators | install, run, drive, test, go live safely, observability |

Also: **[`../../skills/`](../../skills/)** (Track‑2 strategy skills) and
`../AGENTS.md` (build ledger).

## A note on naming

The brand is **Yeaster**; the codebase matches it — internal identifiers, package
modules, and env vars use a `yeaster*` / `YST_*` prefix (e.g. `YeasterGuard`,
`YST_MAINNET`, the proof key `commit_record`). It shares **no** identifiers with
any predecessor. Third‑party prefixes (`CMC_`, `TWAK_`, `OPENAI_`, `BSC_`, …) are
intentionally kept — they authenticate to those services.

## Source‑of‑truth hierarchy

When these docs and the code disagree, the **code wins**.
