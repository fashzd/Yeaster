"""The finalized house strategy — Yeaster Momentum.

The single backtested, live-default config (the proven edge: hunts breakouts and
trending runners, decided by the bold lead with native auto-brackets). These are
the exact numbers validated in the year-long walk-forward — change them only with
fresh validation.
"""

from __future__ import annotations

from typing import Any

# The 5 detectors of the finalized strategy (NOT the full screener set).
MOMENTUM_DETECTORS = ["rel_strength", "breakout", "extended_runner", "vol_surge", "scanner_spot"]

# All 8 grade dimensions with their proven base weights.
MOMENTUM_DIMS = {
    "kline": 1.0, "perp": 1.0, "transition": 1.0, "dark_flow": 0.8,
    "sector": 0.8, "whale": 0.7, "unlock": 0.6, "sentiment": 0.6,
}

# Let-winners-run exit calibration (the actual bracket levels, distinct from the
# 3.5% sizing risk-divisor): wide stop, wider target, volatility-scaled trail.
#
# Trailing is volatility-scaled (ATR): the trail rides `atr_k * ATR(atr_period)`
# under the running peak instead of a flat percent, so each coin gets breathing
# room proportional to its own daily range (a flat 3% clipped every winner on
# daily-bar noise — see data/backtests/reports/CONCLUSION-trailing.md). The hard
# `stop_pct` is always the floor; `trailing_pct` is the fixed-% fallback used when
# an ATR value is unavailable (e.g. a brand-new listing with too little history).
#
# Take-profit is a WIDE backstop (40%), not a strangle: a real-OHLC backtest over
# 135 tokens showed a tight 16% target converting the strategy's asymmetric runners
# into capped scratch trades (it turned a +46% trending half into a loss). A wide TP
# + the ATR trail lets winners run while still guaranteeing an exit on a parabolic
# spike. (A no-TP variant scored higher only by running 5x concentration into a 33%
# drawdown — over the 30% competition DQ line — so it is deliberately NOT used.)
MOMENTUM_EXIT = {
    "stop_pct": 0.08, "tp_pct": 0.40,
    "trailing_mode": "atr",     # "atr" | "fixed"
    "atr_k": 3.0,               # trail distance = atr_k * ATR(atr_period)
    "atr_period": 14,
    "trailing_pct": 0.03,       # fallback only, when ATR is unavailable
}

# Firewall rails.
MOMENTUM_GUARD = {"max_trade_pct": 0.12, "max_position_pct": 0.30,
                  "max_slippage_bps": 100, "hard_drawdown_pct": 0.15}

MOMENTUM: dict[str, Any] = {
    "id": "yeaster-momentum",
    "name": "Yeaster Momentum",
    "thesis": "Finalized autonomous strategy — hunts breakouts & trending runners, decided by the bold "
              "lead AI, protected by native auto-brackets with a volatility-scaled trailing stop.",
    "stats": "Exit bracket re-tuned on 135-token real-OHLC backtest: ATR-3x trail + wide 40% backstop "
             "(the old fixed-3% trail clipped every winner; ATR scales the trail to each coin's volatility).",
    "detectors": MOMENTUM_DETECTORS,
    "score_dims": MOMENTUM_DIMS,
    "commit_arm": "llm_lead",
    "commit_style": "aggressive",
    "exit": MOMENTUM_EXIT,
    "guard": MOMENTUM_GUARD,
}


def active() -> dict[str, Any]:
    """The currently active strategy config (one finalized preset for now)."""
    return MOMENTUM
