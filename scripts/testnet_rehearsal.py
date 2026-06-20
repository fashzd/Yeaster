#!/usr/bin/env python3
"""Live testnet rehearsal: quote (and optionally execute) one guarded swap.

Exercises the REAL two-step path against the live TWAK CLI on BSC testnet — quote
→ firewall → approval token → execute — without any of the brain. Quote-only by
default; pass --execute to broadcast (needs testnet funds + gas).

    set -a; . ./.env; set +a
    python scripts/testnet_rehearsal.py --from USDC --to CAKE --amount 1.0
    python scripts/testnet_rehearsal.py --from USDC --to CAKE --amount 1.0 --execute
"""

from __future__ import annotations

import argparse

from yeaster.core.models import Mandate, OrderTicket
from yeaster.execution.approval import issue_from_guard_log
from yeaster.execution.models import BSC_TESTNET_CHAIN_ID, SwapRequest
from yeaster.execution.twak import TwakBroker
from yeaster.guard.firewall import RuntimeState, YeasterGuard


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_asset", default="USDC")
    ap.add_argument("--to", dest="to_asset", default="CAKE")
    ap.add_argument("--amount", type=float, default=1.0)
    ap.add_argument("--execute", action="store_true", help="actually broadcast (needs testnet funds)")
    args = ap.parse_args()

    broker = TwakBroker(backend="cli")
    print(f"[rehearsal] backend={broker.backend} chain={BSC_TESTNET_CHAIN_ID} (testnet)")

    req = SwapRequest(from_asset=args.from_asset, to_asset=args.to_asset,
                      amount_in=args.amount, chain_id=BSC_TESTNET_CHAIN_ID, slippage_tolerance_bps=50)
    quote = broker.quote_swap(req)
    print(f"[quote] {quote.amount_in} {quote.from_asset} → ~{quote.expected_amount_out:.6f} "
          f"{quote.to_asset}  slippage={quote.expected_slippage_bps}bps  hash={quote.quote_hash[:14]}…")

    mandate = Mandate(mandate_id="rehearsal", allowed_assets=[args.from_asset.upper(), args.to_asset.upper(), "USDC", "USDT"],
                      max_trade_pct=1.0, max_position_pct=1.0, max_slippage_bps=100, hard_drawdown_pct=0.99)
    ticket = OrderTicket(from_asset=args.from_asset, to_asset=args.to_asset, amount_pct=0.5,
                         confidence=1.0, thesis="testnet rehearsal")
    guard = YeasterGuard(mandate)
    log = guard.evaluate(ticket, RuntimeState(requested_slippage_bps=quote.expected_slippage_bps))
    print(f"[guard] {log.final_decision.value}  reasons={log.rejection_reasons or '-'}")

    if not args.execute:
        print("[rehearsal] quote-only (pass --execute to broadcast). ✋")
        return 0
    if log.final_decision.value != "EXECUTED":
        print("[rehearsal] guard blocked — not broadcasting.")
        return 1

    token = issue_from_guard_log(quote, log.model_dump())
    receipt = broker.execute_approved_swap(quote, token)
    print(f"[execute] {receipt.status.value}  tx={receipt.tx_hash}  {receipt.explorer_url or ''}")
    return 0 if receipt.status.value == "EXECUTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
