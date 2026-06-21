"""Position exit management — bracket reconciliation + trailing stops.

Each tick, before hunting new entries, the agent manages what it already holds:
  * if price has crossed the stop or take-profit, exit to the reserve (de-risk,
    always permitted by the firewall) and cancel the sibling bracket;
  * otherwise ratchet the trailing stop UP as the position makes new highs.
"""

from __future__ import annotations

from typing import Any, Optional

from yeaster.core.models import Mandate, OrderTicket
from yeaster.core.universe import DEFAULT_RESERVE
from yeaster.execution import brackets
from yeaster.execution.approval import issue_from_guard_log
from yeaster.execution.models import SwapRequest, SwapStatus
from yeaster.guard.firewall import RuntimeState, YeasterGuard

def _trail_stop(pos: dict, peak: float) -> float:
    """The trailing stop for ``pos`` given its running ``peak``.

    Volatility-scaled when the preset is in ATR mode and the position carries an
    ATR (``peak - atr_k * atr_entry``); otherwise the fixed-% fallback
    (``peak * (1 - trailing_pct)``). The result is floored by the position's hard
    stop (``entry * (1 - stop_pct)``) so the trail can only ever tighten upward —
    risk per trade is never loosened.
    """
    from yeaster.core.preset import active
    ex = active()["exit"]
    atr_entry = pos.get("atr_entry") or 0.0
    if ex.get("trailing_mode") == "atr" and atr_entry > 0:
        trail = peak - float(ex.get("atr_k", 3.0)) * atr_entry
    else:
        trail = peak * (1.0 - float(ex.get("trailing_pct", 0.03)))
    entry = pos.get("entry_price") or 0.0
    hard_stop = entry * (1.0 - float(ex.get("stop_pct", 0.08))) if entry else 0.0
    return max(hard_stop, trail)


def reconcile(state: dict, broker, by_sym, mandate: Mandate, twak_backend: str,
              emit=None) -> list[dict[str, Any]]:
    """Walk the position book; exit or trail each. Returns a list of actions taken."""
    _emit = emit or (lambda *a: None)
    actions: list[dict[str, Any]] = []
    positions = dict(state.get("positions", {}))

    for symbol, pos in positions.items():
        asset = by_sym.get(symbol.upper())
        price = getattr(asset, "price_usd", None)
        if not price or price <= 0:
            continue

        stop = pos.get("stop_price") or 0.0
        tp = pos.get("tp_price") or float("inf")

        if price <= stop or price >= tp:
            reason = "stop" if price <= stop else "take_profit"
            receipt = _exit_position(broker, state, symbol, pos, mandate, twak_backend)
            _cancel_brackets(pos, twak_backend)
            if receipt and receipt.status == SwapStatus.EXECUTED:
                pnl = (price - pos.get("entry_price", price)) * pos.get("qty", 0.0)
                state["realized_pnl_usd"] = state.get("realized_pnl_usd", 0.0) + pnl
                from yeaster.runtime import state as state_mod
                state_mod.record_exit(state, symbol, pnl_usd=pnl, reason=reason)
                actions.append({"symbol": symbol, "action": f"exit:{reason}", "price": price,
                                "pnl_usd": round(pnl, 4), "tx_hash": receipt.tx_hash})
                _emit("exit", {"text": f"{reason.upper()} {symbol} @ ${price:,.4f} · pnl ${pnl:+.2f}",
                               "symbol": symbol, "reason": reason, "pnl_usd": round(pnl, 4)})
            continue

        # trail the stop up (volatility-scaled; floored by the hard stop)
        peak = max(pos.get("peak_price", price), price)
        new_stop = round(_trail_stop(pos, peak), 10)
        if new_stop > stop:
            _retrail(state, broker, symbol, pos, new_stop, twak_backend)
            actions.append({"symbol": symbol, "action": "trail", "new_stop": new_stop})
            _emit("trail", {"text": f"trail {symbol} stop → ${new_stop:,.4f}", "symbol": symbol, "new_stop": new_stop})
        state["positions"][symbol]["peak_price"] = peak

    return actions


def _exit_position(broker, state, symbol, pos, mandate: Mandate, twak_backend):
    """Sell ``symbol`` → reserve. Retries on a transient revert (re-quotes a fresh
    route) and ensures the sell allowance exists, because a freshly-bought token has
    none and the first sell would otherwise revert — which would silently defeat the
    stop / take-profit / trailing exit."""
    qty = pos.get("qty", 0.0)
    if qty <= 0:
        return None
    from yeaster.execution import twak as _twak
    last = None
    for attempt in range(2):
        try:
            req = SwapRequest(from_asset=symbol, to_asset=DEFAULT_RESERVE, amount_in=qty,
                              chain_id=_chain_id(), slippage_tolerance_bps=mandate.max_slippage_bps)
            quote = broker.quote_swap(req)
            ticket = OrderTicket(from_asset=symbol, to_asset=DEFAULT_RESERVE, amount_pct=1.0,
                                 confidence=1.0, kind="exit", thesis="bracket exit")
            guard = YeasterGuard(mandate, safe_mode_latched=state.get("safe_mode_latched", False))
            log = guard.evaluate(ticket, RuntimeState(requested_slippage_bps=quote.expected_slippage_bps))
            if log.final_decision.value != "EXECUTED":   # de-risk should always pass, but be safe
                return None
            token = issue_from_guard_log(quote, log.model_dump())
            receipt = broker.execute_approved_swap(quote, token)
            if receipt and receipt.status == SwapStatus.EXECUTED:
                return receipt
            last = receipt
        except Exception:  # noqa: BLE001 — revert/transient; ensure approval then retry once
            last = None
        try:
            _twak.ensure_sell_approval(symbol, _chain_id())
        except Exception:
            pass
    return last


def _retrail(state, broker, symbol, pos, new_stop, twak_backend) -> None:
    old_id = pos.get("stop_id")
    if old_id:
        try:
            brackets.cancel(old_id, twak_backend)
        except Exception:
            pass
    try:
        spec = brackets.build_bracket_specs(symbol, pos.get("qty", 0.0), new_stop, pos.get("tp_price", 0.0))["stop"]
        new_id = brackets.place(spec, twak_backend).id
        state["positions"][symbol]["stop_id"] = new_id
    except Exception:
        pass
    state["positions"][symbol]["stop_price"] = new_stop


def _cancel_brackets(pos: dict, twak_backend: str) -> None:
    for key in ("stop_id", "tp_id"):
        if pos.get(key):
            try:
                brackets.cancel(pos[key], twak_backend)
            except Exception:
                pass


def _chain_id() -> int:
    from yeaster.core.settings import get_settings
    from yeaster.execution.models import BSC_TESTNET_CHAIN_ID
    return 56 if get_settings().mainnet_unlocked else BSC_TESTNET_CHAIN_ID
