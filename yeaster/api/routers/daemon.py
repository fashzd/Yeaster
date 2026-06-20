"""The autonomous daemon — start (optionally timed+locked) / stop / status / run-once."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from yeaster.runtime.daemon import DAEMON, KillSwitchError

router = APIRouter(prefix="/daemon", tags=["daemon"])


class DaemonStart(BaseModel):
    cadence_seconds: int = 300
    cmc_backend: str = "auto"
    twak_backend: str = "auto"
    live: bool = False
    run_hours: Optional[float] = None     # committed-run duration; chat locks for the window
    lock: bool = False                    # lock the chat + require password to kill
    kill_password: Optional[str] = None   # required to halt early when locked


class DaemonStop(BaseModel):
    password: Optional[str] = None


@router.post("/start")
def start(cfg: DaemonStart) -> dict:
    return DAEMON.start(cadence_seconds=cfg.cadence_seconds, cmc_backend=cfg.cmc_backend,
                        twak_backend=cfg.twak_backend, run_hours=cfg.run_hours, lock=cfg.lock,
                        kill_password=cfg.kill_password, live=cfg.live)


@router.post("/stop")
def stop(req: DaemonStop) -> dict:
    try:
        return DAEMON.stop(password=req.password)
    except KillSwitchError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/status")
def status() -> dict:
    return DAEMON.status()


@router.post("/run-once")
def run_once() -> dict:
    return DAEMON.run_once()
