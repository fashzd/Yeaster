"""BSC token resolution for live swaps.

TWAK's built-in registry misses most whitelist tokens, so we resolve a symbol to
its canonical BSC contract address via the CoinMarketCap info endpoint (cached on
disk). Contract addresses are also the collision-proof identifier (USDf ≠ USDF).
Natives/majors that TWAK already knows pass through as symbols.
(Proven resolver, ported from the predecessor.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "wallet" / "bsc_contracts.json"

# TWAK resolves these by symbol on BSC; don't look them up.
_PASS_THROUGH = {"BNB", "ETH", "USDT", "USDC", "BTCB", "WBNB", "DAI", "BUSD"}


def resolve_bsc_contract(symbol: str) -> Optional[str]:
    """Symbol → BSC contract address (CMC-sourced, disk-cached). None if unresolved."""
    sym = symbol.upper()
    cache: dict = {}
    if _CACHE_PATH.exists():
        try:
            cache = json.loads(_CACHE_PATH.read_text())
            if sym in cache:
                return cache[sym] or None   # "" is a cached MISS → None
        except Exception:
            cache = {}
    api_key = os.environ.get("CMC_API_KEY") or os.environ.get("CMC_MCP_API_KEY")
    if not api_key:
        return None
    import requests

    try:
        resp = requests.get(
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/info",
            headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
            params={"symbol": sym}, timeout=20,
        )
        resp.raise_for_status()
        nodes = resp.json().get("data", {}).get(sym) or []
        if isinstance(nodes, dict):
            nodes = [nodes]
        contract = None
        for node in nodes:
            for platform in node.get("contract_address", []):
                name = (platform.get("platform", {}).get("name") or "").lower()
                if "bnb" in name or name == "bsc":
                    contract = platform.get("contract_address")
                    break
            if contract:
                break
    except Exception:
        return None
    # Cache the result either way — a MISS ("") too, so an unresolvable ticker
    # (e.g. an ambiguous "H") isn't re-queried over the network every tick.
    cache[sym] = contract or ""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass
    return contract


def token_arg(symbol: str) -> str:
    """The arg to give twak: symbol for natives/majors, else the BSC contract (or symbol)."""
    sym = symbol.upper()
    if sym in _PASS_THROUGH:
        return sym
    return resolve_bsc_contract(sym) or sym


def has_address(symbol: str) -> bool:
    return symbol.upper() in _PASS_THROUGH or resolve_bsc_contract(symbol) is not None
