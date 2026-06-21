"""Performance metrics over an equity curve + per-trade returns.

Deliberately dependency-free (no numpy): the agent repo stays lean.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Metrics:
    total_return: float      # fraction, e.g. 0.12 = +12%
    max_drawdown: float      # fraction, positive number
    sharpe: float            # annualized (daily returns * sqrt(365))
    n_trades: int
    win_rate: float          # fraction of closed trades with pnl > 0
    avg_win: float           # mean pct return of winners
    avg_loss: float          # mean pct return of losers (negative)
    start_equity: float
    final_equity: float

    def as_dict(self) -> dict:
        return asdict(self)


def max_drawdown(equity: list[float]) -> float:
    peak = float("-inf")
    mdd = 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)
    return mdd


def sharpe(equity: list[float], periods_per_year: int = 365) -> float:
    if len(equity) < 3:
        return 0.0
    rets = [(equity[i] / equity[i - 1] - 1.0) for i in range(1, len(equity)) if equity[i - 1] > 0]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (mean / sd) * math.sqrt(periods_per_year)


def summarize(equity: list[float], trade_pnls: list[float], start_equity: float) -> Metrics:
    """``trade_pnls`` are per-trade fractional returns (net of costs)."""
    final = equity[-1] if equity else start_equity
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]
    return Metrics(
        total_return=(final / start_equity - 1.0) if start_equity > 0 else 0.0,
        max_drawdown=max_drawdown(equity),
        sharpe=sharpe(equity),
        n_trades=len(trade_pnls),
        win_rate=(len(wins) / len(trade_pnls)) if trade_pnls else 0.0,
        avg_win=(sum(wins) / len(wins)) if wins else 0.0,
        avg_loss=(sum(losses) / len(losses)) if losses else 0.0,
        start_equity=start_equity,
        final_equity=final,
    )
