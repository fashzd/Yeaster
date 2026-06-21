"""Render backtest results as JSON + a plain-text report (no plotting deps).

Every report carries the honesty/scope notes so a reader can never mistake this
for a validation of the live agent's full (live-CMC-weighted) decision.
"""

from __future__ import annotations

import json

from .engine import BacktestResult

HONESTY_NOTES = [
    "Point-in-time & walk-forward: a decision on date t sees only bars dated <= t; entries fill next-day open.",
    "Costs modeled: fee + slippage charged on both entry and exit.",
    "Exits modeled on true intraday High/Low (stop / take-profit / trailing), with gap-open fills.",
    "OHLCV-only: entries use the deterministic SCREEN detectors + local indicators.",
    "OUT OF SCOPE: the live GRADE composite (~85% live-CMC-skill weight: perp/whale/sentiment/...) is NOT "
    "reconstructible from bars and never enters this backtest. This calibrates the entry SCREEN and the "
    "EXIT BRACKET, not the live agent's full edge.",
    "Caveats that real data does NOT fix: survivorship bias (delisted tokens absent), per-token history "
    "depth, and single-window sample size.",
]


def result_to_dict(r: BacktestResult) -> dict:
    return {
        "metrics": r.metrics.as_dict(),
        "exit": r.exit_label,
        "config": r.config,
        "n_days": r.n_days,
        "universe_size": r.universe_size,
        "date_range": list(r.date_range),
        "trades": r.trades,
        "equity_curve": [{"date": d, "equity": e} for d, e in r.equity_curve],
        "honesty": HONESTY_NOTES,
    }


def result_to_json(r: BacktestResult) -> str:
    return json.dumps(result_to_dict(r), indent=2)


def text_summary(r: BacktestResult) -> str:
    m = r.metrics
    L = [
        "Yeaster backtest — exit-aware, point-in-time",
        f"  exit bracket : {r.exit_label}",
        f"  window       : {r.date_range[0]} -> {r.date_range[1]}  ({r.n_days} trading days)",
        f"  universe     : {r.universe_size} symbols  |  costs {r.config['round_trip_cost_pct']}% round-trip",
        "",
        f"  total return : {m.total_return * 100:+.2f}%",
        f"  max drawdown : {m.max_drawdown * 100:.2f}%",
        f"  sharpe       : {m.sharpe:.3f}",
        f"  trades       : {m.n_trades}  (win-rate {m.win_rate * 100:.1f}%)",
        f"  avg win/loss : {m.avg_win * 100:+.2f}% / {m.avg_loss * 100:+.2f}%",
        f"  equity       : {m.start_equity:.2f} -> {m.final_equity:.2f}",
        "",
        "  honesty / scope:",
    ]
    L += [f"    - {n}" for n in HONESTY_NOTES]
    return "\n".join(L)


def sweep_table(rows: list[dict]) -> str:
    head = (f"  {'trailing config':<26}{'return':>9}{'maxDD':>8}{'sharpe':>8}"
            f"{'win%':>7}{'avgWin':>8}{'trades':>8}{'H1':>8}{'H2':>8}  flags")
    L = ["Trailing-stop sweep (entries + stop + TP fixed; ranked: consistent, sharpe, return)", "", head]
    for r in rows:
        flags = []
        if r["is_live_default"]:
            flags.append("LIVE-DEFAULT")
        if r["consistent"]:
            flags.append("consistent")
        L.append(
            f"  {r['label']:<26}{r['total_return'] * 100:>+8.2f}%{r['max_drawdown'] * 100:>7.2f}%"
            f"{r['sharpe']:>8.2f}{r['win_rate'] * 100:>6.1f}%{r['avg_win'] * 100:>+7.2f}%"
            f"{r['n_trades']:>8}{r['ret_first_half'] * 100:>+7.2f}%{r['ret_second_half'] * 100:>+7.2f}%"
            f"  {' '.join(flags)}"
        )
    return "\n".join(L)


def sweep_to_json(rows: list[dict]) -> str:
    return json.dumps({"sweep": rows, "honesty": HONESTY_NOTES}, indent=2)
