"""Emergency flatten — sell every open position to the reserve and clear all
automations. Powers the UI **kill switch** (vs. the graceful unlock, which only
sweeps orphaned automations and keeps protective brackets).
"""

from __future__ import annotations

from typing import Any

from yeaster.core.models import Mandate
from yeaster.core.universe import DEFAULT_RESERVE
from yeaster.execution import brackets
from yeaster.execution.twak import TwakBroker
from yeaster.runtime import exits as exits_mod
from yeaster.runtime import state as state_mod


def _default_mandate() -> Mandate:
    from yeaster.core.preset import active
    g = active()["guard"]
    return Mandate(mandate_id="flatten", allowed_assets=[DEFAULT_RESERVE],
                   max_trade_pct=1.0, max_position_pct=1.0,
                   max_slippage_bps=int(g["max_slippage_bps"]), hard_drawdown_pct=0.99)


def flatten_all(twak_backend: str = "auto", emit=None) -> dict[str, Any]:
    """Market-sell every open position to the reserve (USDT), cancel its brackets,
    then cancel ALL remaining automations. De-risk exits are always guard-allowed."""
    _emit = emit or (lambda *a: None)
    mode = state_mod.state_mode(twak_backend)
    st = state_mod.load(mode)
    broker = TwakBroker(twak_backend)
    from yeaster.market import cmc
    by_sym = cmc.build_snapshot(twak_backend if twak_backend == "mock" else "auto").by_symbol()
    mandate = _default_mandate()

    sold: list[dict[str, Any]] = []
    for symbol in list(st.get("positions", {}).keys()):
        pos = st["positions"][symbol]
        receipt = exits_mod._exit_position(broker, st, symbol, pos, mandate, twak_backend)
        ok = bool(receipt and receipt.status.value == "EXECUTED")
        if ok:
            # Only tear down the protective bracket AFTER the sell confirms — never
            # leave a still-held position naked because its sell reverted.
            exits_mod._cancel_brackets(pos, twak_backend)
            price = getattr(by_sym.get(symbol.upper()), "price_usd", None) or pos.get("entry_price", 0.0)
            pnl = (price - pos.get("entry_price", price)) * pos.get("qty", 0.0)
            st["realized_pnl_usd"] = st.get("realized_pnl_usd", 0.0) + pnl
            state_mod.record_exit(st, symbol, pnl_usd=pnl, reason="flatten")
        sold.append({"symbol": symbol, "sold": ok, "tx": getattr(receipt, "tx_hash", None)})
        _emit("flatten", {"text": f"flatten {symbol} -> {DEFAULT_RESERVE} ({'ok' if ok else 'FAILED — kept its bracket'})",
                          "symbol": symbol, "sold": ok})

    state_mod.save(st, mode)
    # Sweep automations with no remaining tracked position; brackets of any position
    # that failed to sell are deliberately kept (still protected on-chain).
    cancelled = brackets.cancel_orphans(list(st.get("positions", {}).keys()), twak_backend)
    _emit("flatten", {"text": f"swept {cancelled} orphaned automations", "cancelled": cancelled})
    return {"flattened": sold, "automations_cancelled": cancelled,
            "unsold": [s["symbol"] for s in sold if not s["sold"]]}
