"""Walk-forward, point-in-time backtest engine.

Replays the **real** SCREEN detectors (``brain/screen.deterministic``) and the
**real** sizing rails (``brain/commit.size_amount_pct``) over historical daily
OHLC. Each day:

  1. fill any entry decided yesterday at today's OPEN (no lookahead),
  2. evaluate exit brackets against today's intraday High/Low,
  3. mark the book to today's close and update drawdown,
  4. decide tomorrow's entry from bars dated ``<= today`` only.

Entries use only OHLCV-reconstructible signals (deterministic SCREEN + local
indicators). The live GRADE composite and the live CMC skill dimensions are
**out of scope by construction** — never imported, never called.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Optional, Protocol

from yeaster.brain.commit import DD_HALT, size_amount_pct
from yeaster.brain.screen import deterministic
from yeaster.core.preset import active
from yeaster.core.universe import is_whitelisted
from yeaster.market import indicators as ind

from .data import Bar
from .exits import ExitConfig, ExitFill, Position, atr, check_exit
from .metrics import Metrics, summarize
from .snapshot import reconstruct

# SCREEN detectors that are OHLCV-reconstructible. ``scanner_spot`` (from the
# finalized preset) is a live CMC skill, NOT an OHLCV detector → excluded for honesty.
OHLCV_DETECTORS = ("rel_strength", "breakout", "extended_runner", "vol_surge",
                   "accumulation", "mean_revert")

# How many trailing daily bars to feed the detectors (they look back <= 50).
_HIST_WINDOW = 60


class Source(Protocol):
    def symbols(self) -> list[str]: ...
    def get_bars(self, symbol: str, start: Optional[str] = None,
                 end: Optional[str] = None) -> list[Bar]: ...


@dataclass(frozen=True)
class BacktestConfig:
    universe: Optional[list[str]] = None
    start: Optional[str] = None
    end: Optional[str] = None
    exit: Optional[ExitConfig] = None      # None → from the finalized preset
    detectors: Optional[list[str]] = None  # None → OHLCV_DETECTORS
    fee_bps: float = 25.0
    slippage_bps: float = 25.0
    max_open_positions: int = 5
    starting_equity: float = 10_000.0
    warmup_bars: int = 30                  # need history before the first decision


@dataclass
class BacktestResult:
    metrics: Metrics
    equity_curve: list[tuple[str, float]]
    trades: list[dict]
    config: dict
    exit_label: str
    n_days: int
    universe_size: int
    date_range: tuple[str, str]
    extra: dict = field(default_factory=dict)


def preset_exit() -> ExitConfig:
    """Build an :class:`ExitConfig` from the live finalized preset bracket."""
    ex = active()["exit"]
    return ExitConfig(stop_pct=ex["stop_pct"], tp_pct=ex["tp_pct"],
                      trailing_pct=ex["trailing_pct"], trailing_mode="fixed")


def _conviction(tags: list[str], closes: list[float]) -> float:
    """OHLCV-only conviction in [0,1] from detector agreement + local technicals.

    This is the honest stand-in for the live GRADE composite — which leans ~85%
    on un-backtestable live CMC dimensions and therefore cannot appear here.
    """
    conv = 0.25 + 0.12 * min(len(tags), 4)
    ema_fast = ind.ema(closes, 12)
    ema_slow = ind.ema(closes, 26)
    trend = ind.trend_label(closes[-1], ema_fast, ema_slow)
    if trend == "bullish":
        conv += 0.12
    elif trend == "bearish":
        conv -= 0.12
    r = ind.rsi(closes, 14)
    if r is not None:
        if 50.0 <= r <= 72.0:
            conv += 0.10
        elif r > 80.0:
            conv -= 0.15
    if len(closes) >= 8 and closes[-8] > 0 and (closes[-1] / closes[-8] - 1.0) > 0:
        conv += 0.06
    return max(0.0, min(1.0, conv))


def run_backtest(source: Source, config: BacktestConfig) -> BacktestResult:
    cfg = config
    exit_cfg = cfg.exit or preset_exit()
    detectors = set(cfg.detectors or OHLCV_DETECTORS)
    cost = (cfg.fee_bps + cfg.slippage_bps) / 10_000.0

    # Universe: requested or everything cached, restricted to the whitelist.
    syms = [s.upper() for s in (cfg.universe or source.symbols()) if is_whitelisted(s)]
    wl = set(syms)

    # Pre-load bars per symbol with a date index for O(log n) point-in-time slicing.
    bars_by: dict[str, list[Bar]] = {}
    ts_by: dict[str, list[str]] = {}
    all_dates: set[str] = set()
    for s in syms:
        b = source.get_bars(s, start=None, end=cfg.end)
        if not b:
            continue
        bars_by[s] = b
        ts_by[s] = [x.ts for x in b]
        all_dates.update(ts_by[s])

    axis = sorted(d for d in all_dates if (cfg.start is None or d >= cfg.start))
    if not axis:
        empty = summarize([], [], cfg.starting_equity)
        return BacktestResult(empty, [], [], _config_dict(cfg, cost), exit_cfg.label(),
                              0, len(bars_by), ("", ""))

    def bars_upto(sym: str, t: str) -> list[Bar]:
        idx = bisect_right(ts_by[sym], t)
        return bars_by[sym][:idx]

    def bar_on(sym: str, t: str) -> Optional[Bar]:
        lst = ts_by.get(sym)
        if not lst:
            return None
        idx = bisect_right(lst, t)
        if idx and lst[idx - 1] == t:
            return bars_by[sym][idx - 1]
        return None

    cash = cfg.starting_equity
    positions: dict[str, Position] = {}
    pending: Optional[tuple[str, float, float]] = None  # (symbol, notional, conviction)
    equity_curve: list[tuple[str, float]] = []
    trades: list[dict] = []
    trade_pnls: list[float] = []
    peak_equity = cfg.starting_equity

    for t in axis:
        # 1) Fill yesterday's decision at today's open.
        if pending is not None:
            sym, notional, conv = pending
            pending = None
            b = bar_on(sym, t)
            if b is not None and b.open > 0 and notional > 0 and sym not in positions:
                entry_fill = b.open * (1.0 + cost)
                positions[sym] = Position(
                    symbol=sym, entry_ts=t, entry_price=entry_fill, notional=notional,
                    atr0=atr(bars_upto(sym, t)[:-1] or bars_upto(sym, t), exit_cfg.atr_period),
                )
                cash -= notional

        # 2) Exits on today's bar.
        for sym in list(positions.keys()):
            pos = positions[sym]
            b = bar_on(sym, t)
            if b is None:
                continue
            fill: ExitFill = check_exit(pos, b, exit_cfg)
            if fill.exited:
                qty = pos.notional / pos.entry_price
                proceeds = qty * fill.price * (1.0 - cost)
                cash += proceeds
                pnl = proceeds / pos.notional - 1.0
                trade_pnls.append(pnl)
                trades.append({
                    "symbol": sym, "entry_ts": pos.entry_ts, "exit_ts": t,
                    "entry": round(pos.entry_price, 8), "exit": round(fill.price, 8),
                    "reason": fill.reason, "pnl_pct": round(pnl * 100, 3),
                    "notional": round(pos.notional, 2),
                })
                del positions[sym]

        # 3) Mark to close + drawdown.
        mark = 0.0
        for sym, pos in positions.items():
            b = bar_on(sym, t)
            px = b.close if b is not None else pos.entry_price
            mark += (pos.notional / pos.entry_price) * px
        equity = cash + mark
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
        equity_curve.append((t, round(equity, 2)))

        # 4) Decide tomorrow's entry (point-in-time: bars <= t only).
        if pending is None and drawdown < DD_HALT and len(positions) < cfg.max_open_positions:
            panel = {s: bars_upto(s, t)[-_HIST_WINDOW:] for s in syms if ts_by.get(s)}
            live, hist = reconstruct(panel)
            hits = deterministic(live, hist, wl, enabled=detectors)
            ranked: list[tuple[float, str]] = []
            for s, tags in hits.items():
                if s in positions or not tags:
                    continue
                closes = [x["price"] for x in hist.get(s, [])]
                if len(closes) < 2:
                    continue
                ranked.append((_conviction(tags, closes), s))
            ranked.sort(key=lambda x: (-x[0], x[1]))
            if ranked:
                conv, sym = ranked[0]
                amount_pct = size_amount_pct(conv, equity, drawdown)
                if amount_pct and amount_pct > 0:
                    notional = min(amount_pct * equity, cash)
                    if notional > 0:
                        pending = (sym, notional, conv)

    # Close any open positions at the last close (mark-out).
    last_t = axis[-1]
    for sym in list(positions.keys()):
        pos = positions[sym]
        b = bar_on(sym, last_t) or (bars_upto(sym, last_t)[-1] if bars_upto(sym, last_t) else None)
        if b is None:
            continue
        qty = pos.notional / pos.entry_price
        proceeds = qty * b.close * (1.0 - cost)
        cash += proceeds
        pnl = proceeds / pos.notional - 1.0
        trade_pnls.append(pnl)
        trades.append({
            "symbol": sym, "entry_ts": pos.entry_ts, "exit_ts": last_t,
            "entry": round(pos.entry_price, 8), "exit": round(b.close, 8),
            "reason": "mark_out", "pnl_pct": round(pnl * 100, 3), "notional": round(pos.notional, 2),
        })
        del positions[sym]
    if positions:  # all closed above; recompute final equity as pure cash
        pass
    equity_curve[-1] = (last_t, round(cash, 2))

    eq_values = [e for _, e in equity_curve]
    metrics = summarize(eq_values, trade_pnls, cfg.starting_equity)
    return BacktestResult(
        metrics=metrics, equity_curve=equity_curve, trades=trades,
        config=_config_dict(cfg, cost), exit_label=exit_cfg.label(),
        n_days=len(axis), universe_size=len(bars_by), date_range=(axis[0], axis[-1]),
    )


def _config_dict(cfg: BacktestConfig, cost: float) -> dict:
    return {
        "fee_bps": cfg.fee_bps, "slippage_bps": cfg.slippage_bps, "round_trip_cost_pct": round(cost * 200, 4),
        "max_open_positions": cfg.max_open_positions, "starting_equity": cfg.starting_equity,
        "detectors": sorted(cfg.detectors or OHLCV_DETECTORS), "warmup_bars": cfg.warmup_bars,
        "start": cfg.start, "end": cfg.end,
    }
