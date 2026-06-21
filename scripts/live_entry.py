#!/usr/bin/env python3
"""Controlled single LIVE entry on BSC mainnet — the real-fill test.

Mirrors the agent's own `_open_position`: quote → firewall → approval token →
REAL on-chain swap → compute ATR(14) → place the native stop/TP brackets →
record the position (with `atr_entry`) so the ATR trail manages it thereafter.

Spends real funds. Requires the mainnet gate OPEN in the environment:
    YST_MAINNET=1  YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS

    python scripts/live_entry.py --from USDT --to CAKE --amount 0.5 --execute
"""

from __future__ import annotations

import argparse

from yeaster.core.models import Mandate, OrderTicket
from yeaster.core.preset import active
from yeaster.core.settings import get_settings
from yeaster.execution import brackets
from yeaster.execution.approval import issue_from_guard_log
from yeaster.execution.models import SwapRequest
from yeaster.execution.twak import TwakBroker
from yeaster.guard.firewall import RuntimeState, YeasterGuard
from yeaster.runtime import state as state_mod
from yeaster.runtime.atr_provider import atr_at_entry

MAINNET = 56


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_asset", default="USDT")
    ap.add_argument("--to", dest="to_asset", default="CAKE")
    ap.add_argument("--amount", type=float, default=0.5)
    ap.add_argument("--execute", action="store_true", help="actually broadcast the swap")
    args = ap.parse_args()

    s = get_settings()
    if not s.mainnet_unlocked:
        print("✋ mainnet gate CLOSED. Set YST_MAINNET=1 and "
              "YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS to run a live entry.")
        return 2

    sym = args.to_asset.upper()
    broker = TwakBroker(backend="cli")
    print(f"[live] backend={broker.backend} chain={MAINNET} (MAINNET)  {args.amount} {args.from_asset} → {sym}")

    # Step 1 — quote
    req = SwapRequest(from_asset=args.from_asset, to_asset=sym, amount_in=args.amount,
                      chain_id=MAINNET, slippage_tolerance_bps=int(active()["guard"]["max_slippage_bps"]))
    quote = broker.quote_swap(req)
    print(f"[quote] {quote.amount_in} {quote.from_asset} → ~{quote.expected_amount_out:.6f} {sym}  "
          f"slippage={quote.expected_slippage_bps}bps")

    # Step 2 — firewall (real guard, preset limits)
    g = active()["guard"]
    mandate = Mandate(mandate_id="live-entry", allowed_assets=[args.from_asset.upper(), sym, "USDC", "USDT"],
                      max_trade_pct=float(g["max_trade_pct"]), max_position_pct=float(g["max_position_pct"]),
                      max_slippage_bps=int(g["max_slippage_bps"]), hard_drawdown_pct=float(g["hard_drawdown_pct"]))
    ticket = OrderTicket(from_asset=args.from_asset, to_asset=sym, amount_pct=0.1,
                         confidence=1.0, kind="entry", thesis="live ATR-trail entry test")
    guard = YeasterGuard(mandate)
    log = guard.evaluate(ticket, RuntimeState(requested_slippage_bps=quote.expected_slippage_bps))
    print(f"[guard] {log.final_decision.value}  reasons={log.rejection_reasons or '-'}")

    if not args.execute:
        print("[live] quote-only (pass --execute to broadcast). ✋")
        return 0
    if log.final_decision.value != "EXECUTED":
        print("[live] guard blocked — not broadcasting.")
        return 1

    # Step 3 — REAL on-chain swap
    token = issue_from_guard_log(quote, log.model_dump())
    receipt = broker.execute_approved_swap(quote, token)
    print(f"[swap] {receipt.status.value}  tx={receipt.tx_hash}  {receipt.explorer_url or ''}")
    if receipt.status.value != "EXECUTED":
        print(f"[live] swap failed: {receipt.error}")
        return 1

    # Step 4 — entry bookkeeping + the new ATR trail wiring
    entry = (quote.amount_in / quote.expected_amount_out) if quote.expected_amount_out else 0.0
    qty = receipt.amount_out or quote.expected_amount_out
    ex = active()["exit"]
    atr_entry = atr_at_entry(sym, int(ex.get("atr_period", 14))) if ex.get("trailing_mode") == "atr" else 0.0
    stop_price = round(entry * (1.0 - ex["stop_pct"]), 10)
    tp_price = round(entry * (1.0 + ex["tp_pct"]), 10)
    print(f"[entry] price=${entry:.6f}  qty={qty:.6f} {sym}  ATR(14)=${atr_entry:.6f}  "
          f"stop=${stop_price:.6f}  tp=${tp_price:.6f}")
    print(f"[trail] ATR-3x distance=${3 * atr_entry:.6f}  (vs old fixed-3%=${entry * 0.03:.6f})")

    # Step 5 — native protective brackets (best-effort; sell back to USDT)
    stop_id = tp_id = None
    try:
        specs = brackets.build_bracket_specs(sym, qty, stop_price, tp_price, reserve="USDT")
        stop_id = brackets.place(specs["stop"], "cli").id
        tp_id = brackets.place(specs["take_profit"], "cli").id
        print(f"[bracket] placed stop={stop_id} tp={tp_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[bracket] placement failed ({exc}); position is small — protect via daemon/manual.")

    st = state_mod.load()
    state_mod.record_entry(st, sym, entry, qty, stop_price, tp_price, stop_id, tp_id, atr_entry=atr_entry)
    state_mod.save(st)
    print(f"[state] recorded {sym} position with atr_entry=${atr_entry:.6f}. Done. ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
