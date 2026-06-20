"""VET — the third reasoning pass: adversarial scrutiny + safety.

Two layers. (1) A deterministic SAFETY rail: any card carrying a genuine-rug flag
is hard-blocked and can never reach sizing. (2) An optional LLM critic that
refutes the survivors and flags traps — advisory, so an LLM outage never weakens
the hard safety rail.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from yeaster.brain import llm

# Genuine rug/scam signals — never tradeable. (Soft flags like twak_caution are
# evidence-only and do NOT block.)
HARD_BLOCK_FLAGS = {"security_flagged", "honeypot_detected", "tax_high", "liquidity_unlocked"}

SHORTLIST_N = 8

_CRITIC_SYSTEM = (
    "You are a ruthless crypto risk manager and trap-spotter. Your job is NOT to find reasons to "
    "trade — it is to find reasons NOT to. For each candidate hunt for: crowded/extended derivatives, "
    "distribution (price up while OI falls, or price down while OI rises), exhaustion, thin evidence "
    "coverage, conflicting dimensions, forward unlock pressure, and weak verification. Return STRICT "
    "JSON: {\"refuted\":[{\"symbol\":\"X\",\"reason\":\"...\"}], \"survivor\":\"<SYMBOL or null>\"}."
)


def is_hard_blocked(card: dict) -> bool:
    flags = set((card.get("safety") or {}).get("risk_flags") or [])
    return bool(flags & HARD_BLOCK_FLAGS)


def vet(cards: list[dict], *, posture: str = "selective", use_llm: bool = True) -> dict[str, Any]:
    """Return {survivors, blocked, refuted, critic_survivor, notes}."""
    blocked = [c["symbol"] for c in cards if is_hard_blocked(c)]
    survivors = [c for c in cards if not is_hard_blocked(c)]

    refuted: list[dict] = []
    critic_survivor: Optional[str] = None
    note = "deterministic safety only"

    if use_llm and survivors and llm.available():
        shortlist = [{
            "symbol": c["symbol"], "kind": c["kind"], "composite": c["composite"],
            "coverage": c["coverage"],
            "dim_scores": {k: round(v["score"], 2) for k, v in c["dims"].items() if v.get("score") is not None},
            "safety_flags": (c.get("safety") or {}).get("risk_flags") or [],
        } for c in survivors[:SHORTLIST_N]]
        try:
            out = llm.complete_json(_CRITIC_SYSTEM, json.dumps({"posture": posture, "candidates": shortlist}))
            refuted = [r for r in (out.get("refuted") or []) if isinstance(r, dict)][:12]
            sv = out.get("survivor")
            critic_survivor = str(sv).upper() if sv and str(sv).lower() not in ("null", "none", "") else None
            note = "llm critic applied"
        except llm.LLMUnavailable:
            note = "llm critic unavailable — deterministic safety only"

    return {
        "survivors": survivors, "blocked": blocked, "refuted": refuted,
        "critic_survivor": critic_survivor, "notes": note,
    }
