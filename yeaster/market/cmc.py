"""CoinMarketCap market-data client → a normalized :class:`MarketSnapshot`.

Backends:
  * ``mock`` — deterministic synthetic quotes (keyless; tests/dev).
  * ``rest`` — CMC Pro REST (quotes + global metrics + fear&greed).
  * ``mcp``  — CMC Data MCP (best-effort; falls back to REST/mock).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Optional

import requests

from yeaster.core.settings import get_settings
from yeaster.core.universe import PEGGED_OR_REFERENCE, STABLES, default_symbols
from yeaster.market.models import AssetQuote, MarketSnapshot, MarketStructure

REST_BASE = "https://pro-api.coinmarketcap.com"
HTTP_TIMEOUT = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_backend(requested: str = "auto") -> str:
    requested = (requested or "auto").lower()
    if requested in ("mock", "rest", "mcp"):
        return requested
    s = get_settings()
    if s.cmc_mcp_api_key:
        return "mcp"
    if s.cmc_api_key:
        return "rest"
    return "mock"


def _hash_snapshot(snap: MarketSnapshot) -> str:
    payload = snap.model_dump(exclude={"snapshot_hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "0x" + hashlib.sha256(canonical.encode()).hexdigest()


# ── mock backend ─────────────────────────────────────────────────────────────


def _mock_assets(symbols: list[str]) -> list[AssetQuote]:
    from yeaster.execution.twak import mock_price  # local import avoids cycle

    out: list[AssetQuote] = []
    for sym in symbols:
        h = int(hashlib.sha256(sym.encode()).hexdigest()[:8], 16)
        stable = sym in STABLES
        pct24 = 0.0 if stable else round(((h % 2000) / 100.0) - 10.0, 2)       # -10..+10
        pct7 = 0.0 if stable else round(((h % 3000) / 100.0) - 15.0, 2)
        rsi = 50.0 if stable else round(30.0 + (h % 4000) / 100.0, 1)          # 30..70
        out.append(AssetQuote(
            symbol=sym, name=sym, price_usd=mock_price(sym),
            percent_change_1h=0.0 if stable else round(((h % 400) / 100.0) - 2.0, 2),
            percent_change_24h=pct24, percent_change_7d=pct7,
            volume_24h_usd=float(1_000_000 + h % 50_000_000),
            market_cap_usd=float(10_000_000 + h % 5_000_000_000),
            is_stablecoin=stable, rsi_14=rsi,
            ema_trend="bullish" if pct7 > 0 else "bearish" if pct7 < 0 else "neutral",
        ))
    return out


def _mock_structure(assets: list[AssetQuote]) -> MarketStructure:
    movers = [a for a in assets if not a.is_stablecoin and a.percent_change_24h is not None]
    up = sum(1 for a in movers if (a.percent_change_24h or 0) > 0)
    breadth = round(up / len(movers), 3) if movers else 0.5
    btc = next((a for a in assets if a.symbol in ("BTC", "BTCB")), None)
    btc_dir = "flat"
    if btc and btc.percent_change_24h is not None:
        btc_dir = "up" if btc.percent_change_24h > 0.5 else "down" if btc.percent_change_24h < -0.5 else "flat"
    regime = "RISK_ON" if breadth >= 0.6 else "RISK_OFF" if breadth <= 0.35 else "NEUTRAL"
    return MarketStructure(
        btc_direction=btc_dir, btc_dominance_pct=52.0, total_market_cap_usd=2.3e12,
        total_volume_24h_usd=9.0e10, fear_greed_index=54, fear_greed_label="Neutral",
        breadth=breadth, regime_hint=regime,
    )


# ── REST backend ─────────────────────────────────────────────────────────────


def _rest_get(path: str, params: dict, key: str) -> dict:
    r = requests.get(
        REST_BASE + path, params=params,
        headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _rest_assets(symbols: list[str], key: str) -> list[AssetQuote]:
    data = _rest_get("/v1/cryptocurrency/quotes/latest",
                     {"symbol": ",".join(symbols), "convert": "USD"}, key).get("data", {})
    out: list[AssetQuote] = []
    for sym in symbols:
        entry = data.get(sym)
        if isinstance(entry, list):
            entry = entry[0] if entry else None
        if not entry:
            continue
        q = (entry.get("quote") or {}).get("USD") or {}
        stable = sym in STABLES
        out.append(AssetQuote(
            symbol=sym, name=entry.get("name", sym), price_usd=float(q.get("price") or 0.0),
            percent_change_1h=q.get("percent_change_1h"), percent_change_24h=q.get("percent_change_24h"),
            percent_change_7d=q.get("percent_change_7d"), volume_24h_usd=q.get("volume_24h"),
            market_cap_usd=q.get("market_cap"), is_stablecoin=stable,
            ema_trend="bullish" if (q.get("percent_change_7d") or 0) > 0 else "bearish",
        ))
    return out


def _rest_structure(assets: list[AssetQuote], key: str) -> MarketStructure:
    s = _mock_structure(assets)  # breadth/btc_dir from our own assets
    try:
        g = _rest_get("/v1/global-metrics/quotes/latest", {"convert": "USD"}, key).get("data", {})
        q = (g.get("quote") or {}).get("USD") or {}
        s.btc_dominance_pct = g.get("btc_dominance")
        s.total_market_cap_usd = q.get("total_market_cap")
        s.total_volume_24h_usd = q.get("total_volume_24h")
    except Exception:
        pass
    try:
        fg = _rest_get("/v3/fear-and-greed/latest", {}, key).get("data", {})
        s.fear_greed_index = int(fg.get("value")) if fg.get("value") is not None else None
        s.fear_greed_label = fg.get("value_classification")
    except Exception:
        pass
    return s


# ── public ───────────────────────────────────────────────────────────────────


def build_snapshot(backend: str = "auto", symbols: Optional[list[str]] = None) -> MarketSnapshot:
    backend = resolve_backend(backend)
    symbols = symbols or default_symbols()
    s = get_settings()

    if backend == "rest" and s.cmc_api_key:
        try:
            assets = _rest_assets(symbols, s.cmc_api_key)
            structure = _rest_structure(assets, s.cmc_api_key)
        except Exception:
            backend, assets, structure = "mock", _mock_assets(symbols), None
    elif backend == "mcp":
        # MCP data path is best-effort; REST/mock cover the live read for now.
        if s.cmc_api_key:
            try:
                assets = _rest_assets(symbols, s.cmc_api_key)
                structure = _rest_structure(assets, s.cmc_api_key)
                backend = "rest"
            except Exception:
                backend, assets, structure = "mock", _mock_assets(symbols), None
        else:
            backend, assets, structure = "mock", _mock_assets(symbols), None
    else:
        backend, assets, structure = "mock", _mock_assets(symbols), None

    if structure is None:
        structure = _mock_structure(assets)

    snap = MarketSnapshot(generated_at=_now(), backend=backend, structure=structure, assets=assets)
    snap.snapshot_hash = _hash_snapshot(snap)
    return snap


def persist_snapshot(snap: MarketSnapshot) -> None:
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(snap.model_dump_json(indent=2))
