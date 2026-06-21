"""Track 2: the five strategy skills register, run, and return valid evidence packs."""

from __future__ import annotations

import yeaster.skills.catalog  # noqa: F401  (registers skills)
from yeaster.skills import base as skills


def test_all_five_registered():
    names = {s.unique_name for s in skills.all_skills()}
    assert names == {
        "yeaster_conviction_grader", "yeaster_momentum_screener", "yeaster_trap_vetter",
        "yeaster_bracket_planner", "yeaster_risk_sizer",
    }


def test_manifest_has_schemas():
    for m in skills.manifest():
        assert m["unique_name"] and m["description"] and m["input_schema"]["type"] == "object"
        assert m["cost"] in ("low", "medium", "high")


def test_bracket_planner_uses_preset_calibration():
    out = skills.invoke("yeaster_bracket_planner", {"entry_price": 100.0})
    assert out["ok"]
    d = out["data"]
    assert d["stop_price"] == 92.0          # 8% stop
    assert d["take_profit_price"] == 140.0  # 40% wide backstop (re-tuned)
    assert d["risk_reward"] == 5.0          # (140-100)/(100-92)


def test_risk_sizer_rails_and_halt():
    ok = skills.invoke("yeaster_risk_sizer", {"conviction": 0.6, "equity_usd": 1000.0, "drawdown_pct": 0.0})
    assert ok["ok"] and 0 < ok["data"]["amount_pct"] <= 0.30
    halted = skills.invoke("yeaster_risk_sizer", {"conviction": 0.6, "equity_usd": 1000.0, "drawdown_pct": 0.2})
    assert halted["data"]["halted"] is True and halted["data"]["amount_pct"] is None


def test_conviction_grader_offline_shape():
    out = skills.invoke("yeaster_conviction_grader", {"symbol": "CAKE", "tags": ["breakout", "vol_surge"]})
    assert out["ok"]
    d = out["data"]
    assert d["symbol"] == "CAKE"
    assert -1.0 <= d["composite"] <= 1.0
    assert "safety" in d and "dims" in d


def test_trap_vetter_offline_clears_clean_token():
    out = skills.invoke("yeaster_trap_vetter", {"symbol": "ETH"})
    assert out["ok"]
    assert out["data"]["verdict"] in ("CLEAR", "BLOCK")
    assert "hard_block_flags" in out["data"]


def test_unknown_skill_fails_cleanly():
    out = skills.invoke("nope", {})
    assert out["ok"] is False and "error" in out["data"]
