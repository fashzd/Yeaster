"""x402 micropayments — status, the sellable daily alpha, and settlement trail.

The agent SELLS its daily alpha over x402: a buyer pays in USDT on BSC, the server
verifies the on-chain transfer, then releases the pick. Enable with ``YST_X402=1``.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from yeaster.brain import alpha as alpha_mod
from yeaster.execution import x402 as x402_mod

router = APIRouter(prefix="/x402", tags=["x402"])


@router.get("")
def status(limit: int = Query(20, ge=1, le=200)) -> dict:
    cfg = x402_mod.X402Config()
    return {
        "enabled": x402_mod.enabled(),
        "scheme": x402_mod.X402_SCHEME,
        "asset": "USDT",
        "network": cfg.network,
        "price_usd": x402_mod.alpha_price_usd(),
        "pay_to": x402_mod.alpha_pay_to(),
        "total_settled_usd": x402_mod.total_settled_usd(),
        "settlements": x402_mod.list_settlements(limit),
    }


@router.get("/alpha/teaser")
def alpha_teaser() -> dict:
    """The locked preview shown before payment (posture + conviction + proof, no pick)."""
    return {
        "enabled": x402_mod.enabled(),
        "price_usd": x402_mod.alpha_price_usd(),
        "asset": "USDT",
        "network": "bsc",
        "pay_to": x402_mod.alpha_pay_to(),
        "teaser": alpha_mod.teaser(alpha_mod.daily_alpha()),
    }


class AlphaPurchase(BaseModel):
    payment_tx: str | None = None


@router.post("/alpha")
def buy_alpha(req: AlphaPurchase, response: Response) -> dict:
    """Buy the daily alpha. Pay ``price_usd`` USDT to ``pay_to`` on BSC, then POST the
    payment tx hash. Returns HTTP 402 with payment requirements until a valid,
    unredeemed payment is supplied."""
    if not x402_mod.enabled():
        response.status_code = 404
        return {"error": "x402 alpha sales are disabled (set YST_X402=1)."}

    price = x402_mod.alpha_price_usd()
    pay_to = x402_mod.alpha_pay_to()
    requirements = {"price_usd": price, "asset": "USDT", "network": "bsc", "pay_to": pay_to,
                    "scheme": "exact", "how": f"send >= {price} USDT to {pay_to} on BSC, then POST {{payment_tx}}"}

    tx = (req.payment_tx or "").strip()
    if not tx:
        response.status_code = 402
        return {"error": "payment required", **requirements}

    if x402_mod.is_tx_consumed(tx):
        response.status_code = 402
        return {"error": "this payment tx was already redeemed", **requirements}

    v = x402_mod.verify_onchain_payment(tx, pay_to, price)
    if not v.get("ok"):
        response.status_code = 402
        return {"error": f"payment not verified: {v.get('reason')}", **requirements}

    x402_mod.record_alpha_sale(tx, v["amount_usd"], v.get("payer", "?"), pay_to)
    return {
        "paid": True, "amount_usd": v["amount_usd"], "payer": v.get("payer"),
        "alpha": alpha_mod.daily_alpha(),
    }
