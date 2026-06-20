"""Tamper-evident proof ledger.

An append-only, sha256-linked chain. Each block captures the market snapshot,
the agent's per-tick decision (``commit_record``), and the firewall log, then
hashes the canonical block — any later edit invalidates every downstream hash.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHAIN_PATH = REPO_ROOT / "data" / "proof" / "proof_chain.jsonl"


class ProofBlock(BaseModel):
    block_index: int = Field(ge=0)
    block_timestamp: str
    previous_block_hash: str
    block_hash: str
    snapshot_hash: Optional[str] = None

    mandate_id: str
    safe_mode_active: bool = False
    final_decision: str
    rejection_reasons: list[str] = Field(default_factory=list)

    snapshot: dict[str, Any] = Field(default_factory=dict)
    commit_record: dict[str, Any] = Field(default_factory=dict)
    guard_log: dict[str, Any] = Field(default_factory=dict)


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return "0x" + hashlib.sha256(text.encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _previous(chain_path: Path) -> tuple[int, str]:
    if not chain_path.exists():
        return 0, "GENESIS"
    lines = [ln.strip() for ln in chain_path.read_text().splitlines() if ln.strip()]
    for offset, line in enumerate(reversed(lines)):
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
        return int(last["block_index"]) + 1, str(last["block_hash"])
    return 0, "GENESIS"


def append_proof(
    *,
    snapshot: dict[str, Any],
    commit_record: dict[str, Any],
    guard_log: dict[str, Any],
    chain_path: Path = DEFAULT_CHAIN_PATH,
) -> ProofBlock:
    """Build, hash, and append one proof block. Returns the block."""
    index, previous = _previous(chain_path)
    base = {
        "block_index": index,
        "block_timestamp": _now_iso(),
        "previous_block_hash": previous,
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "mandate_id": str(guard_log.get("mandate_id", "unknown-mandate")),
        "safe_mode_active": bool(guard_log.get("safe_mode_active", False)),
        "final_decision": str(guard_log.get("final_decision", "EVIDENCE")),
        "rejection_reasons": list(guard_log.get("rejection_reasons", [])),
        "snapshot": snapshot,
        "commit_record": commit_record,
        "guard_log": guard_log,
    }
    block = ProofBlock(**base, block_hash=_sha256(_canonical(base)))
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    with chain_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(block.model_dump(), separators=(",", ":")) + "\n")
    return block


def load_chain(chain_path: Path = DEFAULT_CHAIN_PATH, limit: Optional[int] = None) -> list[ProofBlock]:
    if not chain_path.exists():
        return []
    blocks: list[ProofBlock] = []
    for line in chain_path.read_text().splitlines():
        line = line.strip()
        if line:
            blocks.append(ProofBlock.model_validate_json(line))
    return blocks[-limit:] if limit else blocks


def verify_chain(chain_path: Path = DEFAULT_CHAIN_PATH) -> bool:
    """Recompute every block hash and confirm the links are intact."""
    prev = "GENESIS"
    for block in load_chain(chain_path):
        if block.previous_block_hash != prev:
            return False
        payload = block.model_dump()
        stored = payload.pop("block_hash")
        if _sha256(_canonical(payload)) != stored:
            return False
        prev = stored
    return True
