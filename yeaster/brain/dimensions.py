"""Grade dimensions — uniform skill-backed signal wrappers.

Each returns ``{"score": float in [-1,1] | None, "coverage": 0|1, "flags": [...],
"evidence": {...}}``. ``score=None`` / ``coverage=0`` means NO DATA — the grader
treats it as MISSING, never as a negative. (Proven scoring logic, ported.)
"""

from __future__ import annotations

import re
from typing import Any

from yeaster.market.skills import _data, call_skill


def pack(score, coverage, flags=None, **evidence):
    return {"score": score, "coverage": coverage, "flags": flags or [], "evidence": evidence}


def _concl(d: dict) -> str:
    dr = d.get("decision_report") or d.get("report") or {}
    if not isinstance(dr, dict):
        return ""
    return (str(dr.get("conclusion", "")) + " " + str(dr.get("analysis", ""))).lower()


def _trend_sign(t: Any) -> float:
    t = str(t or "").lower()
    return 1.0 if "up" in t else -1.0 if "down" in t else 0.0


def _bull_bear(s: Any) -> float:
    s = str(s or "").lower()
    if any(w in s for w in ("bull", "up", "long")):
        return 1.0
    if any(w in s for w in ("bear", "down", "short")):
        return -1.0
    return 0.0


# ── transition (routed by candidate kind — the SIREN fix) ────────────────────

_TRANSITION_SCORE = {"breaking_out": 0.8, "warming": 0.6, "dormant": 0.0,
                     "overextended": -0.7, "failing": -0.8}


def transition_dim(symbol: str, kind: str) -> dict[str, Any]:
    from yeaster.market.skills import transition
    t = transition(symbol)
    state = t.get("state")
    if not state:
        return pack(None, 0, state=None, error=t.get("error"))
    sc = _TRANSITION_SCORE.get(state, 0.0)
    # mean-reversion candidates are not punished by breakout-trap states
    if kind == "mean_revert" and state in ("overextended", "failing"):
        sc = 0.0
    return pack(sc, 1, state=state, distance_to_high_pct=t.get("distance_to_high_pct"), vol_ratio=t.get("vol_ratio"))


# ── kline structure ──────────────────────────────────────────────────────────


def kline_quality(symbol: str, interval: str = "4h") -> dict[str, Any]:
    try:
        d = _data(call_skill("classify_kline_pattern_quality", {"symbol": symbol, "interval": interval}))
    except Exception:
        d = {}
    rep = d.get("report") or {}
    if not rep:
        try:
            d2 = _data(call_skill("kline_pattern_recognition", {"symbol": symbol, "interval": interval}))
            bias = str((d2.get("action_guidance") or {}).get("bias") or "").lower()
        except Exception:
            bias = ""
        if not bias or bias == "none":
            return pack(None, 0, signal=bias or None)
        s = 0.6 if any(w in bias for w in ("bull", "up")) else -0.6 if any(w in bias for w in ("bear", "down")) else 0.0
        return pack(s, 1, signal=bias, source="kline_pattern_recognition")

    tc = rep.get("trend_context") or {}
    sct = rep.get("short_term_context") or {}
    ts = rep.get("technical_structure") or {}
    lp = rep.get("latest_pattern") or {}
    htf = ((rep.get("multi_timeframe") or {}).get("higher_tf") or {}).get("trend_context") or {}
    dv = rep.get("divergence") or {}

    try:
        mag = min(1.0, 0.5 + 2.0 * float(tc.get("structure_score"))) if tc.get("structure_score") is not None else 0.6
    except Exception:
        mag = 0.6
    comps: list[tuple[float, float]] = [
        (_trend_sign(tc.get("trend")) * mag, 1.0),
        (_bull_bear(tc.get("ema_alignment")), 0.8),
        (_bull_bear(ts.get("bias")), 0.8),
        (_trend_sign(sct.get("trend")), 0.5),
        (_bull_bear(sct.get("ema_alignment")), 0.4),
        (_trend_sign(htf.get("trend")), 0.7),
    ]
    dval = 0.0
    det = dv.get("detected") or []
    if det:
        typ = str(det[0].get("type", "")).lower()
        try:
            sc = min(1.0, float(det[0].get("strength")) / 100.0)
        except Exception:
            sc = 0.6
        dval = sc if "bull" in typ else -sc if "bear" in typ else 0.0
    comps.append((dval, 0.7))
    if lp.get("name") and lp.get("name") != "none":
        try:
            lp_v = min(1.0, float(lp.get("validation_score") or 0))
        except Exception:
            lp_v = 0.0
        if lp_v > 0:
            comps.append((_bull_bear(lp.get("direction")) * lp_v, 1.2))

    den = sum(w for _v, w in comps)
    score = max(-1.0, min(1.0, sum(v * w for v, w in comps) / den)) if den else 0.0
    return pack(round(score, 3), 1, trend4h=tc.get("trend"), ema4h=tc.get("ema_alignment"),
                trend1h=sct.get("trend"), trend1d=htf.get("trend"), tech_bias=ts.get("bias"),
                divergence=(det[0].get("type") if det else dv.get("summary")), latest_pattern=lp.get("name"))


