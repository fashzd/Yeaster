"""Trust Wallet AgentKit execution client + the two-step broker.

Backends:
  * ``mock``  — deterministic in-process AMM + virtual wallet, zero keys (tests).
  * ``paper`` — virtual wallet valued at live prices via an injected price oracle.
  * ``cli``   — shells the real ``twak`` binary (same wallet, same keychain).

The broker enforces the two-step guard: always quote first; execute only after a
verified, quote-bound :class:`ApprovalToken`. Mainnet is gated at execution time.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from yeaster.core.settings import get_settings
from yeaster.execution.approval import ApprovalError, verify_approval_token
from yeaster.execution.models import (
    BSC_TESTNET_CHAIN_ID,
    ApprovalToken,
    PortfolioState,
    SwapQuote,
    SwapReceipt,
    SwapRequest,
    SwapStatus,
    TokenBalance,
    explorer_for_chain,
    permitted_chain_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_WALLET_PATH = REPO_ROOT / "data" / "wallet" / "paper_wallet.json"

STABLES = {"USDC", "USDT", "DAI", "FDUSD", "TUSD", "USD1", "USDD", "BUSD"}

# Deterministic mock prices (USD) for keyless runs/tests. Any unknown symbol gets
# a stable pseudo-price derived from its name, so the mock is fully reproducible.
_MOCK_PRICES = {
    "BNB": 615.0, "ETH": 3050.0, "BTC": 64000.0, "CAKE": 2.4, "LINK": 14.5,
    "UNI": 7.8, "AAVE": 95.0, "DOGE": 0.12, "ADA": 0.39, "XRP": 0.52,
    "USDC": 1.0, "USDT": 1.0, "DAI": 1.0, "FDUSD": 1.0, "TUSD": 1.0,
}

# A runtime-injected price oracle (the daemon sets this from the live CMC snapshot).
_PRICE_ORACLE: Optional[Callable[[str], Optional[float]]] = None


def set_price_oracle(fn: Optional[Callable[[str], Optional[float]]]) -> None:
    """Install a live price source used by the paper backend (None => mock prices)."""
    global _PRICE_ORACLE
    _PRICE_ORACLE = fn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def mock_price(symbol: str) -> float:
    sym = symbol.upper()
    if sym in _MOCK_PRICES:
        return _MOCK_PRICES[sym]
    if sym in STABLES:
        return 1.0
    # Stable pseudo-price in [0.05, 50) from a hash of the symbol.
    h = int(hashlib.sha256(sym.encode()).hexdigest()[:8], 16)
    return round(0.05 + (h % 5000) / 100.0, 6)


def price(symbol: str, backend: str = "auto") -> float:
    """Best price for ``symbol``: injected oracle first, then mock."""
    if backend != "mock" and _PRICE_ORACLE is not None:
        try:
            p = _PRICE_ORACLE(symbol)
            if p and p > 0:
                return float(p)
        except Exception:
            pass
    return mock_price(symbol)


def resolve_backend(requested: str = "auto") -> str:
    requested = (requested or "auto").lower()
    if requested in ("mock", "paper", "cli"):
        return requested
    # auto: the agent only touches the chain when the owner has OPENED the mainnet
    # gate. Until then it trades on paper everywhere — the safe default.
    s = get_settings()
    if s.mainnet_unlocked and shutil.which(s.twak_cli_bin):
        return "cli"
    return "paper"


# ── Quote hashing ────────────────────────────────────────────────────────────


def _quote_hash(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "quote_hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "0x" + hashlib.sha256(canonical.encode()).hexdigest()


def _build_quote(request: SwapRequest, backend: str, expected_out: float, impact_bps: int,
                 min_out: Optional[float] = None) -> SwapQuote:
    now = _now()
    tol = request.slippage_tolerance_bps
    if min_out is None:
        min_out = expected_out * (1.0 - tol / 10_000.0)
    payload = {
        "quote_id": hashlib.sha256(f"{request.from_asset}{request.to_asset}{request.amount_in}{_iso(now)}".encode()).hexdigest()[:16],
        "backend": backend,
        "chain_id": request.chain_id,
        "from_asset": request.from_asset,
        "to_asset": request.to_asset,
        "amount_in": request.amount_in,
        "expected_amount_out": round(expected_out, 10),
        "min_amount_out": round(min_out, 10),
        "price_impact_bps": impact_bps,
        "expected_slippage_bps": impact_bps,
        "slippage_tolerance_bps": tol,
        "route": [request.from_asset, request.to_asset],
        "quoted_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=60)),
    }
    payload["quote_hash"] = _quote_hash(payload)
    return SwapQuote(**payload)


# ── Mock / paper AMM ─────────────────────────────────────────────────────────


def _amm_quote(request: SwapRequest, backend: str) -> SwapQuote:
    """Constant-ish AMM with size-scaled price impact (deterministic)."""
    p_from = price(request.from_asset, backend)
    p_to = price(request.to_asset, backend)
    usd_in = request.amount_in * p_from
    # Price impact grows ~linearly with trade size; small for our notionals.
    impact_bps = int(min(300, max(5, usd_in / 50.0)))
    gross_out = usd_in / p_to if p_to > 0 else 0.0
    expected_out = gross_out * (1.0 - impact_bps / 10_000.0)
    return _build_quote(request, backend, expected_out, impact_bps)


# ── Paper wallet ─────────────────────────────────────────────────────────────


def _load_paper() -> dict:
    if PAPER_WALLET_PATH.exists():
        return json.loads(PAPER_WALLET_PATH.read_text())
    return {"address": "0xPAPER000000000000000000000000000000PAPER", "balances": {"USDC": 500.0, "USDT": 500.0}}


def _save_paper(state: dict) -> None:
    PAPER_WALLET_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_WALLET_PATH.write_text(json.dumps(state, indent=2))


def seed_paper(usd: float = 1000.0, stable: Optional[str] = None) -> dict:
    if stable:
        balances = {stable.upper(): float(usd)}
    else:
        balances = {"USDC": usd / 2.0, "USDT": usd / 2.0}
    state = {"address": "0xPAPER000000000000000000000000000000PAPER", "balances": balances}
    _save_paper(state)
    return state


def _portfolio_from_balances(address: str, balances: dict[str, float], backend: str, chain_id: int) -> PortfolioState:
    rows: list[TokenBalance] = []
    total = 0.0
    native = 0.0
    for sym, amt in balances.items():
        amt = float(amt)
        val = amt * price(sym, backend)
        total += val
        rows.append(TokenBalance(symbol=sym, balance=amt, value_usd=round(val, 4)))
        if sym in ("BNB", "TBNB"):
            native = amt
    positions = {r.symbol: round((r.value_usd or 0.0) / total, 6) for r in rows if total > 0}
    return PortfolioState(
        address=address, chain_id=chain_id, native_balance=native, balances=rows,
        total_value_usd=round(total, 4), positions_pct=positions, captured_at=_iso(_now()),
    )


# ── Live CLI backend ─────────────────────────────────────────────────────────


# twak CLI v0.19.x chain keys (NOT numeric ids).
_CHAIN_KEYS = {56: "bsc", 97: "smartchain-testnet"}


def _chain_key(chain_id: int) -> str:
    return _CHAIN_KEYS.get(int(chain_id), "bsc")


def _portfolio_chain_key() -> str:
    """The chain the live wallet is read from — the agent's real funds are on mainnet."""
    import os

    return os.getenv("YST_PORTFOLIO_CHAIN", "bsc")


