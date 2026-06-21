"""Chat manual-swap approval flow + BNB-for-manual gating."""

from __future__ import annotations

from yeaster.brain import chat
from yeaster.core.universe import is_tradeable, is_whitelisted


def test_manual_ok_allows_whitelist_and_bnb():
    assert chat._manual_ok("CAKE") is True
    assert chat._manual_ok("BNB") is True          # native, manual-only
    assert chat._manual_ok("NOTATOKEN") is False


def test_buy_returns_pending_approval_not_execution():
    out = chat.respond([{"role": "user", "text": "buy 5% CAKE"}], {"guard_enabled": True})
    act = out.get("action") or {}
    assert act.get("type") == "manual_trade_pending"   # never auto-executes
    assert act.get("symbol") == "CAKE" and act.get("side") == "buy"


def test_buy_bnb_allowed_in_chat_manual():
    out = chat.respond([{"role": "user", "text": "buy 5% BNB"}], {"guard_enabled": True})
    act = out.get("action") or {}
    assert act.get("type") == "manual_trade_pending" and act.get("symbol") == "BNB"


def test_sell_returns_pending_approval():
    out = chat.respond([{"role": "user", "text": "sell CAKE"}], {"guard_enabled": True})
    act = out.get("action") or {}
    assert act.get("type") == "manual_trade_pending" and act.get("side") == "sell"


def test_non_whitelisted_non_bnb_rejected_with_guard():
    out = chat.respond([{"role": "user", "text": "buy 5% notatoken"}], {"guard_enabled": True})
    assert out.get("action") is None        # rejected, no trade action


def test_bnb_excluded_from_autonomous_universe():
    # BNB is manual-only: never whitelisted/tradeable for the autonomous loop.
    assert is_whitelisted("BNB") is False
    assert is_tradeable("BNB") is False