# ── perp structure ───────────────────────────────────────────────────────────

_PRICE_OI = {("up", "up"): 0.7, ("up", "down"): 0.3, ("down", "down"): -0.3, ("down", "up"): -0.7}


def perp_dim(symbol: str) -> dict[str, Any]:
    try:
        d = _data(call_skill("perp_contract_analysis", {"symbol": symbol, "timeframe": "4h"}))
    except Exception:
        return pack(None, 0)
    bias = str((d.get("action_guidance") or {}).get("bias") or "").lower()
    text = _concl(d)
    if not text and not bias:
        return pack(None, 0)
    m = re.search(r"price_(up|down)_oi_(up|down)", text)
    if m:
        base = _PRICE_OI[(m.group(1), m.group(2))]
    else:
        base = 1.0 if any(w in bias for w in ("bull", "long")) else -1.0 if any(w in bias for w in ("bear", "short")) else 0.0
    gm = re.search(r"oi/market[- ]cap ratio ([0-9.]+)\s*%", text)
    infl = float(gm.group(1)) if gm else None
    gate = 0.5 if (infl is not None and infl < 10) else 1.0
    crowded = any(w in text for w in ("crowded", "squeeze", "one-sided")) or "squeeze" in bias
    score = base * gate
    if crowded and score > 0:
        score *= 0.5
    return pack(round(max(-1.0, min(1.0, score)), 3), 1, bias=bias,
                price_oi=(m.group(0) if m else None), oi_mcap_pct=infl, crowded=crowded)


# ── dark flow ────────────────────────────────────────────────────────────────


def oi_dark_flow(symbol: str, window: str = "4h") -> dict[str, Any]:
    try:
        d = _data(call_skill("detect_oi_dark_flow_setup", {"symbol": symbol, "window": window}))
    except Exception:
        return pack(None, 0)
    rep = d.get("report") or {}
    dm = d.get("derived_metrics") or {}
    state = str(rep.get("setup_state") or "").lower()
    if not state:
        return pack(None, 0)
    try:
        dfs = float(dm.get("dark_flow_score"))
    except Exception:
        dfs = None
    if any(w in state for w in ("accumul", "dark_flow", "stealth", "absorption")):
        s = 0.7
        if dfs is not None:
            s = max(s, min(1.0, dfs))
    elif any(w in state for w in ("distrib", "crowded", "noise", "exhaust", "squeeze")):
        s = -0.4
    else:
        s = 0.0
    return pack(s, 1, setup_state=state, dark_flow_score=dfs, oi_change_pct=dm.get("oi_change_pct"))


# ── whale flow ───────────────────────────────────────────────────────────────

_WHALE_SCALE = {"low": 0.3, "contained": 0.3, "moderate": 0.5, "elevated": 0.7, "high": 0.9, "extreme": 1.0}


