"""The agent — status, a tick, and the live reasoning stream."""

from __future__ import annotations

import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from yeaster.core.settings import get_settings
from yeaster.runtime import state as state_mod
from yeaster.runtime import tick as tick_mod

router = APIRouter(prefix="/agent", tags=["agent"])


class TickRequest(BaseModel):
    cmc_backend: str = "auto"
    twak_backend: str = "auto"
    arm: Optional[str] = None
    guard_enabled: bool = True
    posture_override: Optional[str] = None


class ManualRequest(BaseModel):
    from_asset: str = "USDC"
    to_asset: str
    amount_pct: float = 0.05
    twak_backend: str = "auto"
    guard_enabled: bool = True


@router.get("")
def status() -> dict:
    s = get_settings()
    st = state_mod.load()
    return {
        "agent": "yeaster",
        "commit_arm": s.commit_arm,
        "commit_style": s.commit_style,
        "mainnet_unlocked": s.mainnet_unlocked,
        "peak_equity_usd": st.get("peak_equity_usd"),
        "safe_mode_latched": st.get("safe_mode_latched"),
        "trades_today": st.get("trades_today"),
        "open_positions": len(st.get("positions", {})),
        "realized_pnl_usd": round(st.get("realized_pnl_usd", 0.0), 2),
        "wins": st.get("wins", 0),
        "losses": st.get("losses", 0),
        "win_rate": (round(st["wins"] / (st["wins"] + st["losses"]), 3)
                     if (st.get("wins", 0) + st.get("losses", 0)) else None),
        "recent_exits": st.get("recent_exits", [])[-5:],
        "last_tick_at": st.get("last_tick_at"),
    }


@router.get("/positions")
def positions() -> dict:
    st = state_mod.load()
    return {"positions": st.get("positions", {}), "safe_mode_latched": st.get("safe_mode_latched", False),
            "peak_equity_usd": st.get("peak_equity_usd", 0.0)}


def _reject_if_locked() -> None:
    from yeaster.runtime.daemon import DAEMON
    if DAEMON.is_locked():
        raise HTTPException(status_code=423, detail="agent is in a locked committed run — operator actions are disabled")


@router.post("/tick")
def tick(req: TickRequest) -> dict:
    _reject_if_locked()
    return tick_mod.run_tick(cmc_backend=req.cmc_backend, twak_backend=req.twak_backend,
                             arm=req.arm, guard_enabled=req.guard_enabled,
                             posture_override=req.posture_override)


@router.post("/manual")
def manual(req: ManualRequest) -> dict:
    """Operator-driven swap ('buy 5% CAKE' / 'sell CAKE') through guard → execute → proof."""
    _reject_if_locked()
    return tick_mod.run_manual(from_asset=req.from_asset, to_asset=req.to_asset,
                               amount_pct=req.amount_pct, twak_backend=req.twak_backend,
                               guard_enabled=req.guard_enabled)


@router.post("/tick/stream")
def tick_stream(req: TickRequest) -> StreamingResponse:
    """Server-Sent Events: each reasoning pass as it happens, then the result."""
    q: "queue.Queue" = queue.Queue()
    _DONE = object()

    def emit(stage: str, payload: dict) -> None:
        q.put((stage, payload))

    def worker() -> None:
        try:
            tick_mod.run_tick(cmc_backend=req.cmc_backend, twak_backend=req.twak_backend,
                              arm=req.arm, guard_enabled=req.guard_enabled,
                              posture_override=req.posture_override, emit=emit)
        except Exception as exc:
            q.put(("error", {"error": str(exc)}))
        finally:
            q.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is _DONE:
                break
            stage, payload = item
            yield f"event: {stage}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
