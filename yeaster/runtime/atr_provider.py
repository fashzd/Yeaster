"""Runtime ATR provider — the live agent's volatility yardstick at entry.

The live tick only carries latest quotes (no daily high/low), so to size a
volatility-scaled trailing stop we read each coin's recent daily OHLC at the
moment of entry and compute ATR(14). Reuses the backtester's proven pieces:

  * ``backtest.data.fetch_cmc_ohlcv`` — real daily OHLC from CMC (live freshness),
  * ``backtest.data.load_csv``        — the cached panel (offline / paper / tests),
  * ``backtest.exits.atr``            — the ATR(14) computation.

Always returns a float; ``0.0`` signals "no usable ATR" so the caller falls back
to the fixed-% trail and never leaves a position un-trailed.
"""

from __future__ import annotations

from yeaster.backtest.data import fetch_cmc_ohlcv, load_csv, save_csv
from yeaster.backtest.exits import atr
from yeaster.core.settings import get_settings


def atr_at_entry(symbol: str, period: int = 14) -> float:
    """ATR(period) for ``symbol`` in its own price units. Prefers a fresh CMC pull
    when a key is configured (live); falls back to the cached CSV panel; ``0.0``
    when neither yields enough history."""
    sym = symbol.upper()
    need = period + 1
    bars: list = []

    key = get_settings().cmc_api_key
    if key:
        try:
            fetched = fetch_cmc_ohlcv(sym, key, count=max(60, need))
            if fetched:
                save_csv(sym, fetched)  # refresh the cache for next time
                bars = fetched
        except Exception:               # network/plan hiccup → fall back to cache
            bars = []

    if len(bars) < need:
        bars = load_csv(sym)            # offline path (paper / tests / no key)

    return atr(bars, period) if len(bars) >= need else 0.0
