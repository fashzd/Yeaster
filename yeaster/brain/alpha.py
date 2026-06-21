"""The agent's sellable signal — the 'daily alpha'.

Derived from the tamper-evident proof chain: the **strongest recent signal** the
agent graded (highest coverage-weighted composite), enriched with its evidence
(composite, coverage, kind, detector tags) and the lead's thesis when that name
was actually committed. This is what an x402 buyer pays to unlock — a genuine,
proof-backed pick, not a low-conviction compliance trade.
"""

from __future__ import annotations

from typing import Any, Optional

from yeaster.core.universe import is_stable


def _pack(block, cr: dict, symbol: str, card: dict, thesis: Optional[str]) -> dict[str, Any]:
    return {
        "available": True,
        "symbol": symbol,
        "composite": round(float(card.get("composite") or 0.0), 3),
        "coverage": round(float(card.get("coverage") or 0.0), 3),
        "kind": card.get("kind"),
        "conviction": round(float(cr.get("conviction") or 0.0), 3),
        "thesis": (thesis or "").strip() or _auto_thesis(symbol, card),
        "posture": cr.get("posture"),
        "proof_block_hash": block.block_hash,
        "block_index": block.block_index,
        "generated_at": cr.get("generated_at") or block.block_timestamp,
    }


def _auto_thesis(symbol: str, card: dict) -> str:
    comp, cov, kind = card.get("composite"), card.get("coverage"), card.get("kind") or "momentum"
    return (f"{symbol} is the agent's strongest current {kind} signal — top coverage-weighted composite "
            f"{comp:+.2f} on {(cov or 0) * 100:.0f}% data coverage across technicals, derivatives, flow and sector.")


def daily_alpha() -> dict[str, Any]:
    """The strongest recent graded signal, proof-backed. Quality over recency: we
    rank by composite across the recent chain, not just the last (maybe compliance) trade."""
    from yeaster.proof import ledger

    blocks = ledger.load_chain(limit=120)
    best = None  # (composite, block, commit_record, card, thesis)
    for b in blocks:
        cr = b.commit_record or {}
        top = ((cr.get("reasoning") or {}).get("grade") or {}).get("top") or []
        ticket = cr.get("ticket") or {}
        picked = str(ticket.get("to_asset") or "").upper()
        for card in top:
            sym = str(card.get("symbol") or "").upper()
            if not sym or is_stable(sym):
                continue
            comp = float(card.get("composite") or 0.0)
            # the lead's prose thesis only applies to the name it actually picked
            thesis = cr.get("rationale") if sym == picked else None
            if best is None or comp > best[0]:
                best = (comp, b, cr, card, thesis)

    if best:
        _, b, cr, card, thesis = best
        return _pack(b, cr, str(card["symbol"]).upper(), card, thesis)
    return {"available": False, "note": "no graded signal yet — run a cycle to mint today's alpha"}


def teaser(alpha: dict[str, Any]) -> dict[str, Any]:
    """A non-revealing preview shown before payment (no symbol/thesis, but quality signals)."""
    if not alpha.get("available"):
        return {"available": False, "note": alpha.get("note")}
    return {
        "available": True,
        "posture": alpha.get("posture"),
        "conviction": alpha.get("conviction"),
        "composite": alpha.get("composite"),
        "coverage": alpha.get("coverage"),
        "kind": alpha.get("kind"),
        "generated_at": alpha.get("generated_at"),
        "proof_block_hash": alpha.get("proof_block_hash"),
        "locked": True,
    }
