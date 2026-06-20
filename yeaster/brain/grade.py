"""GRADE — the second reasoning pass: grade every candidate across all dimensions.

A PURE grader: it NEVER discards a candidate. Produces a coverage-weighted
composite over directional dimensions, plus a SEPARATE zero-weight safety axis
(token quality) that is surfaced but never moves the composite — the SIREN fix.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from yeaster.brain import dimensions as dim
from yeaster.market import skills

WORKERS = 10

# name -> (wrapper, base_weight). "transition" is routed; "detect" is computed locally.
DIRECTIONAL_DIMS: dict[str, tuple[Optional[Callable[[str], dict]], float]] = {
    "kline":      (dim.kline_quality,   1.0),
    "perp":       (dim.perp_dim,        1.0),
    "dark_flow":  (dim.oi_dark_flow,    0.8),
    "transition": (None,                1.0),
    "sentiment":  (dim.kol_sentiment,   0.6),
    "sector":     (dim.sector_rotation, 0.8),
    "whale":      (dim.whale_flow,      0.7),
    "unlock":     (dim.unlock_impact,   0.6),
}

REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "hunt":       {"_mult": 1.0},
    "selective":  {"_mult": 0.85, "sector": 1.3, "whale": 1.2, "kline": 1.1},
    "stand_down": {"_mult": 0.6, "sector": 1.4, "whale": 1.3, "perp": 0.7, "dark_flow": 1.2},
}

ROUTING_WEIGHTS: dict[str, dict[str, float]] = {
    "breakout":     {"transition": 1.2, "dark_flow": 1.2, "kline": 1.1},
    "mean_revert":  {"kline": 1.3, "whale": 1.3, "sector": 1.2, "transition": 0.4},
    "rel_strength": {"sector": 1.4, "whale": 1.1},
}

_MEAN_REVERT_TAGS = {"mean_revert", "oversold", "vol_surge"}
_BREAKOUT_TAGS = {"breakout", "accumulation", "breaking_out", "extended_runner"}


def candidate_kind(tags: list[str]) -> str:
    t = {str(x).lower() for x in tags}
    if t & _MEAN_REVERT_TAGS and not (t & _BREAKOUT_TAGS):
        return "mean_revert"
    if "rel_strength" in t or "decoupled" in t:
        return "rel_strength"
    return "breakout"


def grade_candidate(symbol: str, detect_tags: Optional[list[str]] = None,
                    posture: str = "selective", dims: Optional[dict] = None) -> dict[str, Any]:
    """Grade ONE candidate across all directional dims + the separate safety axis."""
    detect_tags = sorted({str(t) for t in (detect_tags or [])})
    kind = candidate_kind(detect_tags)
    reg_w = REGIME_WEIGHTS.get(posture, {})
    route_w = ROUTING_WEIGHTS.get(kind, {})

    active = (
        {n: (DIRECTIONAL_DIMS[n][0], float(w)) for n, w in dims.items() if n in DIRECTIONAL_DIMS}
        if dims else dict(DIRECTIONAL_DIMS)
    )

    skills_on = skills.available()

    def run_dim(item):
        name, (fn, _w) = item
        if not skills_on:               # offline: count the dim as attempted-but-no-data, skip network
            return name, dim.pack(None, 0)
        if name == "transition":
            return name, dim.transition_dim(symbol, kind)
        try:
            return name, fn(symbol)
        except Exception as e:
            return name, dim.pack(None, 0, error=f"{type(e).__name__}: {str(e)[:60]}")

    with ThreadPoolExecutor(max_workers=max(1, len(active) + 1)) as ex:
        safety_future = ex.submit(skills.token_quality, symbol) if skills_on else None
        results = dict(ex.map(run_dim, active.items()))
    safety = safety_future.result() if safety_future else {
        "quality_score": 0.0, "coverage": 0.0, "risk_flags": [], "evidence": {}}

    agree = max(len(detect_tags) - 1, 0)
    results["detect"] = dim.pack(min(1.0, agree / 3.0), 1 if detect_tags else 0, tags=detect_tags)

    num = den = 0.0
    cov_hit = cov_tot = 0
    dims_out: dict[str, Any] = {}
    weights = {**{k: v[1] for k, v in active.items()}, "detect": 0.7}
    for name, r in results.items():
        base = weights.get(name, 1.0)
        w = base * reg_w.get(name, 1.0) * route_w.get(name, 1.0)
        cov = r.get("coverage") or 0
        cov_tot += 1
        if r.get("score") is not None and cov:
            cov_hit += 1
            num += w * r["score"] * cov
            den += w * cov
        dims_out[name] = {"score": r.get("score"), "coverage": cov,
                          "weight": round(w, 3), "evidence": r.get("evidence", {})}

    reg_mult = reg_w.get("_mult", 1.0)
    composite = (num / den * reg_mult) if den > 1e-9 else 0.0
    coverage = cov_hit / cov_tot if cov_tot else 0.0

    return {
        "symbol": symbol, "kind": kind, "composite": round(composite, 4),
        "coverage": round(coverage, 3), "detect_tags": detect_tags, "dims": dims_out,
        "safety": {"quality_score": safety["quality_score"], "coverage": safety["coverage"],
                   "risk_flags": safety["risk_flags"], "evidence": safety["evidence"]},
    }


def grade_all(candidates: list[dict], posture: str = "selective",
              dims: Optional[dict] = None) -> list[dict[str, Any]]:
    """Grade EVERY candidate concurrently. Never drops one. Ranked by composite desc."""
    syms = [(c.get("symbol"), c.get("tags") or c.get("detect_tags") or []) for c in candidates]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        cards = list(ex.map(lambda s: grade_candidate(s[0], s[1], posture, dims), syms))
    cards.sort(key=lambda p: p["composite"], reverse=True)
    return cards