def whale_flow(symbol: str, chain: str = "ethereum", window: str = "1d") -> dict[str, Any]:
    try:
        d = _data(call_skill("monitor_whale_transfer_anomalies", {"symbol": symbol, "chain": chain, "window": window}))
    except Exception:
        return pack(None, 0)
    rep = d.get("report") or {}
    direction = str(rep.get("anomaly_direction") or "").lower()
    scale = str(rep.get("anomaly_scale") or "").lower()
    mag = _WHALE_SCALE.get(scale)
    directional = direction and "unavailable" not in direction and direction not in ("none", "no_anomaly", "neutral", "quiet")
    if directional:
        m = mag if mag is not None else 0.5
        if any(w in direction for w in ("accumul", "outflow", "withdraw")):
            s = m
        elif any(w in direction for w in ("distrib", "inflow", "deposit")):
            s = -m
        else:
            s = 0.0
        return pack(s, 1, direction=direction, scale=scale)
    if mag is not None:
        flags = ["whale_activity_extreme"] if scale in ("extreme", "high") else []
        return pack(0.0, 0.5, flags, direction=direction or None, scale=scale)
    return pack(None, 0, direction=direction or None)


# ── unlock pressure ──────────────────────────────────────────────────────────

_UNLOCK_PRESSURE = {"muted": 0.0, "low": 0.0, "moderate": -0.4, "elevated": -0.6,
                    "heavy": -0.9, "high": -0.9, "severe": -1.0}


def unlock_impact(symbol: str) -> dict[str, Any]:
    try:
        d = _data(call_skill("analyze_token_unlock_impact", {"token_id_or_symbol": symbol}))
    except Exception:
        return pack(None, 0)
    rep = d.get("report") or {}
    sp = str(rep.get("sell_pressure_state") or "").lower()
    cliff = str(rep.get("cliff_risk") or "").lower()
    nxt = rep.get("next_supply_event") or {}
    if not sp and not cliff:
        return pack(None, 0)
    s = _UNLOCK_PRESSURE.get(sp, 0.0)
    try:
        days, pct = nxt.get("days_from_now"), nxt.get("unlock_pct_of_supply")
        if days is not None and float(days) <= 14 and pct is not None and float(pct) >= 1.0:
            s = min(s, -0.7)
    except Exception:
        pass
    if cliff in ("high", "severe"):
        s = min(s, -0.6)
    return pack(max(-1.0, s), 1, sell_pressure=sp, cliff_risk=cliff)


# ── sentiment ────────────────────────────────────────────────────────────────

_SENT_POS = ("constructive", "bullish tilt", "bullish", "improving", "turning positive",
             "rising conviction", "accumulating conviction", "positive fundamental", "fresh bullish")
_SENT_NEG = ("cautionary", "bearish tilt", "bearish", "fading", "fatigue", "deteriorat",
             "losing conviction", "risk chatter", "distribution")
_SENT_LOW = ("low evidence quality", "signal strength across all discussion lanes is low", "low signal",
             "sparse", "thin coverage", "insufficient", "no directional consensus", "no stable directional")


def kol_sentiment(symbol: str) -> dict[str, Any]:
    try:
        d = _data(call_skill("altcoin_kol_sentiment", {"symbol": symbol}))
    except Exception:
        return pack(None, 0)
    bias = str((d.get("action_guidance") or {}).get("bias") or "").lower()
    t = _concl(d)
    if not t and not bias:
        return pack(None, 0)
    np_ = sum(w in t for w in _SENT_POS)
    nn = sum(w in t for w in _SENT_NEG)
    if "risk" in bias:
        nn += 1
    low = any(w in t for w in _SENT_LOW)
    if np_ == 0 and nn == 0:
        return pack(0.0, 0.4 if low else 0.5, pos=0, neg=0, low=low, bias=bias)
    raw = (np_ - nn) / (np_ + nn)
    score = max(-0.5, min(0.5, raw * 0.5))
    if low:
        score *= 0.6
    return pack(round(score, 3), 0.5 if low else 1.0, pos=np_, neg=nn, low=low, bias=bias)


# ── sector rotation ──────────────────────────────────────────────────────────


def sector_rotation(symbol: str) -> dict[str, Any]:
    try:
        d = _data(call_skill("altcoin_sector_analysis", {"symbol": symbol}))
    except Exception:
        return pack(None, 0)
    t = _concl(d)
    if not t:
        return pack(None, 0)
    pos = any(w in t for w in ("leading its sector", "leads its sector", "outperforming",
                               "rotating into", "strongest", "sector leader"))
    neg = any(w in t for w in ("countertrend", "underperforming", "lagging", "weakest", "rotating out"))
    s = 0.6 if pos and not neg else -0.6 if neg and not pos else 0.0
    return pack(s, 1, pos=pos, neg=neg)
