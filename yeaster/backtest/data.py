"""Price-data layer: real CMC daily OHLC, cached to CSV for fast, reproducible,
point-in-time-honest backtests.

* :class:`Bar` — one daily OHLCV bar (``ts`` is ``YYYY-MM-DD``, which sorts and
  range-compares lexicographically).
* :func:`fetch_cmc_ohlcv` — pull true daily O/H/L/C/V from the CMC Data API
  (``/v2/cryptocurrency/ohlcv/historical``). Requires ``CMC_API_KEY``.
* :class:`CachedSource` — reads cached ``<SYM>.csv`` files; ``get_bars(sym, end=t)``
  returns only bars dated ``<= t`` so the engine can never see the future.
* :func:`pull_universe` — fetch + cache the whole tradeable whitelist.

The CMC client here serves **OHLCV only**. The live CMC analytics (whale/perp/
sentiment/…) live in ``market/skills.py`` and are never imported here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

REST_BASE = "https://pro-api.coinmarketcap.com"
OHLCV_PATH = "/v2/cryptocurrency/ohlcv/historical"
HTTP_TIMEOUT = 30

# Runtime cache (gitignored). Sits under the repo's data/ dir.
_REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = _REPO_ROOT / "data" / "backtests" / "ohlcv"

CSV_HEADER = ("date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True, slots=True)
class Bar:
    """One daily OHLCV bar. ``ts`` is an ISO date string ``YYYY-MM-DD``."""

    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ── CMC fetch ────────────────────────────────────────────────────────────────


def _parse_ohlcv(payload: dict, symbol: str) -> list[Bar]:
    """Normalize the CMC v2 OHLCV response into sorted :class:`Bar` s.

    The response nests as ``data[SYM]`` which may be a list (``[{quotes: [...]}]``)
    or a dict (``{quotes: [...]}``); each quote carries ``quote.USD.{open,high,
    low,close,volume}`` and a ``time_open`` timestamp.
    """
    data = payload.get("data") or {}
    entry = data.get(symbol.upper())
    if entry is None and isinstance(data, dict):
        entry = data.get("quotes") and data or next(iter(data.values()), None)
    if isinstance(entry, list):
        entry = entry[0] if entry else None
    quotes = (entry or {}).get("quotes", []) if isinstance(entry, dict) else []

    bars: list[Bar] = []
    for q in quotes:
        usd = (q.get("quote") or {}).get("USD") or {}
        ts = (q.get("time_open") or usd.get("timestamp") or "")[:10]
        if not ts:
            continue
        try:
            bars.append(Bar(
                ts=ts,
                open=float(usd.get("open") or 0.0),
                high=float(usd.get("high") or 0.0),
                low=float(usd.get("low") or 0.0),
                close=float(usd.get("close") or 0.0),
                volume=float(usd.get("volume") or 0.0),
            ))
        except (TypeError, ValueError):
            continue
    bars.sort(key=lambda b: b.ts)
    return bars


def fetch_cmc_ohlcv(symbol: str, api_key: str, *, count: int = 400,
                    start: Optional[str] = None, end: Optional[str] = None) -> list[Bar]:
    """Fetch daily OHLC bars for ``symbol`` from the CMC Data API."""
    params: dict[str, object] = {"symbol": symbol.upper(), "interval": "daily"}
    if start or end:
        if start:
            params["time_start"] = start
        if end:
            params["time_end"] = end
    else:
        params["count"] = count
    resp = requests.get(
        REST_BASE + OHLCV_PATH,
        headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
        params=params, timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_ohlcv(resp.json(), symbol)


# ── CSV cache ────────────────────────────────────────────────────────────────


def save_csv(symbol: str, bars: list[Bar], cache_dir: Path = CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol.upper()}.csv"
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_HEADER)
        for b in bars:
            w.writerow([b.ts, b.open, b.high, b.low, b.close, b.volume])
    return path


def load_csv(symbol: str, cache_dir: Path = CACHE_DIR) -> list[Bar]:
    path = cache_dir / f"{symbol.upper()}.csv"
    if not path.is_file():
        return []
    bars: list[Bar] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            bars.append(Bar(
                ts=row["date"], open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]), volume=float(row["volume"]),
            ))
    bars.sort(key=lambda b: b.ts)
    return bars


class CachedSource:
    """A point-in-time price source over the CSV cache.

    ``get_bars(sym, end=t)`` returns bars dated ``<= t`` only — the engine relies
    on this to stay honest (no lookahead).
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self._cache: dict[str, list[Bar]] = {}

    def symbols(self) -> list[str]:
        if not self.cache_dir.is_dir():
            return []
        return sorted(p.stem.upper() for p in self.cache_dir.glob("*.csv"))

    def _all(self, symbol: str) -> list[Bar]:
        sym = symbol.upper()
        if sym not in self._cache:
            self._cache[sym] = load_csv(sym, self.cache_dir)
        return self._cache[sym]

    def get_bars(self, symbol: str, start: Optional[str] = None,
                 end: Optional[str] = None) -> list[Bar]:
        bars = self._all(symbol)
        if start is not None:
            bars = [b for b in bars if b.ts >= start]
        if end is not None:
            bars = [b for b in bars if b.ts <= end]
        return bars


# ── bulk pull ────────────────────────────────────────────────────────────────


def pull_universe(symbols: list[str], api_key: str, *, count: int = 400,
                  cache_dir: Path = CACHE_DIR, log=print) -> dict[str, int]:
    """Fetch + cache OHLC for each symbol. Returns {SYM: n_bars}. Failures are
    logged and recorded as 0 rather than aborting the whole pull."""
    out: dict[str, int] = {}
    for sym in symbols:
        try:
            bars = fetch_cmc_ohlcv(sym, api_key, count=count)
            if bars:
                save_csv(sym, bars, cache_dir)
            out[sym] = len(bars)
            if log:
                span = f"{bars[0].ts}->{bars[-1].ts}" if bars else "no data"
                log(f"  {sym:<8} {len(bars):>4} bars  {span}")
        except Exception as exc:  # noqa: BLE001 — report and continue the pull
            out[sym] = 0
            if log:
                log(f"  {sym:<8} FAILED: {exc}")
    return out
