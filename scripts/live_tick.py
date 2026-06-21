#!/usr/bin/env python3
"""Run ONE full LIVE autonomous tick on mainnet and print the reasoning trace.

snapshot → wallet/equity → reconcile (exits/ATR-trail) → SCREEN → GRADE → VET →
COMMIT → execute (+ native bracket). Real data, real funds. Requires the gate:
    YST_MAINNET=1  YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS

    python scripts/live_tick.py
"""

from __future__ import annotations

from yeaster.core.settings import get_settings
from yeaster.runtime import tick as tick_mod


def _printer(event: str, payload) -> None:
    if event in ("screen", "grade", "vet", "trail", "exit", "decision"):
        txt = payload.get("text") if isinstance(payload, dict) else str(payload)
        if txt:
            print(f"  · {event}: {txt}")


def main() -> int:
    s = get_settings()
    if not s.mainnet_unlocked:
        print("✋ mainnet gate CLOSED. Set YST_MAINNET=1 + YST_MAINNET_CONFIRM to run live.")
        return 2

    print(f"[live-tick] cmc=auto twak=cli  gate=OPEN  grade_cap={s.grade_cap}")
    r = tick_mod.run_tick(cmc_backend="auto", twak_backend="cli", guard_enabled=True, emit=_printer)

    print("=" * 70)
    print(f"posture={r['posture']}  equity=${r['equity_usd']:.2f}  drawdown={r['drawdown_pct']:.1%}")
    sc = r["reasoning"].get("screen", {})
    print(f"SCREEN : {sc.get('text')}  detectors={sc.get('detectors')}")
    gr = r["reasoning"].get("grade", {})
    print(f"GRADE  : top={[t['symbol'] + ':' + format(t['composite'], '+.3f') for t in gr.get('top', [])][:6]}")
    vt = r["reasoning"].get("vet", {})
    print(f"VET    : {vt.get('text')}")
    d = r["decision"]
    print(f"COMMIT : pick={d['pick']}  conviction={d['conviction']}  arm={d['arm']}")
    print(f"         {d['rationale']}")
    if r.get("receipt"):
        rc = r["receipt"]
        print(f"EXEC   : {rc.get('status')}  tx={rc.get('tx_hash')}  {rc.get('explorer_url') or ''}")
    else:
        print("EXEC   : no entry this tick (stand-down or no qualifying candidate)")
    if r.get("exit_actions"):
        print(f"MANAGE : {r['exit_actions']}")
    print(f"PROOF  : {r.get('proof_block_hash')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
