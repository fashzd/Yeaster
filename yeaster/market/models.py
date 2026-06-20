"""Market-data schemas — the normalized snapshot the brain reads each tick."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AssetQuote(BaseModel):
    symbol: str
    name: str = ""
    price_usd: float = 0.0
    percent_change_1h: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    is_stablecoin: bool = False
    # technicals (pre-computed by CMC MCP, or computed locally over closes)
    rsi_14: Optional[float] = None
    ema_trend: str = "neutral"


class MarketStructure(BaseModel):
    btc_direction: str = "flat"
    btc_dominance_pct: Optional[float] = None
    total_market_cap_usd: Optional[float] = None
    total_volume_24h_usd: Optional[float] = None
    fear_greed_index: Optional[int] = None
    fear_greed_label: Optional[str] = None
    breadth: Optional[float] = None          # fraction of non-stable assets up 24h
    regime_hint: str = "NEUTRAL"             # PANIC | RISK_OFF | NEUTRAL | RISK_ON


class MarketSnapshot(BaseModel):
    schema_version: str = "1.0"
    generated_at: str
    backend: str                              # mock | rest | mcp
    convert: str = "USD"
    snapshot_hash: Optional[str] = None
    structure: MarketStructure = Field(default_factory=MarketStructure)
    assets: list[AssetQuote] = Field(default_factory=list)

    def by_symbol(self) -> dict[str, AssetQuote]:
        return {a.symbol: a for a in self.assets}
