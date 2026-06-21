"""Yeaster Backtest — a native, point-in-time walk-forward harness.

This package is **additive and isolated**: it READS the live brain (SCREEN
detectors, sizing rails, the finalized preset, local indicators, the universe)
and replays it over historical daily OHLC. It never touches the live trading
path, and — by construction — it only uses **OHLCV-reconstructible** signals.

Honesty boundary: the live GRADE composite (``brain/grade.py`` + the live CMC
skill dimensions in ``market/skills.py``) is **out of scope** — those signals
cannot be reconstructed from bars, so they never enter a backtest. What this
harness can legitimately calibrate is the entry SCREEN and, above all, the
**exit bracket** (stop / take-profit / trailing), which is signal-agnostic
price logic. The trailing-stop question lives entirely inside that boundary.
"""

from __future__ import annotations

from .data import Bar, CachedSource, fetch_cmc_ohlcv, pull_universe
from .engine import BacktestConfig, BacktestResult, run_backtest
from .metrics import Metrics, summarize

__all__ = [
    "Bar",
    "CachedSource",
    "fetch_cmc_ohlcv",
    "pull_universe",
    "BacktestConfig",
    "BacktestResult",
    "run_backtest",
    "Metrics",
    "summarize",
]