def _run_cli(args: list[str]) -> dict:
    bin_ = get_settings().twak_cli_bin
    proc = subprocess.run([bin_, *args], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"twak {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    out = proc.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


def _amt(s) -> float:
    """Parse a twak amount string like '0.000846 BNB' (or a number) to a float."""
    try:
        return float(str(s).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def _tok(symbol: str, chain_id: int) -> str:
    """Resolve a token to the arg twak wants: contract address on mainnet, else symbol."""
    if chain_id == 56:
        from yeaster.core.addresses import token_arg
        return token_arg(symbol)
    return symbol


def _cli_quote(request: SwapRequest) -> SwapQuote:
    raw = _run_cli([
        "swap", str(request.amount_in), _tok(request.from_asset, request.chain_id),
        _tok(request.to_asset, request.chain_id),
        "--chain", _chain_key(request.chain_id),
        "--slippage", str(request.slippage_tolerance_bps / 100.0),
        "--quote-only", "--json",
    ])
    # twak quote JSON: {input, output:"<n> SYM", minReceived:"<n> SYM", provider, priceImpact:"<pct>"}
    expected_out = _amt(raw.get("output") or raw.get("amount_out") or raw.get("expected_amount_out"))
    min_out = _amt(raw.get("minReceived")) or None
    impact_bps = int(round(float(raw.get("priceImpact") or raw.get("price_impact_pct") or 0) * 100))
    return _build_quote(request, "cli", expected_out, impact_bps, min_out=min_out)


def _cli_execute(quote: SwapQuote) -> SwapReceipt:
    # The wallet password is read by twak from TWAK_WALLET_PASSWORD / keychain —
    # never passed on the command line (it would leak into process args).
    args = [
        "swap", str(quote.amount_in), _tok(quote.from_asset, quote.chain_id),
        _tok(quote.to_asset, quote.chain_id),
        "--chain", _chain_key(quote.chain_id),
        "--slippage", str(quote.slippage_tolerance_bps / 100.0), "--json",
    ]
    raw = _run_cli(args)
    tx = raw.get("txHash") or raw.get("transactionHash") or raw.get("tx_hash") or raw.get("hash") or raw.get("tx")
    amount_out = _amt(raw.get("output")) or float(raw.get("amount_out") or quote.expected_amount_out)
    return SwapReceipt(
        status=SwapStatus.EXECUTED if tx else SwapStatus.FAILED,
        backend="cli", chain_id=quote.chain_id, tx_hash=tx,
        from_asset=quote.from_asset, to_asset=quote.to_asset,
        amount_in=quote.amount_in, amount_out=amount_out,
        effective_slippage_bps=quote.expected_slippage_bps, quote_hash=quote.quote_hash,
        explorer_url=(explorer_for_chain(quote.chain_id) + tx) if tx else None,
        executed_at=_iso(_now()), error=None if tx else "no tx_hash returned",
    )


def _wallet_address(chain_id: int) -> str:
    try:
        raw = _run_cli(["wallet", "balance", "--chain", _chain_key(chain_id), "--json"])
        return str(raw.get("address") or "")
    except Exception:
        return ""


def ensure_sell_approval(symbol: str, chain_id: int) -> dict:
    """Approve the swap router to spend ``symbol`` so later SELLS — stop-loss,
    take-profit, the ATR trail, manual exits, and the kill-switch flatten — don't
    revert. A freshly-bought token has no allowance; without this the FIRST sell
    (an automation firing, or a flatten) reverts. Idempotent: no-op if already
    approved, and a no-op off live mainnet."""
    s = get_settings()
    spender = s.swap_spender
    if chain_id != 56 or not spender:
        return {"ok": False, "skipped": True}
    if resolve_backend("auto") != "cli":
        return {"ok": False, "skipped": True}
    token = _tok(symbol, chain_id)
    key = _chain_key(chain_id)
    try:
        owner = _wallet_address(chain_id)
        if owner:
            raw = _run_cli(["erc20", "allowance", "--token", token, "--owner", owner,
                            "--spender", spender, "--chain", key, "--json"])
            if str(raw.get("allowance", "0")) not in ("0", ""):
                return {"ok": True, "already_approved": True}
        _run_cli(["erc20", "approve", "--token", token, "--spender", spender,
                  "--amount", "unlimited", "--confirm-unlimited", "--chain", key, "--json"])
        return {"ok": True, "approved": True}
    except Exception as exc:  # noqa: BLE001 — never block a trade on the approval call
        return {"ok": False, "error": str(exc)}


def trending(limit: int = 12) -> list[dict]:
    """TWAK top trending tokens (best-effort; empty list if the CLI lacks the command)."""
    if not shutil.which(get_settings().twak_cli_bin):
        return []
    try:
        raw = _run_cli(["trending", "--json"])
    except Exception:
        return []
    rows = raw if isinstance(raw, list) else (raw.get("trending") or raw.get("tokens") or raw.get("data") or [])
    out = []
    for r in rows[:limit]:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or r.get("ticker") or r.get("asset") or "").upper()
        if sym:
            out.append({"symbol": sym, "name": r.get("name"), "rank": r.get("rank"),
                        "category": r.get("category"), "change_24h": r.get("price_change_24h") or r.get("change")})
    return out


# ── On-chain holdings sweep (fills the TWAK CLI's blind spot) ─────────────────
# `twak wallet balance`/`portfolio` only report TWAK's *tracked* token set — an
# ERC-20 the agent swapped into (or received) but that TWAK doesn't track stays
# invisible, under-reporting the live book. The chain is the source of truth: one
# Multicall3 `balanceOf` sweep over the resolved tradeable universe surfaces every
# held token. Best-effort and cached so frequent wallet polls don't hammer RPC.

_MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"   # canonical, same address every chain
_SWEEP_TTL_SECONDS = 45.0
_sweep_cache: dict[str, tuple[float, dict]] = {}   # address -> (ts, {sym: (human_balance, value_usd|None)})
_decimals_cache: dict[str, int] = {}


def _universe_contracts() -> dict[str, str]:
    """Resolved symbol→BSC-contract map of the tradeable universe (CMC-sourced, disk-cached)."""
    from yeaster.core.addresses import _CACHE_PATH
    try:
        cache = json.loads(_CACHE_PATH.read_text())
    except Exception:
        return {}
    return {k.upper(): v for k, v in cache.items() if isinstance(v, str) and v.startswith("0x")}


def _word(x: int) -> str:
    return f"{x:064x}"


def _multicall3_balanceof(address: str, contracts: list[str]) -> dict[str, int]:
    """One eth_call to Multicall3.aggregate3, returning raw balanceOf(address) per
    contract as {contract_lower: int}. Returns {} on any RPC/decoding failure."""
    from yeaster.execution.x402 import _bsc_rpc
    owner = address.lower().replace("0x", "").rjust(64, "0")
    inner_padded = ("70a08231" + owner).ljust(128, "0")   # balanceOf(address): 36 bytes → padded to 64
    n = len(contracts)
    tuple_size = 32 * 3 + 32 + 64                          # head(3 words) + bytes-len + bytes-data(36→64)
    head = _word(0x20) + _word(n) + "".join(_word(n * 32 + i * tuple_size) for i in range(n))
    body = "".join(
        c.lower().replace("0x", "").rjust(64, "0")        # target
        + _word(1)                                        # allowFailure = true
        + _word(0x60)                                     # offset to callData within tuple
        + _word(36)                                       # callData length
        + inner_padded
        for c in contracts
    )
    res = _bsc_rpc("eth_call", [{"to": _MULTICALL3, "data": "0x82ad56cb" + head + body}, "latest"])
    if not res or res == "0x":
        return {}
    try:
        h = res[2:]
        arr = (int(h[0:64], 16) // 32) * 64               # hex pos of the Result[] length word
        cnt = int(h[arr:arr + 64], 16)
        offs = arr + 64                                   # start of the per-element offset words
        out: dict[str, int] = {}
        for i in range(cnt):
            tup = offs + int(h[offs + i * 64: offs + (i + 1) * 64], 16) * 2
            success = int(h[tup:tup + 64], 16)
            bpos = tup + int(h[tup + 64:tup + 128], 16) * 2
            blen = int(h[bpos:bpos + 64], 16)
            data = h[bpos + 64: bpos + 64 + blen * 2]
            out[contracts[i].lower()] = int(data, 16) if (success and data) else 0
        return out
    except (ValueError, IndexError):
        return {}


def _erc20_decimals(contract: str) -> int:
    if contract.lower() in _decimals_cache:
        return _decimals_cache[contract.lower()]
    from yeaster.execution.x402 import _bsc_rpc
    r = _bsc_rpc("eth_call", [{"to": contract, "data": "0x313ce567"}, "latest"])   # decimals()
    dec = int(r, 16) if r and r != "0x" else 18
    _decimals_cache[contract.lower()] = dec
    return dec


def _sweep_prices(symbols: list[str]) -> dict[str, float]:
    """Real USD prices for swept holdings, straight from CMC. We deliberately do
    NOT use the injected price oracle here: it can be MOCK-backed (a mock-mode tick
    installs pseudo-prices, e.g. ~$36 for FLOKI → a 1,400-token dust bag reads as
    $50k on the LIVE wallet). CMC is the authoritative source for the live book;
    an un-priceable token is left unvalued rather than fabricated."""
    key = get_settings().cmc_api_key
    if not symbols or not key:
        return {}
    out: dict[str, float] = {}
    try:
        from yeaster.market.cmc import _rest_assets
        for a in _rest_assets(symbols, key):
            if a.price_usd and a.price_usd > 0:
                out[a.symbol.upper()] = float(a.price_usd)
    except Exception:
        pass
    return out


def _merge_onchain_holdings(pf: PortfolioState, address: str, read_chain: int) -> PortfolioState:
    """Merge any held ERC-20s the CLI omitted into the portfolio (BSC mainnet only).
    The cache holds the *priced* rows so CMC is hit at most once per TTL, not per poll."""
    if read_chain != 56 or not address or address == "unknown" or os.getenv("YST_WALLET_SWEEP", "1") != "1":
        return pf
    have = {b.symbol.upper() for b in pf.balances}
    now = time.time()
    cached = _sweep_cache.get(address)
    if cached and now - cached[0] < _SWEEP_TTL_SECONDS:
        priced = cached[1]
    else:
        priced = {}
        try:
            todo = {s: c for s, c in _universe_contracts().items() if s not in have}
            if todo:
                syms, contracts = list(todo), [todo[s] for s in todo]
                raw = _multicall3_balanceof(address, contracts)
                held = {sym: raw.get(c.lower(), 0) / 10 ** _erc20_decimals(c)
                        for sym, c in zip(syms, contracts) if raw.get(c.lower(), 0) > 0}
                prices = _sweep_prices(list(held))
                for sym, bal in held.items():
                    p = prices.get(sym)
                    priced[sym] = (bal, round(bal * p, 4) if p else None)   # value None if un-priceable
        except Exception:
            priced = {}
        _sweep_cache[address] = (now, priced)
    fresh = {s: bv for s, bv in priced.items() if s not in have}   # never double-count a now-tracked token
    if not fresh:
        return pf
    rows = list(pf.balances)
    total = pf.total_value_usd or sum(b.value_usd or 0.0 for b in rows)
    for sym, (bal, val) in fresh.items():
        rows.append(TokenBalance(symbol=sym, balance=bal, value_usd=val))
        if val:
            total += val
    positions = {r.symbol: round((r.value_usd or 0.0) / total, 6) for r in rows if total > 0}
    return pf.model_copy(update={"balances": rows, "total_value_usd": round(total, 4), "positions_pct": positions})


def _cli_portfolio(_chain_id: int) -> PortfolioState:
    key = _portfolio_chain_key()
    read_chain = next((cid for cid, k in _CHAIN_KEYS.items() if k == key), 56)
    raw = _run_cli(["wallet", "balance", "--chain", key, "--json"])
    address = str(raw.get("address") or get_settings().bsc_testnet_wallet_address or "unknown")

    rows: list[TokenBalance] = []
    total = 0.0
    # Native coin lives at the TOP LEVEL (symbol/available/total/totalUsd), not in tokens[].
    native_sym = str(raw.get("symbol") or "BNB").upper()
    native_bal = _amt(raw.get("available") or raw.get("total") or 0.0)
    native_usd = raw.get("totalUsd")
    native_val = float(native_usd) if native_usd is not None else native_bal * price(native_sym, "cli")
    if native_bal > 0:
        rows.append(TokenBalance(symbol=native_sym, balance=native_bal, value_usd=round(native_val, 4)))
        total += native_val
    # ERC-20 tokens.
    for row in raw.get("tokens") or raw.get("balances") or []:
        sym = str(row.get("symbol") or row.get("asset") or "").upper()
        if not sym:
            continue
        bal = _amt(row.get("balance") or row.get("amount") or 0.0)
        val = float(row["value_usd"]) if row.get("value_usd") is not None else bal * price(sym, "cli")
        total += val
        rows.append(TokenBalance(symbol=sym, balance=bal, value_usd=round(val, 4)))

    positions = {r.symbol: round((r.value_usd or 0.0) / total, 6) for r in rows if total > 0}
    pf = PortfolioState(address=address, chain_id=read_chain, native_balance=native_bal, balances=rows,
                        total_value_usd=round(total, 4), positions_pct=positions, captured_at=_iso(_now()))
    return _merge_onchain_holdings(pf, address, read_chain)


# ── The broker (two-step) ────────────────────────────────────────────────────


class TwakBroker:
    """Stateless two-step execution over the resolved TWAK surface."""

    def __init__(self, backend: str = "auto") -> None:
        self.requested = (backend or "auto").lower()
        self.backend = resolve_backend(backend)

    # Step 1 — quote
    def quote_swap(self, request: SwapRequest) -> SwapQuote:
        if self.backend == "cli":
            return _cli_quote(request)
        return _amm_quote(request, self.backend)

    @staticmethod
    def to_guard_runtime(quote: SwapQuote, portfolio: Optional[PortfolioState] = None) -> dict[str, Any]:
        runtime: dict[str, Any] = {"requested_slippage_bps": quote.expected_slippage_bps}
        if portfolio is not None:
            runtime["current_positions"] = dict(portfolio.positions_pct)
        return runtime

    # Step 2 — execute (only after a verified, quote-bound permit)
    def execute_approved_swap(self, quote: SwapQuote, token: ApprovalToken) -> SwapReceipt:
        if quote.chain_id not in permitted_chain_ids():
            return self._rejected(quote, f"Refusing chain_id {quote.chain_id}: not in {permitted_chain_ids()}.")
        try:
            verify_approval_token(token, quote)
        except ApprovalError as exc:
            return self._rejected(quote, f"Approval denied: {exc}")

        if self.backend == "cli":
            return _cli_execute(quote)
        return self._paper_execute(quote)

    def portfolio(self) -> PortfolioState:
        if self.backend == "cli":
            return _cli_portfolio(self._chain_id())
        state = _load_paper()
        return _portfolio_from_balances(state["address"], state["balances"], self.backend, self._chain_id())

    def _chain_id(self) -> int:
        return get_settings().trade_chain_id if get_settings().mainnet_unlocked else BSC_TESTNET_CHAIN_ID

    def _paper_execute(self, quote: SwapQuote) -> SwapReceipt:
        state = _load_paper()
        bal = state["balances"]
        have = float(bal.get(quote.from_asset, 0.0))
        if have + 1e-9 < quote.amount_in:
            return self._rejected(quote, f"Insufficient {quote.from_asset}: have {have}, need {quote.amount_in}")
        bal[quote.from_asset] = round(have - quote.amount_in, 10)
        bal[quote.to_asset] = round(float(bal.get(quote.to_asset, 0.0)) + quote.expected_amount_out, 10)
        if bal[quote.from_asset] <= 1e-9:
            bal.pop(quote.from_asset, None)
        _save_paper(state)
        tx = "0x" + hashlib.sha256(f"{quote.quote_hash}{_iso(_now())}".encode()).hexdigest()
        return SwapReceipt(
            status=SwapStatus.EXECUTED, backend=self.backend, chain_id=quote.chain_id, tx_hash=tx,
            from_asset=quote.from_asset, to_asset=quote.to_asset, amount_in=quote.amount_in,
            amount_out=quote.expected_amount_out, effective_slippage_bps=quote.expected_slippage_bps,
            quote_hash=quote.quote_hash, explorer_url=explorer_for_chain(quote.chain_id) + tx,
            executed_at=_iso(_now()),
            portfolio=_portfolio_from_balances(state["address"], state["balances"], self.backend, quote.chain_id),
        )

    @staticmethod
    def _rejected(quote: SwapQuote, reason: str) -> SwapReceipt:
        return SwapReceipt(
            status=SwapStatus.REJECTED, backend="n/a", chain_id=quote.chain_id,
            from_asset=quote.from_asset, to_asset=quote.to_asset, amount_in=quote.amount_in,
            quote_hash=quote.quote_hash, error=reason,
        )
