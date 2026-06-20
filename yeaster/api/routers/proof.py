"""Proof ledger — the tamper-evident decision chain."""

from __future__ import annotations

from fastapi import APIRouter, Query

from yeaster.proof import ledger

router = APIRouter(prefix="/proof", tags=["proof"])


@router.get("")
def chain(limit: int = Query(20, ge=1, le=200)) -> dict:
    blocks = ledger.load_chain(limit=limit)
    return {
        "count": len(blocks),
        "verified": ledger.verify_chain(),
        "blocks": [
            {"block_index": b.block_index, "block_hash": b.block_hash, "block_timestamp": b.block_timestamp,
             "final_decision": b.final_decision, "snapshot_hash": b.snapshot_hash,
             "pick": (b.commit_record or {}).get("ticket", {}) and (b.commit_record or {}).get("ticket", {}).get("to_asset"),
             "posture": (b.commit_record or {}).get("posture"),
             "rationale": (b.commit_record or {}).get("rationale")}
            for b in reversed(blocks)
        ],
    }
