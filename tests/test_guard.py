"""Phase 3: firewall checks, de-risk carve-out, Safe-Mode latch, token safety."""

from __future__ import annotations

from yeaster.core.models import Mandate, OrderTicket
from yeaster.guard.firewall import RuntimeState, YeasterGuard
from yeaster.guard.token_safety import build_token_safety_checks, evaluate_with_token_safety


def _mandate(**kw) -> Mandate:
    base = dict(mandate_id="m1", allowed_assets=["CAKE", "ETH", "USDC", "USDT"],
                max_trade_pct=0.12, max_position_pct=0.30, max_slippage_bps=50, hard_drawdown_pct=0.15)
    base.update(kw)
    return Mandate(**base)


def _entry(to="CAKE", amount_pct=0.10):
    return OrderTicket(from_asset="USDC", to_asset=to, amount_pct=amount_pct, confidence=0.7, thesis="t")


def test_clean_entry_executes():
    g = YeasterGuard(_mandate())
    log = g.evaluate(_entry(), RuntimeState(requested_slippage_bps=20, current_positions={"USDC": 1.0}))
    assert log.final_decision.value == "EXECUTED"


def test_offlist_asset_rejected():
    g = YeasterGuard(_mandate())
    log = g.evaluate(_entry(to="SCAMCOIN"), RuntimeState(current_positions={"USDC": 1.0}))
    assert log.final_decision.value == "REJECTED"
    assert "allowlist" in log.rejection_reasons


def test_slippage_cap_rejects():
    g = YeasterGuard(_mandate())
    log = g.evaluate(_entry(), RuntimeState(requested_slippage_bps=80, current_positions={"USDC": 1.0}))
    assert "slippage_limit" in log.rejection_reasons


def test_trade_cap_rejects_oversize():
    g = YeasterGuard(_mandate(max_trade_pct=0.05))
    # 50% of a USDC sleeve that is 100% of the book = 50% portfolio fraction
    log = g.evaluate(_entry(amount_pct=0.5), RuntimeState(current_positions={"USDC": 1.0}))
    assert "max_trade_limit" in log.rejection_reasons


def test_hard_drawdown_latches_safe_mode_and_blocks_entry():
    g = YeasterGuard(_mandate())
    log = g.evaluate(_entry(), RuntimeState(portfolio_drawdown_pct=0.20, current_positions={"USDC": 1.0}))
    assert log.final_decision.value == "REJECTED"
    assert "hard_drawdown" in log.rejection_reasons
    assert log.safe_mode_active is True


def test_de_risk_exit_allowed_under_safe_mode():
    g = YeasterGuard(_mandate(), safe_mode_latched=True)
    exit_ticket = OrderTicket(from_asset="CAKE", to_asset="USDC", amount_pct=1.0, confidence=1.0, thesis="exit")
    log = g.evaluate(exit_ticket, RuntimeState(current_positions={"CAKE": 0.3}))
    assert log.final_decision.value == "EXECUTED"  # exit never trapped


def test_de_risk_exit_exceeds_caps_but_passes():
    g = YeasterGuard(_mandate(max_trade_pct=0.05))
    exit_ticket = OrderTicket(from_asset="ETH", to_asset="USDC", amount_pct=1.0, confidence=1.0, thesis="exit")
    log = g.evaluate(exit_ticket, RuntimeState(current_positions={"ETH": 0.3}))
    assert log.final_decision.value == "EXECUTED"


# ── token safety ─────────────────────────────────────────────────────────────

def test_token_safety_missing_data_fails():
    checks = build_token_safety_checks("CAKE", whale_concentration_pct=None, liquidity_usd=None)
    assert checks["whale_concentration"].passed is False
    assert checks["liquidity_floor"].passed is False


def test_token_safety_stable_exempt_from_whale():
    checks = build_token_safety_checks("USDT", whale_concentration_pct=95.0, liquidity_usd=5_000_000.0)
    assert checks["whale_concentration"].passed is True


def test_token_safety_merges_and_rejects():
    g = YeasterGuard(_mandate())
    log = g.evaluate(_entry(), RuntimeState(requested_slippage_bps=10, current_positions={"USDC": 1.0}))
    assert log.final_decision.value == "EXECUTED"
    merged = evaluate_with_token_safety(log, "CAKE", token_profile={"whale_concentration_pct": 80.0, "liquidity_usd": 10.0})
    assert merged.final_decision.value == "REJECTED"
    assert "whale_concentration" in merged.rejection_reasons
    assert "liquidity_floor" in merged.rejection_reasons
