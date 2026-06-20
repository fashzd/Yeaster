"""SCREEN — the first reasoning pass: scout the market for candidates.

Fuses several INDEPENDENT detectors, each surfacing coins a different way, into
one tagged shortlist. A coin hit by multiple detectors ranks higher (cross-source
agreement). Deterministic detectors run over the daily panel + live snapshot;
skill detectors make one market-wide call each. (Proven detector logic, ported.)
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict
from typing import Any, Optional

from yeaster.core.universe import STABLES, is_tradeable
from yeaster.market import skills


def _median(xs: list[float]) -> float:
    return st.median(xs) if xs else 0.0


def _filter_enabled(hits: dict[str, list[str]], enabled: Optional[set[str]]) -> dict[str, list[str]]:
    if enabled is None:
        return hits
    en = {str(x) for x in enabled}
    return {s: [t for t in tags if t in en] for s, tags in hits.items() if any(t in en for t in tags)}


def deterministic(live: dict[str, dict], hist: dict[str, list[dict]],
                  wl: set[str], enabled: Optional[set[str]] = None) -> dict[str, list[str]]:
    """live: {SYM: {price, volume, pct_24h, pct_7d}}; hist: {SYM: [daily bars]}."""
    hits: dict[str, list[str]] = defaultdict(list)
    chgs = [b["pct_24h"] for s, b in live.items()
            if s in wl and is_tradeable(s) and b.get("pct_24h") is not None]
    med = _median(chgs)

    # 1) relative strength / decoupling — leads the median, real but not blown
    for s, b in live.items():
        if s not in wl or not is_tradeable(s):
            continue
        c24, c7 = b.get("pct_24h"), b.get("pct_7d")
        if c24 is not None and (c24 - med) >= 5.0 and c24 < 25.0 and (c7 or 0) > 0:
            hits[s].append("rel_strength")

    # structural detectors (need ~25 daily bars)
    for s, bars in hist.items():
        if s not in wl or not is_tradeable(s) or len(bars) < 25:
            continue
        closes = [x["price"] for x in bars]
        vols = [x["volume"] for x in bars]
        price = closes[-1]
        hi20 = max(closes[-21:-1])
        lo20 = min(closes[-21:-1])
        sma20 = sum(closes[-20:]) / 20
        sd = st.pstdev(closes[-20:]) or 0.0
        avgvol = (sum(vols[-21:-1]) / 20) or 1.0
        c24 = (live.get(s) or {}).get("pct_24h") or 0.0

        if price > hi20 and vols[-1] >= 2 * avgvol and c24 < 25:
            hits[s].append("breakout")
        rng = (hi20 - lo20) / lo20 if lo20 > 0 else 9
        if rng < 0.25 and 0.90 * hi20 <= price <= hi20 and vols[-1] > 1.2 * avgvol and c24 < 10:
            hits[s].append("accumulation")
        if sd > 0 and (price - sma20) / sd <= -2.0:
            hits[s].append("mean_revert")
        if vols[-1] >= 3 * avgvol:
            hits[s].append("vol_surge")

        # extended runner — strong DISTRIBUTED uptrend riding highs, NOT parabolic
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sum(closes) / len(closes)
        r7 = closes[-1] / closes[-8] - 1 if closes[-8] > 0 else 0.0
        ddays = [closes[-i] / closes[-i - 1] - 1 for i in range(1, 8) if closes[-i - 1] > 0]
        up_sum = sum(d for d in ddays if d > 0) or 1e-9
        conc = (max(ddays) / up_sum) if ddays else 0.0
        px_sma = price / sma20 if sma20 > 0 else 0.0
        sigma = (price - sma20) / sd if sd > 0 else 0.0
        parabolic = px_sma >= 1.40 or sigma >= 2.5 or conc >= 0.60
        if price > sma20 > sma50 and r7 >= 0.30 and price >= 0.92 * hi20 and not parabolic:
            hits[s].append("extended_runner")

    return _filter_enabled(hits, enabled)


def skill_detectors(wl: set[str], enabled: Optional[set[str]] = None) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = defaultdict(list)
    if not skills.available():
        return hits
    want_scanner = enabled is None or "scanner_spot" in {str(x) for x in enabled}
    want_overview = enabled is None or any(str(x).startswith("overview") for x in enabled)
    if want_scanner:
        for c in skills.scan_breakouts(wl, top_n=8):
            hits[c["symbol"]].append("scanner_spot")
    if want_overview:
        for c in skills.overview_candidates(wl):
            hits[c["symbol"]].append(c["lane"])
    return _filter_enabled(hits, enabled)


def screen(live: dict[str, dict], hist: dict[str, list[dict]], universe,
           enabled: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """Return ranked candidates [{symbol, tags, score}] — multi-tagged rank highest."""
    wl = {s.upper() for s in universe}
    merged: dict[str, set] = defaultdict(set)
    for d in (deterministic(live, hist, wl, enabled), skill_detectors(wl, enabled)):
        for s, tags in d.items():
            merged[s].update(tags)
    out = [{"symbol": s, "tags": sorted(t), "score": len(t)} for s, t in merged.items() if s in wl]
    out.sort(key=lambda x: (-x["score"], x["symbol"]))
    return out


def live_map(snapshot) -> dict[str, dict]:
    """Build the SCREEN ``live`` map from a MarketSnapshot."""
    return {a.symbol.upper(): {"price": float(a.price_usd or 0), "volume": float(a.volume_24h_usd or 0),
                               "pct_24h": a.percent_change_24h, "pct_7d": a.percent_change_7d}
            for a in snapshot.assets if (a.price_usd or 0) > 0}
