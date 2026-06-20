"""x402 micropayments — status + settlement trail."""

from __future__ import annotations

from fastapi import APIRouter, Query

from yeaster.execution import x402 as x402_mod

router = APIRouter(prefix="/x402", tags=["x402"])


@router.get("")
def status(limit: int = Query(20, ge=1, le=200)) -> dict:
    cfg = x402_mod.X402Config()
    return {
        "enabled": x402_mod.enabled(),
        "scheme": x402_mod.X402_SCHEME,
        "asset": cfg.asset,
        "network": cfg.network,
        "price_usd": cfg.price_usd,
        "total_settled_usd": x402_mod.total_settled_usd(),
        "settlements": x402_mod.list_settlements(limit),
    }
