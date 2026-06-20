"""Persisted agent state — peak equity, drawdown memory, the position book, and
the Safe-Mode latch. One JSON file; the daemon and the API both read/write it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / "data" / "state" / "agent_state.json"

_DEFAULT: dict[str, Any] = {
    "peak_equity_usd": 0.0,
    "safe_mode_latched": False,
    "positions": {},          # SYM -> {entry_price, peak_price, qty, stop_price, tp_price, opened_at, stop_id, tp_id}
    "trades_today": 0,
    "last_trade_date": None,
    "last_tick_at": None,
    "realized_pnl_usd": 0.0,
    "wins": 0,
    "losses": 0,
    "recent_exits": [],       # [{symbol, pnl_usd, reason, at}] newest last, capped
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load(path: Path = STATE_PATH) -> dict[str, Any]:
    if path.exists():
        data = json.loads(path.read_text())
        return {**_DEFAULT, **data}
    return dict(_DEFAULT)


def save(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def update_equity(state: dict[str, Any], equity: float) -> float:
    """Update the peak and return the current drawdown fraction."""
    peak = max(state.get("peak_equity_usd", 0.0), equity)
    state["peak_equity_usd"] = peak
    return 0.0 if peak <= 0 else max(0.0, (peak - equity) / peak)


def roll_day(state: dict[str, Any]) -> None:
    if state.get("last_trade_date") != _today():
        state["trades_today"] = 0


def record_entry(state: dict[str, Any], symbol: str, entry_price: float, qty: float,
                 stop_price: float, tp_price: float, stop_id: Optional[str], tp_id: Optional[str]) -> None:
    state["positions"][symbol.upper()] = {
        "entry_price": entry_price, "peak_price": entry_price, "qty": qty,
        "stop_price": stop_price, "tp_price": tp_price, "opened_at": _now(),
        "stop_id": stop_id, "tp_id": tp_id,
    }
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["last_trade_date"] = _today()


def record_exit(state: dict[str, Any], symbol: str, pnl_usd: Optional[float] = None,
                reason: Optional[str] = None) -> None:
    state["positions"].pop(symbol.upper(), None)
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["last_trade_date"] = _today()
    if pnl_usd is not None:
        if pnl_usd >= 0:
            state["wins"] = state.get("wins", 0) + 1
        else:
            state["losses"] = state.get("losses", 0) + 1
        recent = state.get("recent_exits", [])
        recent.append({"symbol": symbol.upper(), "pnl_usd": round(pnl_usd, 4),
                       "reason": reason or "exit", "at": _now()})
        state["recent_exits"] = recent[-10:]


def unrealized_pnl(state: dict[str, Any], price_of) -> float:
    """Sum (current - entry) * qty across open positions. price_of(sym) -> float|None."""
    total = 0.0
    for sym, pos in state.get("positions", {}).items():
        p = price_of(sym)
        if p:
            total += (p - pos.get("entry_price", p)) * pos.get("qty", 0.0)
    return total


def book_for_llm(state: dict[str, Any], equity: float, drawdown: float,
                 unrealized: float = 0.0) -> dict[str, Any]:
    wins, losses = state.get("wins", 0), state.get("losses", 0)
    closed = wins + losses
    return {
        "equity_usd": round(equity, 2),
        "drawdown_pct": round(drawdown, 4),
        "trades_today": state.get("trades_today", 0),
        "open_positions": len(state.get("positions", {})),
        "realized_pnl_usd": round(state.get("realized_pnl_usd", 0.0), 2),
        "unrealized_pnl_usd": round(unrealized, 2),
        "win_rate": round(wins / closed, 3) if closed else None,
        "wins": wins, "losses": losses,
        "recent_exits": [f"{e['symbol']} {e['reason']} {e['pnl_usd']:+.2f}" for e in state.get("recent_exits", [])[-5:]],
    }
