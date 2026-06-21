"""Exit-bracket simulation on true intraday OHLC.

A long position is governed by three brackets, all modeled (not assumed):
  * **hard stop**     — ``entry * (1 - stop_pct)``
  * **take-profit**   — ``entry * (1 + tp_pct)``  (``tp_pct=0`` disables)
  * **trailing stop** — ratchets up under the running peak; trailing only ever
    *tightens* the effective stop, never loosens it.

Trailing supports three shapes (this is the lever the trailing study sweeps):
  * ``fixed``  — ``peak * (1 - trailing_pct)``
  * ``atr``    — ``peak - atr_k * ATR(period)`` (ATR fixed at entry; volatility-scaled)
  * **profit-armed** — for either shape, trailing only activates once price has
    reached ``entry * (1 + arm_pct)``; before that the hard stop governs (so
    entry noise can't clip the trade).

Intraday realism: brackets are checked against the bar's High/Low, the adverse
(stop/trail) side is checked **before** the favorable (TP) side, and gap opens
fill at the open — so a 3% trail getting shaken out by a normal pullback shows
up exactly as it would live.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import Bar


# ── volatility ───────────────────────────────────────────────────────────────


def atr(bars: list[Bar], period: int = 14) -> float:
    """Average True Range over the last ``period`` bars (absolute price units).
    Needs true O/H/L/C; 0.0 if there is not enough data."""
    if len(bars) < period + 1:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(bars)):
        h, low, pc = bars[i].high, bars[i].low, bars[i - 1].close
        trs.append(max(h - low, abs(h - pc), abs(low - pc)))
    window = trs[-period:]
    return sum(window) / len(window) if window else 0.0


# ── config + position ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExitConfig:
    stop_pct: float = 0.08
    tp_pct: float = 0.16
    trailing_pct: float = 0.03
    trailing_mode: str = "fixed"   # "fixed" | "atr"
    atr_k: float = 3.0             # trail distance = atr_k * ATR(atr_period)
    atr_period: int = 14
    arm_pct: float = 0.0           # profit-arm threshold; 0 = trail always on

    def label(self) -> str:
        if self.trailing_mode == "atr":
            trail = f"atr{self.atr_k:g}x"
        elif self.trailing_pct > 0:
            trail = f"trail{self.trailing_pct * 100:g}%"
        else:
            trail = "no-trail"
        arm = f"+arm{self.arm_pct * 100:g}%" if self.arm_pct > 0 else ""
        return f"stop{self.stop_pct * 100:g}%/tp{self.tp_pct * 100:g}%/{trail}{arm}"


@dataclass
class Position:
    symbol: str
    entry_ts: str
    entry_price: float
    notional: float                # USD at entry (cost basis, post-cost)
    peak: float = field(default=0.0)   # highest High seen since entry
    atr0: float = field(default=0.0)   # ATR at entry (for atr trailing)

    def __post_init__(self) -> None:
        if self.peak <= 0:
            self.peak = self.entry_price


@dataclass(frozen=True)
class ExitFill:
    exited: bool
    price: float
    reason: str   # "stop" | "trail" | "tp" | ""


_NO_EXIT = ExitFill(False, 0.0, "")


def check_exit(pos: Position, bar: Bar, cfg: ExitConfig) -> ExitFill:
    """Evaluate one day's bar against the brackets; mutates ``pos.peak``.

    Returns an :class:`ExitFill`; when ``exited`` is False the position rides on.
    """
    # Ratchet the peak on the day's high first (trailing references the peak).
    if bar.high > pos.peak:
        pos.peak = bar.high

    hard_stop = pos.entry_price * (1.0 - cfg.stop_pct)

    # Trailing stop — only when armed, and only if it tightens above the hard stop.
    trail_stop = 0.0
    armed = cfg.arm_pct <= 0.0 or pos.peak >= pos.entry_price * (1.0 + cfg.arm_pct)
    if armed:
        if cfg.trailing_mode == "atr" and pos.atr0 > 0 and cfg.atr_k > 0:
            trail_stop = pos.peak - cfg.atr_k * pos.atr0
        elif cfg.trailing_mode == "fixed" and cfg.trailing_pct > 0:
            trail_stop = pos.peak * (1.0 - cfg.trailing_pct)

    effective_stop = max(hard_stop, trail_stop)
    stop_reason = "trail" if trail_stop > hard_stop else "stop"

    tp = pos.entry_price * (1.0 + cfg.tp_pct) if cfg.tp_pct > 0 else None

    # Adverse side first (pessimistic): a gap-open below the stop fills at the open.
    if bar.open <= effective_stop:
        return ExitFill(True, bar.open, stop_reason)
    if bar.low <= effective_stop:
        return ExitFill(True, effective_stop, stop_reason)

    # Favorable side: gap-open above TP fills at the open.
    if tp is not None:
        if bar.open >= tp:
            return ExitFill(True, bar.open, "tp")
        if bar.high >= tp:
            return ExitFill(True, tp, "tp")

    return _NO_EXIT
