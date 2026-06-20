"""Phase 4: the brain composes offline (no skills) — screen → grade → vet → commit."""

from __future__ import annotations

from yeaster.brain import grade, screen
from yeaster.brain.cycle import think
from yeaster.market.cmc import build_snapshot


def _breakout_bars(base: float = 1.0, n: int = 30) -> list[dict]:
    """Synthesize a clean 20d-high breakout on a volume surge in the last bar."""
    bars = [{"price": base + 0.001 * i, "volume": 1_000.0} for i in range(n - 1)]
    last = bars[-1]["price"] * 1.15
    bars.append({"price": last, "volume": 5_000.0})  # new high + 5x volume
    return bars


def test_screen_detects_breakout():
    snap = build_snapshot("mock")
    live = screen.live_map(snap)
    hist = {"CAKE": _breakout_bars(2.0)}
    cands = screen.screen(live, hist, ["CAKE", "ETH"])
    cake = next((c for c in cands if c["symbol"] == "CAKE"), None)
    assert cake is not None
    assert "breakout" in cake["tags"]
    assert "vol_surge" in cake["tags"]


def test_grade_candidate_shape_offline():
    card = grade.grade_candidate("CAKE", ["breakout", "vol_surge"], posture="selective")
    assert card["symbol"] == "CAKE"
    assert -1.0 <= card["composite"] <= 1.0
    # offline, only the cross-source "detect" dim has data
    assert card["dims"]["detect"]["score"] is not None
    assert "safety" in card and "quality_score" in card["safety"]


def test_think_full_cycle_offline():
    snap = build_snapshot("mock")
    hist = {"CAKE": _breakout_bars(2.0)}

    # det_top has a coverage floor: offline (1/9 dims) it correctly stands down.
    top = think(snap, hist, posture="selective", equity=1000.0, drawdown=0.0,
                arm="det_top", universe=["CAKE", "ETH", "LINK"])
    assert set(top["reasoning"].keys()) >= {"screen", "grade", "vet", "commit"}
    assert top["stand_down"] is True

    # det_safety sizes off safety/coverage without the floor → a real sized ticket.
    safe = think(snap, hist, posture="selective", equity=1000.0, drawdown=0.0,
                 arm="det_safety", universe=["CAKE", "ETH", "LINK"])
    assert safe["ticket"] is not None
    assert safe["ticket"]["to_asset"] == "CAKE"
    assert 0.0 < safe["ticket"]["amount_pct"] <= 0.30


def test_drawdown_halt_blocks_entry():
    snap = build_snapshot("mock")
    hist = {"CAKE": _breakout_bars(2.0)}
    result = think(snap, hist, posture="selective", equity=1000.0, drawdown=0.20,
                   arm="det_safety", universe=["CAKE"])
    assert result["ticket"] is None  # DD_HALT brake


def test_think_stand_down_when_no_candidates():
    snap = build_snapshot("mock")
    result = think(snap, {}, posture="selective", equity=1000.0, arm="det_top", universe=["ETH"])
    assert result["stand_down"] is True
    assert result["ticket"] is None
