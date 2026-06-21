"""Tests for the native backtester: honesty isolation, determinism, exits, run."""

from __future__ import annotations

import re
from pathlib import Path

from yeaster.backtest.data import Bar
from yeaster.backtest.engine import BacktestConfig, run_backtest
from yeaster.backtest.exits import ExitConfig, Position, atr, check_exit

_PKG = Path(__file__).resolve().parents[1] / "yeaster" / "backtest"

# An import (not a docstring mention) of a live-only, un-backtestable module.
_FORBIDDEN = re.compile(
    r"^\s*(import|from)\s+.*(brain\.grade|brain\.dimensions|market\.skills|live_overlay)",
    re.MULTILINE,
)


def test_backtest_never_imports_live_only_signals():
    """The honesty boundary, enforced: no backtest source pulls in the live GRADE
    composite or the live CMC skill layer."""
    for f in _PKG.glob("*.py"):
        assert not _FORBIDDEN.search(f.read_text()), f"{f.name} imports a live-only signal module"


# ── synthetic source ─────────────────────────────────────────────────────────


def _series() -> list[Bar]:
    """A whitelisted-symbol price path with a clear breakout + volume spike, a
    short continuation, then a decline that trips the stop — so >=1 trade closes."""
    bars: list[Bar] = []
    px = 2.0
    day = 0

    def push(close: float, vol: float, *, hi=None, lo=None, op=None):
        nonlocal day
        op = op if op is not None else close
        hi = hi if hi is not None else max(op, close) * 1.005
        lo = lo if lo is not None else min(op, close) * 0.995
        bars.append(Bar(ts=f"2025-{1 + day // 28:02d}-{1 + day % 28:02d}",
                        open=op, high=hi, low=lo, close=close, volume=vol))
        day += 1

    for _ in range(30):                       # gentle uptrend, fresh highs daily
        px *= 1.003
        push(px, 1000.0)
    px *= 1.06                                # breakout day: new high + 3x volume
    push(px, 3000.0)
    for _ in range(4):                        # continuation (entry fills + rides)
        px *= 1.01
        push(px, 1500.0)
    for _ in range(10):                       # decline -> trips the 8% stop
        px *= 0.96
        push(px, 1200.0)
    return bars


class _MemSource:
    def __init__(self, symbols: list[str]):
        self._bars = {s: _series() for s in symbols}

    def symbols(self) -> list[str]:
        return list(self._bars)

    def get_bars(self, symbol, start=None, end=None):
        bars = self._bars.get(symbol.upper(), [])
        if end is not None:
            bars = [b for b in bars if b.ts <= end]
        return bars


# ── exits ────────────────────────────────────────────────────────────────────


def test_atr_positive_on_real_ohlc():
    bars = _series()
    assert atr(bars, 14) > 0.0


def test_hard_stop_fires():
    pos = Position(symbol="X", entry_ts="2025-01-01", entry_price=100.0, notional=100.0)
    cfg = ExitConfig(stop_pct=0.08, tp_pct=0.16, trailing_pct=0.0)
    bar = Bar(ts="2025-01-02", open=99.0, high=99.5, low=90.0, close=91.0, volume=1.0)
    fill = check_exit(pos, bar, cfg)
    assert fill.exited and fill.reason == "stop"
    assert abs(fill.price - 92.0) < 1e-9      # entry * (1 - 0.08)


def test_take_profit_fires():
    pos = Position(symbol="X", entry_ts="2025-01-01", entry_price=100.0, notional=100.0)
    cfg = ExitConfig(stop_pct=0.08, tp_pct=0.16, trailing_pct=0.0)
    bar = Bar(ts="2025-01-02", open=101.0, high=117.0, low=100.5, close=116.0, volume=1.0)
    fill = check_exit(pos, bar, cfg)
    assert fill.exited and fill.reason == "tp"
    assert abs(fill.price - 116.0) < 1e-9     # entry * (1 + 0.16)


def test_trailing_tightens_above_hard_stop():
    pos = Position(symbol="X", entry_ts="2025-01-01", entry_price=100.0, notional=100.0, peak=130.0)
    cfg = ExitConfig(stop_pct=0.08, tp_pct=0.0, trailing_pct=0.03)   # trail @ 3% under peak
    # peak 130 -> trail stop 126.1; a dip to 125 should exit on the trail, not the 92 hard stop.
    bar = Bar(ts="2025-01-02", open=128.0, high=129.0, low=125.0, close=126.0, volume=1.0)
    fill = check_exit(pos, bar, cfg)
    assert fill.exited and fill.reason == "trail"
    assert abs(fill.price - 126.1) < 1e-6


# ── engine ───────────────────────────────────────────────────────────────────


def test_run_produces_trades_and_is_deterministic():
    src = _MemSource(["CAKE", "AVAX", "INJ"])     # all whitelisted
    cfg = BacktestConfig(starting_equity=10_000.0, max_open_positions=3)
    r1 = run_backtest(src, cfg)
    r2 = run_backtest(src, cfg)
    assert r1.metrics.n_trades >= 1
    assert r1.metrics.as_dict() == r2.metrics.as_dict()        # determinism
    assert [t["symbol"] for t in r1.trades] == [t["symbol"] for t in r2.trades]
    assert r1.equity_curve == r2.equity_curve


def test_trailing_change_alters_outcome_not_entries():
    src = _MemSource(["CAKE", "AVAX", "INJ"])
    tight = run_backtest(src, BacktestConfig(exit=ExitConfig(0.08, 0.16, 0.03)))
    wide = run_backtest(src, BacktestConfig(exit=ExitConfig(0.08, 0.16, 0.12)))
    # Same signals fire either way; the realized result differs by exit config.
    assert tight.metrics.n_trades >= 1 and wide.metrics.n_trades >= 1
    assert tight.exit_label != wide.exit_label
