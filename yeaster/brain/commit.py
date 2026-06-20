"""COMMIT — the final reasoning pass: pick one and size it (or stand down).

Policy proposes, rails dispose. The policy *arm* (deterministic or LLM lead)
proposes a pick + conviction from the vetted survivors; the deterministic RAILS
turn conviction into notional under risk-per-trade, drawdown brakes, and caps.
(Proven sizing logic + the god-trader lead, ported.)
"""

from __future__ import annotations

import json
from typing import Any, Optional

from yeaster.brain import llm
from yeaster.core.universe import DEFAULT_RESERVE

# ── deterministic rails ──────────────────────────────────────────────────────
RISK_PER_TRADE = 0.007       # 0.7% R base
STOP_PCT = 0.035             # 3.5% notional stop = sizing divisor
DD_HALFSIZE = 0.09           # halve risk at 9% drawdown
DD_HALT = 0.15               # NO new entries at 15% drawdown
MAX_POSITION_PCT = 0.30      # per-name cap
SHORTLIST_N = 8
COMPOSITE_BAR = 0.15         # det arm qualification bar
COVERAGE_FLOOR = 0.40


def size_amount_pct(conviction: float, equity: float, drawdown: float) -> Optional[float]:
    """R-based sizing → portfolio fraction, or None to stand down (hard brake)."""
    if drawdown >= DD_HALT or equity <= 0:
        return None
    risk = RISK_PER_TRADE * (0.5 if drawdown >= DD_HALFSIZE else 1.0) * max(0.2, min(1.0, conviction))
    notional = min(risk * equity / STOP_PCT, MAX_POSITION_PCT * equity)
    return round(notional / equity, 4)


def _eligible(cards: list[dict]) -> list[dict]:
    from yeaster.brain.vet import is_hard_blocked
    return [c for c in cards if not is_hard_blocked(c)]


def _ticket(pick: str, conviction: float, equity: float, drawdown: float, rationale: str) -> Optional[dict]:
    amount = size_amount_pct(conviction, equity, drawdown)
    if amount is None or amount <= 0:
        return None
    return {"from_asset": DEFAULT_RESERVE, "to_asset": pick.upper(), "amount_pct": amount,
            "confidence": round(conviction, 3), "kind": "entry", "thesis": rationale[:240]}


def _decision(arm: str, pick: Optional[str], conviction: float, rationale: str,
              equity: float, drawdown: float, considered: list[str], **extra) -> dict:
    ticket = _ticket(pick, conviction, equity, drawdown, rationale) if pick else None
    return {"arm": arm, "pick": pick if ticket else None, "conviction": round(conviction, 3) if ticket else 0.0,
            "rationale": rationale, "ticket": ticket, "considered": considered, **extra}


# ── arms ─────────────────────────────────────────────────────────────────────


def arm_det_top(cards: list[dict], posture: str, equity: float, drawdown: float, book: dict) -> dict:
    pool = _eligible(cards)
    considered = [c["symbol"] for c in pool]
    qualified = [c for c in pool if c["composite"] >= COMPOSITE_BAR and c["coverage"] >= COVERAGE_FLOOR]
    if not qualified:
        return _decision("det_top", None, 0.0, "no candidate cleared the composite/coverage bar.",
                         equity, drawdown, considered)
    top = max(qualified, key=lambda c: c["composite"])
    conv = max(0.0, min(1.0, (top["composite"] - COMPOSITE_BAR) / (1 - COMPOSITE_BAR) + 0.3))
    return _decision("det_top", top["symbol"], conv,
                     f"top composite {top['composite']:+.3f} (cov {top['coverage']:.0%}, {top['kind']}).",
                     equity, drawdown, considered)


def arm_det_safety(cards: list[dict], posture: str, equity: float, drawdown: float, book: dict) -> dict:
    pool = [c for c in _eligible(cards) if c["composite"] >= 0.0]
    considered = [c["symbol"] for c in pool]
    if not pool:
        return _decision("det_safety", None, 0.0, "no survivable candidate.", equity, drawdown, considered)
    best = max(pool, key=lambda c: ((c["safety"] or {}).get("quality_score", 0.0), c["coverage"], c["composite"]))
    conv = max(0.0, min(1.0, 0.3 + 0.4 * best["coverage"] + 0.3 * max(0.0, best["composite"])))
    return _decision("det_safety", best["symbol"], conv,
                     f"safest + best-covered ({best['coverage']:.0%}, q{(best['safety'] or {}).get('quality_score',0):+.1f}).",
                     equity, drawdown, considered)


