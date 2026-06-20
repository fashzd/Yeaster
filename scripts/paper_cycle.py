#!/usr/bin/env python3
"""Full paper cycle: snapshot → think → guard → paper execute → brackets → proof.

Runs entirely offline (mock data, paper wallet). Proves the pipeline composes
end-to-end and seals a verifiable proof block.

    python scripts/paper_cycle.py
"""

from __future__ import annotations

from yeaster.execution import twak
from yeaster.proof import ledger
from yeaster.runtime import tick as tick_mod


def _breakout_bars(base: float, n: int = 30):
    bars = [{"price": base + 0.001 * i, "volume": 1_000.0} for i in range(n - 1)]
    bars.append({"price": bars[-1]["price"] * 1.15, "volume": 5_000.0})
    return bars


def main() -> int:
    twak.seed_paper(1000.0)
    hist = {"CAKE": _breakout_bars(2.0), "LINK": _breakout_bars(14.0)}

    result = tick_mod.run_tick(cmc_backend="mock", twak_backend="paper", arm="det_safety",
                               guard_enabled=True, posture_override="selective", hist=hist)

    print("=" * 64)
    print(f"posture={result['posture']}  equity=${result['equity_usd']:.2f}  dd={result['drawdown_pct']:.1%}")
    sc = result["reasoning"].get("screen", {})
    print(f"SCREEN: {sc.get('text')}  detectors={sc.get('detectors')}")
    gr = result["reasoning"].get("grade", {})
    print(f"GRADE : top={[t['symbol'] + ':' + format(t['composite'], '+.3f') for t in gr.get('top', [])][:5]}")
    vt = result["reasoning"].get("vet", {})
    print(f"VET   : {vt.get('text')}")
    d = result["decision"]
    print(f"COMMIT: pick={d['pick']} conviction={d['conviction']} arm={d['arm']}")
    print(f"        {d['rationale']}")
    if result.get("receipt"):
        r = result["receipt"]
        print(f"EXEC  : {r['status']} {r.get('amount_out')} {r['to_asset']}  tx={r.get('tx_hash', '')[:18]}…")
    print(f"GUARD : {result['guard']['final_decision'] if result.get('guard') else 'n/a'}")
    print(f"PROOF : block {result['proof_block_hash'][:18]}…  chain_verified={ledger.verify_chain()}")
    print(f"POSNS : {list(result['positions'].keys())}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
