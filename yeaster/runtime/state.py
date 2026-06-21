"""Persisted agent state — peak equity, drawdown memory, the position book, and
the Safe-Mode latch.

**Paper and live are isolated** into separate files (``agent_state_paper.json`` /
``agent_state_live.json``) so PnL, positions and brackets never mix between modes —
critical now that the mainnet gate is open and ``auto`` resolves to live.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = REPO_ROOT / "data" / "state"


def _state_path(mode: str = "paper") -> Path:
    m = "live" if str(mode).lower() == "live" else "paper"
    return _STATE_DIR / f"agent_state_{m}.json"


def state_mode(twak_backend: str = "auto") -> str:
    """The state bucket for a trade backend: 'live' iff it resolves to the on-chain
    CLI, else 'paper'. Keeps the two books fully separate."""
    from yeaster.execution.twak import resolve_backend
    return "live" if resolve_backend(twak_backend) == "cli" else "paper"


STATE_PATH = _state_path("paper")   # back-compat default (paper book)

_DEFAULT: dict[str, Any] = {
    "peak_equity_usd": 0.0,
    "safe_mode_latched": False,
    "positions": {},          # SYM -> {entry_price, peak_price, qty, stop_price, tp_price, atr_entry, opened_at, stop_id, tp_id}
    "trades_today": 0,
    "last_trade_date": None,
    "last_tick_at": None,
    "realized_pnl_usd": 0.0,
    "wins": 0,
    "losses": 0,
    "consecutive_losses": 0,  # current losing streak (reset on a win) — a PnL decision lever
    "realized_pnl_today": 0.0,
    "realized_pnl_date": None,
    "recent_exits": [],       # [{symbol, pnl_usd, reason, at}] newest last, capped
    "recent_activity": [],    # unified trade feed [{id, kind, symbol, ...}] — entries + exits from ALL paths
}


def _push_activity(state: dict[str, Any], event: dict[str, Any]) -> None:
    """Append a trade event to the unified feed (entries + exits, any path). The chat
    renders new events as cards so autonomous / tick / manual trades all surface."""
    event = {"id": f"{event['kind']}:{event['symbol']}:{_now()}", "at": _now(), **event}
    feed = state.get("recent_activity", [])
    feed.append(event)
    state["recent_activity"] = feed[-20:]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load(mode: str = "paper", path: Optional[Path] = None) -> dict[str, Any]:
    p = path or _state_path(mode)
    if p.exists():
        data = json.loads(p.read_text())
        return {**_DEFAULT, **data}
    return dict(_DEFAULT)


def save(state: dict[str, Any], mode: str = "paper", path: Optional[Path] = None) -> None:
    p = path or _state_path(mode)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


def update_equity(state: dict[str, Any], equity: float) -> float:
    """Update the peak and return the current drawdown fraction."""
    peak = max(state.get("peak_equity_usd", 0.0), equity)
    state["peak_equity_usd"] = peak
    return 0.0 if peak <= 0 else max(0.0, (peak - equity) / peak)


def roll_day(state: dict[str, Any]) -> None:
    if state.get("last_trade_date") != _today():
        state["trades_today"] = 0


def record_entry(state: dict[str, Any], symbol: str, entry_price: float, qty: float,
                 stop_price: float, tp_price: float, stop_id: Optional[str], tp_id: Optional[str],
                 atr_entry: float = 0.0) -> None:
    state["positions"][symbol.upper()] = {
        "entry_price": entry_price, "peak_price": entry_price, "qty": qty,
        "stop_price": stop_price, "tp_price": tp_price, "atr_entry": atr_entry,
        "opened_at": _now(), "stop_id": stop_id, "tp_id": tp_id,
    }
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["last_trade_date"] = _today()
    _push_activity(state, {"kind": "entry", "symbol": symbol.upper(),
                           "price": round(entry_price, 8), "qty": round(qty, 8)})


def record_exit(state: dict[str, Any], symbol: str, pnl_usd: Optional[float] = None,
                reason: Optional[str] = None) -> None:
    state["positions"].pop(symbol.upper(), None)
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["last_trade_date"] = _today()
    if pnl_usd is not None:
        if pnl_usd >= 0:
            state["wins"] = state.get("wins", 0) + 1
            state["consecutive_losses"] = 0
        else:
            state["losses"] = state.get("losses", 0) + 1
            state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
        # realized PnL for the current UTC day (the LLM sees this in its book)
        if state.get("realized_pnl_date") != _today():
            state["realized_pnl_today"] = 0.0
            state["realized_pnl_date"] = _today()
        state["realized_pnl_today"] = round(state.get("realized_pnl_today", 0.0) + pnl_usd, 6)
        recent = state.get("recent_exits", [])
        recent.append({"symbol": symbol.upper(), "pnl_usd": round(pnl_usd, 4),
                       "reason": reason or "exit", "at": _now()})
        state["recent_exits"] = recent[-10:]
    # every exit (with or without realized PnL) surfaces a card in the chat
    _push_activity(state, {"kind": "exit", "symbol": symbol.upper(),
                           "pnl_usd": round(pnl_usd, 4) if pnl_usd is not None else None,
                           "reason": reason or "exit"})


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
        "realized_pnl_today": round(state.get("realized_pnl_today", 0.0), 2)
        if state.get("realized_pnl_date") == _today() else 0.0,
        "unrealized_pnl_usd": round(unrealized, 2),
        "win_rate": round(wins / closed, 3) if closed else None,
        "wins": wins, "losses": losses,
        "consecutive_losses": state.get("consecutive_losses", 0),
        "recent_exits": [f"{e['symbol']} {e['reason']} {e['pnl_usd']:+.2f}" for e in state.get("recent_exits", [])[-5:]],
    }
