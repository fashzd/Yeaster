"""Wallet + brackets — live TWAK reads for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from yeaster.execution import brackets
from yeaster.execution.twak import TwakBroker

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("")
def wallet(backend: str = Query("auto")) -> dict:
    """The agent's live book: holdings, per-asset value, equity."""
    try:
        broker = TwakBroker(backend=backend)
        pf = broker.portfolio()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"wallet read failed: {exc}")
    return {
        "backend": broker.backend,
        "address": pf.address,
        "chain_id": pf.chain_id,
        "total_value_usd": pf.total_value_usd,
        "native_balance": pf.native_balance,
        "positions_pct": pf.positions_pct,
        "tokens": [b.model_dump() for b in pf.balances],
        "captured_at": pf.captured_at,
    }


@router.get("/brackets")
def brackets_list(backend: str = Query("auto")) -> dict:
    """Live native stop / take-profit automations protecting open positions."""
    autos = brackets.list_automations(backend)
    return {"count": len(autos), "automations": [a.model_dump() for a in autos]}
