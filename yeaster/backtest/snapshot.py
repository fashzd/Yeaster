"""Bridge bars → the inputs ``brain/screen.py`` expects.

The live SCREEN stage consumes a ``live`` snapshot map and a ``hist`` daily panel:

    live : {SYM: {price, volume, pct_24h, pct_7d}}
    hist : {SYM: [{price, volume}, ...]}     # oldest -> newest daily bars

Here we reconstruct both *point-in-time* from OHLC bars dated ``<= t``, so the
real, unmodified detectors in ``screen.deterministic()`` run against history with
no lookahead. Only close + volume + day/week returns are derived — all
OHLCV-reconstructible, all honest.
"""

from __future__ import annotations

from .data import Bar


def _pct(curr: float, prev: float) -> float | None:
    if prev and prev > 0:
        return (curr / prev - 1.0) * 100.0
    return None


def reconstruct(panel: dict[str, list[Bar]]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Build (live, hist) for ``screen.deterministic`` from per-symbol bars ≤ t.

    ``panel`` maps each symbol to its bars up to and including the decision date,
    oldest first. Symbols with no bars are skipped.
    """
    live: dict[str, dict] = {}
    hist: dict[str, list[dict]] = {}
    for sym, bars in panel.items():
        if not bars:
            continue
        closes = [b.close for b in bars]
        last = bars[-1]
        prev_24h = closes[-2] if len(closes) >= 2 else 0.0
        prev_7d = closes[-8] if len(closes) >= 8 else 0.0
        live[sym] = {
            "price": last.close,
            "volume": last.volume,
            "pct_24h": _pct(last.close, prev_24h),
            "pct_7d": _pct(last.close, prev_7d),
        }
        hist[sym] = [{"price": b.close, "volume": b.volume} for b in bars]
    return live, hist
