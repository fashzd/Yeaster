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
# 3.5% sizing risk-divisor): wide stop, wider target, trailing ratchet.
MOMENTUM_EXIT = {"stop_pct": 0.08, "tp_pct": 0.16, "trailing_pct": 0.03}

# Firewall rails.
MOMENTUM_GUARD = {"max_trade_pct": 0.12, "max_position_pct": 0.30,
                  "max_slippage_bps": 100, "hard_drawdown_pct": 0.15}

MOMENTUM: dict[str, Any] = {
    "id": "yeaster-momentum",
    "name": "Yeaster Momentum",
    "thesis": "Finalized autonomous strategy — hunts breakouts & trending runners, decided by the bold "
              "lead AI, protected by native auto-brackets.",
    "stats": "Runner edge backtested +41.6%/30d (67% win, 1-yr walk-forward).",
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
