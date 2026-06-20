"""CYCLE — the deterministic stage runner: one agent thinking in passes.

``think`` runs screen → grade → vet → commit and returns a structured decision
plus a reasoning trace. ``think_events`` yields the same work as a stream of
thoughts (for the live terminal), ending with a ``result`` event. This is genuine
internal orchestration — sequential reasoning passes of ONE mind, not a roster
of agents.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

from yeaster.brain import commit as commit_pass
from yeaster.brain import grade as grade_pass
from yeaster.brain import screen as screen_pass
from yeaster.brain import vet as vet_pass
from yeaster.core.settings import get_settings
from yeaster.core.universe import UNIVERSE


def _top(cards: list[dict], n: int = 6) -> list[dict]:
    return [{"symbol": c["symbol"], "composite": c["composite"], "coverage": c["coverage"], "kind": c["kind"]}
            for c in cards[:n]]


def _run(snapshot, hist: dict[str, list[dict]], *, posture: str, equity: float, drawdown: float,
         book: dict, arm: str, grade_cap: int, universe, detectors=None, dims=None) -> Iterator[tuple[str, dict]]:
    """Internal generator: yields (stage, payload) thoughts, then ('result', full)."""
    universe = universe or UNIVERSE

    # 1) SCREEN (restricted to the strategy's detector set)
    live = screen_pass.live_map(snapshot)
    candidates = screen_pass.screen(live, hist, universe, enabled=detectors)
    detectors: dict[str, int] = {}
    for c in candidates:
        for t in c["tags"]:
            detectors[t] = detectors.get(t, 0) + 1
    yield "screen", {"text": f"screened {len(candidates)} candidates from {len(live)} assets",
                     "count": len(candidates), "detectors": detectors,
                     "candidates": [c["symbol"] for c in candidates[:12]]}

    if not candidates:
        result = _result(posture, [], [], None, {"notes": "no candidates"}, [], "no candidates surfaced")
        yield "result", result
        return

    capped = candidates[:grade_cap]

    # 2) GRADE (strategy dimension weights)
    cards = grade_pass.grade_all(capped, posture, dims=dims)
    yield "grade", {"text": f"graded {len(cards)} candidates", "top": _top(cards)}

    # 3) VET
    v = vet_pass.vet(cards, posture=posture)
    yield "vet", {"text": f"{len(v['survivors'])} survived, {len(v['blocked'])} hard-blocked",
                  "blocked": v["blocked"], "refuted": v["refuted"], "notes": v["notes"]}

    # 4) COMMIT
    decision = commit_pass.commit(v["survivors"], arm=arm, posture=posture,
                                  equity=equity, drawdown=drawdown, book=book)
    if decision.get("ticket"):
        t = decision["ticket"]
        msg = f"commit {t['amount_pct']:.1%} → {t['to_asset']} (conviction {decision['conviction']:.2f})"
    else:
        msg = f"stand down — {decision.get('rationale', 'no clean trade')[:80]}"
    yield "commit", {"text": msg, "pick": decision.get("pick"), "conviction": decision.get("conviction"),
                     "arm": decision.get("arm"), "ticket": decision.get("ticket")}

    result = _result(posture, _top(cards, 8), v["blocked"], decision.get("ticket"), v, decision["considered"],
                     decision.get("rationale", ""), decision=decision, refuted=v["refuted"])
    yield "result", result


def _result(posture, graded_top, blocked, ticket, vet_out, considered, rationale,
            decision: Optional[dict] = None, refuted=None) -> dict[str, Any]:
    return {
        "posture": posture,
        "graded_top": graded_top,
        "blocked": blocked,
        "considered": considered,
        "refuted": refuted or [],
        "ticket": ticket,
        "pick": (decision or {}).get("pick"),
        "conviction": (decision or {}).get("conviction", 0.0),
        "arm": (decision or {}).get("arm"),
        "rationale": rationale,
        "stand_down": ticket is None,
    }


def think(snapshot, hist: dict[str, list[dict]], *, posture: str = "selective", equity: float = 0.0,
          drawdown: float = 0.0, book: Optional[dict] = None, arm: Optional[str] = None,
          grade_cap: Optional[int] = None, universe=None, detectors=None, dims=None) -> dict[str, Any]:
    """Run the full cycle and return the final result + a reasoning trace."""
    s = get_settings()
    arm = arm or s.commit_arm
    grade_cap = grade_cap or s.grade_cap
    trace: dict[str, Any] = {}
    result: dict[str, Any] = {}
    for stage, payload in _run(snapshot, hist, posture=posture, equity=equity, drawdown=drawdown,
                               book=book or {}, arm=arm, grade_cap=grade_cap, universe=universe,
                               detectors=detectors, dims=dims):
        if stage == "result":
            result = payload
        else:
            trace[stage] = payload
    result["reasoning"] = trace
    return result


def think_events(snapshot, hist: dict[str, list[dict]], *, posture: str = "selective", equity: float = 0.0,
                 drawdown: float = 0.0, book: Optional[dict] = None, arm: Optional[str] = None,
                 grade_cap: Optional[int] = None, universe=None, detectors=None, dims=None) -> Iterator[tuple[str, dict]]:
    """Stream the cycle as (stage, payload) thoughts for the live terminal."""
    s = get_settings()
    yield from _run(snapshot, hist, posture=posture, equity=equity, drawdown=drawdown, book=book or {},
                    arm=arm or s.commit_arm, grade_cap=grade_cap or s.grade_cap, universe=universe,
                    detectors=detectors, dims=dims)
