"""The five Yeaster strategy skills (Track 2).

Each wraps an existing brain/guard module in-process. Pure + read-only: they
compute and return evidence — they never trade, mutate state, or touch the wallet.
"""

from __future__ import annotations

from typing import Any

from yeaster.skills.base import Skill, register

# ── 1. Conviction Grader (flagship) ──────────────────────────────────────────


def _grade(params: dict[str, Any]) -> dict[str, Any]:
    from yeaster.brain.grade import grade_candidate
    symbol = str(params["symbol"]).upper()
    tags = params.get("tags") or []
    posture = params.get("posture") or "selective"
    card = grade_candidate(symbol, tags, posture=posture)
    return {
        "symbol": card["symbol"], "kind": card["kind"], "composite": card["composite"],
        "coverage": card["coverage"], "dims": card["dims"], "safety": card["safety"],
        "detect_tags": card["detect_tags"],
    }


CONVICTION_GRADER = register(Skill(
    unique_name="yeaster_conviction_grader",
    description="Grade a token across multiple signal dimensions into one coverage-weighted "
                "composite [-1..1], with a SEPARATE zero-weight safety axis (the SIREN fix). "
                "Returns the composite, evidence depth (coverage), per-dimension breakdown, and safety.",
    input_schema={"type": "object", "required": ["symbol"], "properties": {
        "symbol": {"type": "string", "description": "Token symbol, e.g. CAKE"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional detector tags (kind routing)"},
        "posture": {"type": "string", "enum": ["hunt", "selective", "stand_down"]},
    }},
    cost="high", tags=("scoring", "conviction", "momentum"), run=_grade,
))


# ── 2. Momentum Screener ─────────────────────────────────────────────────────


def _screen(params: dict[str, Any]) -> dict[str, Any]:
    from yeaster.brain import screen as screen_mod
    from yeaster.core.universe import UNIVERSE
    from yeaster.market import cmc
    backend = params.get("backend", "auto")
    universe = params.get("universe") or list(UNIVERSE)
    snap = cmc.build_snapshot(backend)
    live = screen_mod.live_map(snap)
    hist = params.get("bars") or {}  # optional caller-supplied daily bars
    cands = screen_mod.screen(live, hist, universe, enabled=set(params["detectors"]) if params.get("detectors") else None)
    return {"backend": snap.backend, "count": len(cands), "candidates": cands[:int(params.get("limit", 25))]}


MOMENTUM_SCREENER = register(Skill(
    unique_name="yeaster_momentum_screener",
    description="Scout a token universe for momentum candidates by fusing independent detectors "
                "(relative strength, breakout, accumulation, volume surge, trending runner, social "
                "scanner). Returns ranked candidates with cross-source agreement tags.",
    input_schema={"type": "object", "properties": {
        "backend": {"type": "string", "enum": ["auto", "rest", "mcp", "mock"]},
        "universe": {"type": "array", "items": {"type": "string"}},
        "detectors": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    }},
    cost="medium", tags=("discovery", "screening", "momentum"), run=_screen,
))


# ── 3. Trap / Safety Vetter ──────────────────────────────────────────────────


def _vet(params: dict[str, Any]) -> dict[str, Any]:
    from yeaster.brain.grade import grade_candidate
    from yeaster.brain.vet import HARD_BLOCK_FLAGS, is_hard_blocked
    symbol = str(params["symbol"]).upper()
    card = grade_candidate(symbol, params.get("tags") or [], posture=params.get("posture") or "selective")
    flags = (card.get("safety") or {}).get("risk_flags") or []
    blocked = is_hard_blocked(card)
    hard = sorted(set(flags) & HARD_BLOCK_FLAGS)
    return {
        "symbol": symbol, "tradeable": not blocked,
        "hard_block_flags": hard, "all_flags": flags,
        "safety_quality": (card.get("safety") or {}).get("quality_score"),
        "safety_coverage": (card.get("safety") or {}).get("coverage"),
        "verdict": "BLOCK" if blocked else "CLEAR",
        "reason": ("hard rug/scam signal: " + ", ".join(hard)) if blocked else "no hard safety flags",
    }


TRAP_VETTER = register(Skill(
    unique_name="yeaster_trap_vetter",
    description="Adversarial safety check on a token: hard-blocks genuine rug/scam signals "
                "(honeypot, punitive tax, unlocked liquidity, extreme whale concentration) and "
                "returns a CLEAR/BLOCK verdict with the token-quality read.",
    input_schema={"type": "object", "required": ["symbol"], "properties": {
        "symbol": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "posture": {"type": "string"},
    }},
    cost="medium", tags=("safety", "risk", "trap-detection"), run=_vet,
))


# ── 4. Bracket Planner ───────────────────────────────────────────────────────


def _brackets(params: dict[str, Any]) -> dict[str, Any]:
    from yeaster.core.preset import active
    entry = float(params["entry_price"])
    ex = active()["exit"]
    stop_pct = float(params.get("stop_pct", ex["stop_pct"]))
    tp_pct = float(params.get("tp_pct", ex["tp_pct"]))
    trail = float(params.get("trailing_pct", ex["trailing_pct"]))
    return {
        "entry_price": entry,
        "stop_price": round(entry * (1 - stop_pct), 10),
        "take_profit_price": round(entry * (1 + tp_pct), 10),
        "stop_pct": stop_pct, "tp_pct": tp_pct, "trailing_pct": trail,
        "risk_reward": round(tp_pct / stop_pct, 2) if stop_pct else None,
        "note": "let-winners-run calibration (wide stop, wider target, trailing ratchet)",
    }


BRACKET_PLANNER = register(Skill(
    unique_name="yeaster_bracket_planner",
    description="Plan native exit brackets for a long entry: stop-loss, take-profit and trailing "
                "stop using the finalized let-winners-run calibration (default 8% / 16% / 3%).",
    input_schema={"type": "object", "required": ["entry_price"], "properties": {
        "entry_price": {"type": "number", "exclusiveMinimum": 0},
        "stop_pct": {"type": "number"}, "tp_pct": {"type": "number"}, "trailing_pct": {"type": "number"},
    }},
    cost="low", tags=("risk", "exits", "execution"), run=_brackets,
))


# ── 5. Risk-Aware Sizer ──────────────────────────────────────────────────────


def _size(params: dict[str, Any]) -> dict[str, Any]:
    from yeaster.brain.commit import (DD_HALFSIZE, DD_HALT, MAX_POSITION_PCT,
                                      RISK_PER_TRADE, STOP_PCT, size_amount_pct)
    conviction = float(params["conviction"])
    equity = float(params["equity_usd"])
    dd = float(params.get("drawdown_pct", 0.0))
    amount = size_amount_pct(conviction, equity, dd)
    halted = amount is None
    return {
        "amount_pct": amount, "notional_usd": round((amount or 0) * equity, 2),
        "halted": halted, "halt_reason": "drawdown >= hard halt" if halted else None,
        "dd_halfsize_applied": dd >= DD_HALFSIZE and not halted,
        "params": {"risk_per_trade": RISK_PER_TRADE, "stop_pct": STOP_PCT,
                   "dd_halfsize": DD_HALFSIZE, "dd_halt": DD_HALT, "max_position_pct": MAX_POSITION_PCT},
    }


RISK_SIZER = register(Skill(
    unique_name="yeaster_risk_sizer",
    description="Size a position from conviction, equity and drawdown using R-based risk "
                "(0.7%R / 3.5% stop divisor) with drawdown brakes (halve at 9%, halt at 15%) "
                "and a 30% per-name cap. Returns the portfolio fraction + notional.",
    input_schema={"type": "object", "required": ["conviction", "equity_usd"], "properties": {
        "conviction": {"type": "number", "minimum": 0, "maximum": 1},
        "equity_usd": {"type": "number", "minimum": 0},
        "drawdown_pct": {"type": "number", "minimum": 0, "maximum": 1},
    }},
    cost="low", tags=("risk", "sizing", "position"), run=_size,
))


def load_all() -> None:
    """Importing this module registers all five skills (side effect above)."""
