"""Pure technical-indicator math — dependency-free, side-effect-free.

Used by the mock/computed market backend and any path that has raw closes but no
pre-computed technicals. Wilder's RSI, EMA, MACD. (Same proven math as the agent
has always used; isolated here so it can be unit-tested against canonical vectors.)
"""

from __future__ import annotations

from typing import Optional


def ema_series(values: list[float], period: int) -> list[float]:
    """EMA over the whole series (same length as input)."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


def ema(values: list[float], period: int) -> Optional[float]:
    """Latest EMA, or None if there is not enough data."""
    if len(values) < period:
        return None
    return ema_series(values, period)[-1]


def rsi(values: list[float], period: int = 14) -> Optional[float]:
    """Relative Strength Index (Wilder smoothing). 0-100, or None."""
    if len(values) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """MACD line / signal / histogram, or None if too short."""
    if len(values) < slow + signal:
        return None
    ema_fast = ema_series(values, fast)
    ema_slow = ema_series(values, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema_series(macd_line, signal)
    return {
        "macd": round(macd_line[-1], 6),
        "signal": round(signal_line[-1], 6),
        "histogram": round(macd_line[-1] - signal_line[-1], 6),
    }


def trend_label(price: float, ema_fast: Optional[float], ema_slow: Optional[float]) -> str:
    """Coarse trend from EMA stack: 'bullish' | 'bearish' | 'neutral'."""
    if ema_fast is None or ema_slow is None:
        return "neutral"
    if ema_fast > ema_slow and price >= ema_slow:
        return "bullish"
    if ema_fast < ema_slow and price <= ema_slow:
        return "bearish"
    return "neutral"
