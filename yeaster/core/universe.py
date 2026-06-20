"""The competition universe — the official 148-token whitelist.

The whitelist (``whitelist.json``) is the **hard tradeable universe**: the agent
may only ever target a token on this list. From it we derive:
  * ``STABLES``   — reserve / de-risk assets (never momentum targets);
  * ``UNIVERSE``  — the momentum set the screen scouts (whitelist − stables − pegged − references);
  * ``ALLOWLIST`` — the full whitelist the firewall permits (incl. stables for exits).

All matching is case-insensitive (the list has mixed case: USDe, XAUt, …).
"""

from __future__ import annotations

import json
from pathlib import Path

_WHITELIST_PATH = Path(__file__).resolve().parent / "whitelist.json"
_RAW = json.loads(_WHITELIST_PATH.read_text())
_SYMBOLS: list[str] = [s.upper() for s in _RAW["symbols"]]

# The full competition whitelist (uppercased), the firewall allowlist.
ALLOWLIST: tuple[str, ...] = tuple(dict.fromkeys(_SYMBOLS))

# Reserve / de-risk stables — never momentum targets.
STABLES: frozenset[str] = frozenset(
    s for s in ALLOWLIST if s in {
        "USDT", "USDC", "DAI", "USD1", "USDE", "USDD", "TUSD", "FDUSD", "BUSD", "FRAX", "FRXUSD",
    }
)

# Tokenized gold + BTC references — on the list but not momentum alts.
PEGGED_OR_REFERENCE: frozenset[str] = frozenset(
    s for s in ALLOWLIST if s in {"XAUT", "XAUM", "PAXG", "BTC", "BTCB"}
)

_NON_MOMENTUM = STABLES | PEGGED_OR_REFERENCE

# The momentum universe the screen stage scouts (preserves whitelist order).
UNIVERSE: tuple[str, ...] = tuple(s for s in ALLOWLIST if s not in _NON_MOMENTUM)

DEFAULT_RESERVE = "USDC"
COMPETITION_CONTRACT = _RAW.get("competition_contract")


def is_stable(symbol: str) -> bool:
    return symbol.upper() in STABLES


def is_whitelisted(symbol: str) -> bool:
    return symbol.upper() in ALLOWLIST


def is_tradeable(symbol: str) -> bool:
    """A valid momentum target: whitelisted and not a stable/pegged/reference."""
    s = symbol.upper()
    return s in ALLOWLIST and s not in _NON_MOMENTUM


def default_symbols() -> list[str]:
    """All symbols a snapshot should cover — the whole whitelist."""
    return list(ALLOWLIST)
