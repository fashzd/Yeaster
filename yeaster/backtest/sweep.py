"""Trailing-stop sweep — the core quant-research question.

Holds the entry logic and the stop/take-profit fixed (from the live preset) and
varies ONLY the trailing configuration, so any difference is attributable to the
trail. Reports each variant's metrics plus first-half / second-half returns as a
cheap stability check, ranked so a robust (consistent + risk-adjusted) winner
rises to the top.

Note: entry *signals* are identical across variants (the SCREEN decision never
sees the exit config); the portfolio path can differ slightly because realized
drawdown feeds position sizing. That is realistic, not a bug — flagged in output.
"""

from __future__ import annotations

from dataclasses import replace

from .engine import BacktestConfig, BacktestResult, preset_exit, run_backtest
from .exits import ExitConfig


def default_grid(base: ExitConfig) -> list[ExitConfig]:
    """Trailing variants over the preset's stop/TP. ``base`` supplies stop/tp."""
    s, t = base.stop_pct, base.tp_pct
    grid: list[ExitConfig] = []
    # Fixed-% trails, including the live default (3%) and "no trail".
    for tp in (0.0, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15):
        grid.append(ExitConfig(stop_pct=s, tp_pct=t, trailing_pct=tp, trailing_mode="fixed"))
    # Volatility-scaled (ATR) trails.
    for k in (2.0, 2.5, 3.0):
        grid.append(ExitConfig(stop_pct=s, tp_pct=t, trailing_mode="atr", atr_k=k))
    # Profit-armed fixed trails (don't trail until in profit).
    grid.append(ExitConfig(stop_pct=s, tp_pct=t, trailing_pct=0.05, trailing_mode="fixed", arm_pct=0.08))
    grid.append(ExitConfig(stop_pct=s, tp_pct=t, trailing_pct=0.08, trailing_mode="fixed", arm_pct=0.08))
    return grid


def bracket_grid(atr_k: float = 3.0) -> list[ExitConfig]:
    """Full exit-bracket grid: stop × take-profit, all on the ATR trail. ``tp=0``
    means no take-profit (let the trail do all the work)."""
    grid: list[ExitConfig] = []
    for stop in (0.06, 0.08, 0.10, 0.12):
        for tp in (0.0, 0.16, 0.24, 0.32, 0.40):
            grid.append(ExitConfig(stop_pct=stop, tp_pct=tp, trailing_mode="atr", atr_k=atr_k))
    return grid


def _half_returns(curve: list[tuple[str, float]]) -> tuple[float, float]:
    if len(curve) < 4:
        return 0.0, 0.0
    mid = len(curve) // 2
    e0, em, e1 = curve[0][1], curve[mid][1], curve[-1][1]
    r1 = (em / e0 - 1.0) if e0 > 0 else 0.0
    r2 = (e1 / em - 1.0) if em > 0 else 0.0
    return r1, r2


def sweep_trailing(source, base_config: BacktestConfig,
                   grid: list[ExitConfig] | None = None) -> list[dict]:
    """Run each trailing variant and return ranked rows."""
    base_exit = base_config.exit or preset_exit()
    variants = grid or default_grid(base_exit)
    rows: list[dict] = []
    for ec in variants:
        result: BacktestResult = run_backtest(source, replace(base_config, exit=ec))
        m = result.metrics
        r1, r2 = _half_returns(result.equity_curve)
        rows.append({
            "label": ec.label(),
            "is_live_default": (ec.trailing_mode == "fixed" and abs(ec.trailing_pct - base_exit.trailing_pct) < 1e-9
                                and ec.arm_pct == 0.0),
            "total_return": m.total_return,
            "max_drawdown": m.max_drawdown,
            "sharpe": m.sharpe,
            "win_rate": m.win_rate,
            "avg_win": m.avg_win,
            "avg_loss": m.avg_loss,
            "n_trades": m.n_trades,
            "ret_first_half": r1,
            "ret_second_half": r2,
            "consistent": (r1 > 0 and r2 > 0),
        })
    # Robust first: both halves positive, then risk-adjusted, then return.
    rows.sort(key=lambda r: (r["consistent"], r["sharpe"], r["total_return"]), reverse=True)
    return rows


def sweep_brackets(source, base_config: BacktestConfig,
                   grid: list[ExitConfig] | None = None) -> list[dict]:
    """Sweep the full exit bracket (stop × TP, ATR trail) and return ranked rows."""
    variants = grid or bracket_grid()
    rows: list[dict] = []
    for ec in variants:
        result: BacktestResult = run_backtest(source, replace(base_config, exit=ec))
        m = result.metrics
        r1, r2 = _half_returns(result.equity_curve)
        rows.append({
            "label": ec.label(),
            "is_live_default": False,
            "total_return": m.total_return, "max_drawdown": m.max_drawdown, "sharpe": m.sharpe,
            "win_rate": m.win_rate, "avg_win": m.avg_win, "avg_loss": m.avg_loss, "n_trades": m.n_trades,
            "ret_first_half": r1, "ret_second_half": r2, "consistent": (r1 > 0 and r2 > 0),
        })
    rows.sort(key=lambda r: (r["consistent"], r["sharpe"], r["total_return"]), reverse=True)
    return rows