_LEAD_DISCIPLINED = (
    "You are a god-tier crypto trader with two decades of experience. Edge and asymmetry over activity; "
    "sitting in cash when there is no real edge is a valid, frequent outcome. You are graded by TOTAL RETURN "
    "over a short window, with a hard max-drawdown DQ. Pick the single best long from the shortlist, or null."
)
_LEAD_AGGRESSIVE = (
    "You are a god-tier crypto trader in ATTACK mode in a short ranked sprint. Capital in cash earns nothing; "
    "prefer placing at least one trade per day unless the entire tape is dangerous. Conviction IS position size: "
    "0.15-0.25 toehold, 0.40-0.60 solid, 0.75+ stake-your-reputation. Pick the single best long, or null only if "
    "the whole tape is a trap."
)
_LEAD_SCHEMA = ' Return STRICT JSON: {"pick":"<SYMBOL or null>","conviction":0.0-1.0,"thesis":"...","key_risk":"..."}'


def arm_llm_lead(cards: list[dict], posture: str, equity: float, drawdown: float, book: dict) -> dict:
    from yeaster.core.settings import get_settings
    pool = _eligible(cards)
    considered = [c["symbol"] for c in pool]
    if not pool:
        return _decision("llm_lead", None, 0.0, "no eligible candidate.", equity, drawdown, considered)
    if not llm.available():
        # graceful fallback to the deterministic top arm
        d = arm_det_top(cards, posture, equity, drawdown, book)
        d["arm"] = "llm_lead:fallback"
        return d

    style = get_settings().commit_style
    system = (_LEAD_AGGRESSIVE if style == "aggressive" else _LEAD_DISCIPLINED) + _LEAD_SCHEMA
    shortlist = [{
        "symbol": c["symbol"], "kind": c["kind"], "composite": c["composite"], "coverage": c["coverage"],
        "detect_tags": c["detect_tags"],
        "dim_scores": {k: round(v["score"], 2) for k, v in c["dims"].items() if v.get("score") is not None},
        "safety": {"quality": (c["safety"] or {}).get("quality_score"), "flags": (c["safety"] or {}).get("risk_flags")},
    } for c in pool[:SHORTLIST_N]]
    user = json.dumps({"posture": posture, "shortlist": shortlist, "book": book})[:11000]

    try:
        out = llm.complete_json(system, user)
    except llm.LLMUnavailable:
        d = arm_det_top(cards, posture, equity, drawdown, book)
        d["arm"] = "llm_lead:fallback"
        return d

    syms = {c["symbol"] for c in pool}
    pick = out.get("pick")
    pick = str(pick).upper() if pick is not None else None
    if pick in (None, "NONE", "NULL", "NO_TRADE", "NO TRADE", "") or pick not in syms:
        return _decision("llm_lead", None, 0.0, str(out.get("thesis") or "no clean trade")[:240],
                         equity, drawdown, considered, style=style)
    conv = max(0.0, min(1.0, float(out.get("conviction") or 0.0)))
    rationale = str(out.get("thesis") or f"lead picked {pick}")[:240]
    return _decision("llm_lead", pick, conv, rationale, equity, drawdown, considered,
                     style=style, key_risk=out.get("key_risk"))


ARMS = {
    "det_top": arm_det_top,
    "det_safety": arm_det_safety,
    "llm_lead": arm_llm_lead,
}


def commit(cards: list[dict], *, arm: str = "llm_lead", posture: str = "selective",
           equity: float = 0.0, drawdown: float = 0.0, book: Optional[dict] = None) -> dict:
    """Run the chosen policy arm; the rails inside size the ticket (or stand down)."""
    fn = ARMS.get(arm) or ARMS["llm_lead"]
    return fn(cards, posture, equity, drawdown, book or {})
