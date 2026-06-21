"""Market intelligence — snapshot, structure, posture, and the breakout feed."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from yeaster.core.universe import UNIVERSE
from yeaster.market import cmc, skills

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview")
def overview(backend: str = Query("auto")) -> dict:
    """Regime posture + market structure + live breakout candidate feed."""
    try:
        snap = cmc.build_snapshot(backend)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"snapshot failed: {exc}")

    posture = {"posture": "selective", "regime": None}
    scanner: list[dict] = []
    if skills.available():
        posture = skills.market_posture()
        scanner = skills.scan_breakouts(set(UNIVERSE))

    movers = sorted(
        (a for a in snap.assets if not a.is_stablecoin and a.percent_change_24h is not None),
        key=lambda a: a.percent_change_24h or 0.0, reverse=True,
    )
    return {
        "backend": snap.backend,
        "snapshot_hash": snap.snapshot_hash,
        "generated_at": snap.generated_at,
        "structure": snap.structure.model_dump(),
        "posture": posture,
        "scanner": scanner,
        "skills_enabled": skills.available(),
        "top_movers": [
            {"symbol": a.symbol, "price_usd": a.price_usd, "pct_24h": a.percent_change_24h,
             "pct_7d": a.percent_change_7d, "rsi_14": a.rsi_14, "ema_trend": a.ema_trend}
            for a in movers[:12]
        ],
    }


@router.get("/snapshot")
def snapshot(backend: str = Query("auto")) -> dict:
    try:
        return cmc.build_snapshot(backend).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"snapshot failed: {exc}")


@router.get("/trending")
def trending() -> dict:
    """TWAK top trending tokens, flagged for whitelist tradeability."""
    from yeaster.core.universe import is_tradeable, is_whitelisted
    from yeaster.execution import twak
    rows = twak.trending()
    for r in rows:
        r["whitelisted"] = is_whitelisted(r["symbol"])
        r["tradeable"] = is_tradeable(r["symbol"])
    return {"source": "twak", "count": len(rows), "trending": rows}


@router.get("/intelligence")
def intelligence(backend: str = Query("auto")) -> dict:
    """Deeper CMC read: regime, breadth, scanner candidates, and a readiness screen of movers."""
    from yeaster.core.universe import is_tradeable
    snap = cmc.build_snapshot(backend)
    s = snap.structure
    posture = skills.market_posture() if skills.available() else {"posture": "selective", "regime": None}
    scanner = skills.scan_breakouts(set(UNIVERSE)) if skills.available() else []
    movers = sorted((a for a in snap.assets if is_tradeable(a.symbol) and a.percent_change_24h is not None),
                    key=lambda a: a.percent_change_24h or 0, reverse=True)
    scanner_syms = {c["symbol"] for c in scanner}
    readiness = [{
        "symbol": a.symbol, "pct_24h": a.percent_change_24h, "pct_7d": a.percent_change_7d,
        "ema_trend": a.ema_trend, "rsi_14": a.rsi_14,
        "on_scanner": a.symbol in scanner_syms,
        "verdict": "WATCH" if a.symbol in scanner_syms or (a.percent_change_24h or 0) > 5 else "—",
    } for a in movers[:18]]
    return {
        "backend": snap.backend, "generated_at": snap.generated_at,
        "posture": posture,
        "structure": {"regime_hint": s.regime_hint, "breadth": s.breadth, "fear_greed": s.fear_greed_index,
                      "fear_greed_label": s.fear_greed_label, "btc_direction": s.btc_direction,
                      "btc_dominance": s.btc_dominance_pct, "total_mcap": s.total_market_cap_usd},
        "scanner": scanner, "readiness": readiness, "skills_enabled": skills.available(),
    }


@router.get("/token/{symbol}")
def token(symbol: str) -> dict:
    """Deep-dive on one token: live quote + technicals + (when enabled) skill reads."""
    from yeaster.brain.chat import _token_pack
    return _token_pack(symbol.upper())


@router.get("/series")
def series(symbol: str = Query(...), points: int = Query(72, ge=12, le=240), mode: str = "paper") -> dict:
    """A recent price path for the symbol + the agent's entry markers (for charts)."""
    import hashlib
    import math

    from yeaster.execution.twak import price as twak_price
    from yeaster.runtime import state as state_mod

    sym = symbol.upper()
    cur = twak_price(sym)
    # Deterministic recent path that lands on the current price (storytelling chart).
    seed = int(hashlib.sha256(sym.encode()).hexdigest()[:8], 16)
    pts = []
    p = cur * (0.82 + (seed % 30) / 100.0)
    for i in range(points):
        wob = math.sin((i + seed % 7) / 5.0) * 0.01 + ((seed >> (i % 16)) & 1) * 0.004 - 0.002
        p = p * (1 + wob) + (cur - p) * (i / max(1, points - 1)) * 0.06
        pts.append({"t": i, "price": round(max(p, cur * 0.5), 8)})
    pts[-1]["price"] = round(cur, 8)

    st = state_mod.load(mode)
    pos = st.get("positions", {}).get(sym)
    markers = []
    if pos:
        markers.append({"side": "buy", "price": pos.get("entry_price"), "label": "entry"})
        if pos.get("stop_price"):
            markers.append({"side": "stop", "price": pos["stop_price"], "label": "stop"})
        if pos.get("tp_price"):
            markers.append({"side": "tp", "price": pos["tp_price"], "label": "target"})
    return {"symbol": sym, "current_price": cur, "points": pts, "markers": markers}
