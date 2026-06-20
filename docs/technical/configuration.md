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
| `YST_WIDE_SNAPSHOT` | `1` | snapshot the full universe |
| `YST_WHALE_CONCENTRATION_LIMIT_PCT` | `30.0` | token‑safety whale cap |
| `YST_TRADE_CHAIN_ID` | `56` | target chain (97 testnet / 56 mainnet) |
| `YST_PORTFOLIO_CHAIN` | `bsc` | chain the live wallet is read from |
| `YST_APPROVAL_SECRET` | dev default | HMAC permit key — **set in prod** |
| `YST_X402` / `YST_X402_SECRET` | `0` / dev | x402 micropayments (off by default) |

## The real‑funds gate (mainnet)

Real mainnet execution requires **both**:

```bash
YST_MAINNET=1
YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS
```

With the gate closed, `auto` backends resolve to **paper** everywhere and the agent
never touches the chain. With it open, `auto` → live CLI and chain 56 is permitted.

## The strategy preset

`yeaster/core/preset.py` holds the finalized **Yeaster Momentum** config (the one
backtested edge): detectors `[rel_strength, breakout, extended_runner, vol_surge,
scanner_spot]`, all 8 grade dims, bold lead, exit **8% stop / 16% TP / 3% trail**,
guard slippage 100 bps. Change only with fresh validation.

## The universe

`yeaster/core/whitelist.json` = the official **148‑token** competition whitelist
(the hard tradeable bound). `core/universe.py` derives the momentum set (minus
stables/gold/refs) and the firewall allowlist.

## Backends

- **cmc**: `mock` (keyless), `rest` (Pro API), `mcp` (Data MCP) — `auto` picks by key.
- **twak**: `mock`, `paper` (virtual wallet), `cli` (real wallet) — `auto` honors the gate.
