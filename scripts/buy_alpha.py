#!/usr/bin/env python3
"""x402 demo — buy the agent's daily alpha with a real on-chain USDT payment.

Flow: read the price + pay-to from the running API → send USDT on BSC (via TWAK)
→ POST the payment tx hash → receive the unlocked alpha.

    # API must be running with YST_X402=1
    python scripts/buy_alpha.py                       # pays + unlocks
    python scripts/buy_alpha.py --payment-tx 0x..     # already paid; just redeem
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import requests

API = os.environ.get("YEASTER_API", "http://localhost:8000")
USDT = "0x55d398326f99059fF775485246999027B3197955"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payment-tx", help="an existing USDT payment tx hash to redeem")
    args = ap.parse_args()

    teaser = requests.get(f"{API}/api/x402/alpha/teaser", timeout=15).json()
    if not teaser.get("enabled"):
        print("x402 alpha sales are disabled (set YST_X402=1 on the server).")
        return 2
    price, pay_to = teaser["price_usd"], teaser["pay_to"]
    print(f"[x402] daily alpha price: {price} USDT → {pay_to}")
    print(f"[x402] locked teaser: {json.dumps(teaser.get('teaser'))}")

    tx = args.payment_tx
    if not tx:
        bin_ = os.environ.get("TWAK_CLI_BIN", "twak")
        print(f"[x402] paying {price} USDT to {pay_to} on BSC …")
        raw = subprocess.run([bin_, "transfer", "--to", pay_to, "--token", USDT,
                              "--amount", str(price), "--chain", "bsc", "--json"],
                             capture_output=True, text=True, timeout=120)
        out = raw.stdout.strip()
        try:
            tx = json.loads(out).get("txHash") or json.loads(out).get("hash")
        except Exception:
            print(f"[x402] payment failed: {raw.stderr.strip() or out}")
            return 1
        print(f"[x402] payment tx: {tx}")

    r = requests.post(f"{API}/api/x402/alpha", json={"payment_tx": tx}, timeout=30)
    body = r.json()
    if r.status_code == 200 and body.get("paid"):
        a = body.get("alpha", {})
        print(f"\n✅ UNLOCKED alpha: {a.get('symbol')}  conviction {a.get('conviction')}  ({a.get('posture')})")
        print(f"   thesis: {a.get('thesis')}")
        print(f"   proof:  {a.get('proof_block_hash')}")
        return 0
    print(f"\n[{r.status_code}] {json.dumps(body)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
