"""Tests for the operator controls + decision-pipeline changes:
orphan/all cancellation, LLM-required stand-down, PnL teeth, kill-switch password."""

from __future__ import annotations

import pytest

from yeaster.brain import commit as commit_mod
from yeaster.brain import llm
from yeaster.execution import brackets
from yeaster.runtime import state as state_mod
from yeaster.runtime.daemon import DAEMON, KillSwitchError, _hash


# ── automation cleanup (paper store) ─────────────────────────────────────────


def _place(sym, backend, store):
    spec = brackets.build_bracket_specs(sym, 1.0, 1.0, 2.0, reserve="USDT")["stop"]
    return brackets.place(spec, backend)


def test_cancel_orphans_keeps_tracked(tmp_path, monkeypatch):
    monkeypatch.setattr(brackets, "PAPER_AUTO_PATH", tmp_path / "pa.json")
    _place("CAKE", "paper", tmp_path)     # tracked
    _place("FLOKI", "paper", tmp_path)    # orphan
    n = brackets.cancel_orphans(["CAKE"], "paper")
    assert n == 1
    active = {r["from_asset"] for r in brackets._load() if r.get("status", "ACTIVE") == "ACTIVE"}
    assert "CAKE" in active and "FLOKI" not in active


def test_cancel_all(tmp_path, monkeypatch):
    monkeypatch.setattr(brackets, "PAPER_AUTO_PATH", tmp_path / "pa.json")
    _place("CAKE", "paper", tmp_path)
    _place("FLOKI", "paper", tmp_path)
    assert brackets.cancel_all("paper") == 2
    assert all(r.get("status") != "ACTIVE" for r in brackets._load())


def test_kill_sweeps_all_paper_orphans_when_flat(tmp_path, monkeypatch):
    # The kill switch's end-state: no tracked positions => every paper automation swept.
    monkeypatch.setattr(brackets, "PAPER_AUTO_PATH", tmp_path / "pa.json")
    _place("CAKE", "paper", tmp_path)
    _place("FLOKI", "paper", tmp_path)
    assert brackets.cancel_orphans([], "paper") == 2
    assert all(r.get("status") != "ACTIVE" for r in brackets._load())


# ── LLM is the decisive factor (no silent deterministic substitute) ──────────


def test_llm_lead_stands_down_when_unavailable(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    cards = [{"symbol": "CAKE", "composite": 0.5, "coverage": 0.9, "kind": "breakout",
              "safety": {}, "dims": {}, "detect_tags": []}]
    d = commit_mod.commit(cards, arm="llm_lead", posture="selective", equity=1000.0, drawdown=0.0, book={})
    assert d["pick"] is None
    assert d["arm"] == "llm_lead:unavailable"
    assert d.get("alert") == "llm_unavailable"


# ── PnL teeth ────────────────────────────────────────────────────────────────


def test_loss_haircut_grades():
    assert commit_mod._loss_haircut({"consecutive_losses": 0}) == 1.0
    assert commit_mod._loss_haircut({"consecutive_losses": 3}) == 0.6
    assert commit_mod._loss_haircut({"consecutive_losses": 5}) == 0.4


def test_det_top_size_shrinks_on_loss_streak():
    cards = [{"symbol": "CAKE", "composite": 0.5, "coverage": 0.9, "kind": "breakout", "safety": {}}]
    base = commit_mod.arm_det_top(cards, "selective", 1000.0, 0.0, {})
    cold = commit_mod.arm_det_top(cards, "selective", 1000.0, 0.0, {"consecutive_losses": 5})
    assert cold["conviction"] < base["conviction"]


def test_state_tracks_streak_and_daily_pnl():
    st = {**state_mod._DEFAULT, "positions": {}}
    state_mod.record_exit(st, "A", pnl_usd=-1.0, reason="stop")
    state_mod.record_exit(st, "B", pnl_usd=-2.0, reason="stop")
    assert st["consecutive_losses"] == 2
    assert st["realized_pnl_today"] == -3.0
    state_mod.record_exit(st, "C", pnl_usd=5.0, reason="tp")
    assert st["consecutive_losses"] == 0
    book = state_mod.book_for_llm(st, 1000.0, 0.0)
    assert book["consecutive_losses"] == 0
    assert book["realized_pnl_today"] == 2.0


# ── kill-switch password gate ────────────────────────────────────────────────


def test_paper_live_state_isolation(tmp_path, monkeypatch):
    from yeaster.runtime import state as s
    monkeypatch.setattr(s, "_STATE_DIR", tmp_path)
    s.save({**s._DEFAULT, "peak_equity_usd": 111.0, "positions": {"CAKE": {}}}, "paper")
    s.save({**s._DEFAULT, "peak_equity_usd": 999.0, "positions": {"INJ": {}}}, "live")
    assert s.load("paper")["peak_equity_usd"] == 111.0
    assert s.load("live")["peak_equity_usd"] == 999.0
    assert list(s.load("paper")["positions"]) == ["CAKE"]   # no cross-bleed
    assert list(s.load("live")["positions"]) == ["INJ"]
    assert (tmp_path / "agent_state_paper.json").exists()
    assert (tmp_path / "agent_state_live.json").exists()


def test_state_mode_mapping():
    from yeaster.runtime import state as s
    assert s.state_mode("paper") == "paper"
    assert s.state_mode("mock") == "paper"     # gate-closed/test env → paper


def test_dust_floor_stands_down_on_tiny_equity():
    # Below the contest floor an organic entry is dust → stand down, don't trade.
    assert commit_mod.size_amount_pct(1.0, 2.0, 0.0) is None     # full conviction, ~$0.40 notional < $1.20
    # A well-funded wallet sizes normally.
    amt = commit_mod.size_amount_pct(1.0, 1000.0, 0.0)
    assert amt is not None and amt > 0


def test_compliance_trade_clears_contest_minimum():
    # The mandatory ≥1/day trade must size UP to clear $1.20 regardless of wallet size.
    for eq in (10.0, 20.0, 5.0):
        pct = commit_mod.compliance_amount_pct(eq)
        assert pct is not None, f"compliance must place a trade at ${eq}"
        assert pct * eq >= 1.20, f"compliance notional ${pct*eq:.2f} below $1.20 at ${eq} equity"
    # An empty wallet genuinely can't comply.
    assert commit_mod.compliance_amount_pct(1.0) is None         # $1.56 target > 95% of $1


def test_brackets_reserve_is_usdt_not_usdc():
    # The on-chain stop/TP legs must sell into the funded USDT reserve, not USDC.
    specs = brackets.build_bracket_specs("CAKE", 1.0, 1.0, 2.0)
    assert specs["stop"].to_asset == "USDT"
    assert specs["take_profit"].to_asset == "USDT"


def test_onchain_sweep_surfaces_untracked_holdings(monkeypatch):
    # The TWAK CLI omits untracked ERC-20s; the on-chain sweep must merge them in
    # with a REAL price (never a mock) and recompute the total.
    from yeaster.execution import twak
    from yeaster.execution.models import PortfolioState, TokenBalance

    pf = PortfolioState(address="0xWALLET", chain_id=56, native_balance=0.0,
                        balances=[TokenBalance(symbol="USDT", balance=2.0, value_usd=2.0)],
                        total_value_usd=2.0, positions_pct={"USDT": 1.0}, captured_at="2026-06-21T00:00:00Z")
    monkeypatch.setattr(twak, "_universe_contracts", lambda: {"CAKE": "0xcake", "DEAD": "0xdead"})
    monkeypatch.setattr(twak, "_multicall3_balanceof",
                        lambda addr, contracts: {"0xcake": 5 * 10 ** 18, "0xdead": 0})
    monkeypatch.setattr(twak, "_erc20_decimals", lambda c: 18)
    monkeypatch.setattr(twak, "_sweep_prices", lambda syms: {"CAKE": 2.0})
    twak._sweep_cache.clear()

    out = twak._merge_onchain_holdings(pf, "0xWALLET", 56)
    held = {b.symbol: b for b in out.balances}
    assert "CAKE" in held and abs(held["CAKE"].balance - 5.0) < 1e-9
    assert abs(held["CAKE"].value_usd - 10.0) < 1e-6          # 5 * $2, REAL price
    assert "DEAD" not in held                                  # zero balance dropped
    assert abs(out.total_value_usd - 12.0) < 1e-6             # 2 + 10


def test_onchain_sweep_skips_off_mainnet_and_unvalued_not_fabricated(monkeypatch):
    from yeaster.execution import twak
    from yeaster.execution.models import PortfolioState, TokenBalance

    pf = PortfolioState(address="0xW", chain_id=97, native_balance=0.0,
                        balances=[TokenBalance(symbol="USDT", balance=2.0, value_usd=2.0)],
                        total_value_usd=2.0, positions_pct={"USDT": 1.0}, captured_at="2026-06-21T00:00:00Z")
    # off mainnet (chain 97) → untouched
    assert twak._merge_onchain_holdings(pf, "0xW", 97) is pf
    # on mainnet, a token with no real price is shown but UNVALUED (not mock-priced)
    monkeypatch.setattr(twak, "_universe_contracts", lambda: {"FLOKI": "0xfloki"})
    monkeypatch.setattr(twak, "_multicall3_balanceof", lambda a, c: {"0xfloki": 1409 * 10 ** 9})
    monkeypatch.setattr(twak, "_erc20_decimals", lambda c: 9)
    monkeypatch.setattr(twak, "_sweep_prices", lambda syms: {})   # CMC/oracle both miss
    twak._sweep_cache.clear()
    pf56 = pf.model_copy(update={"chain_id": 56})
    out = twak._merge_onchain_holdings(pf56, "0xW", 56)
    floki = {b.symbol: b for b in out.balances}["FLOKI"]
    assert floki.value_usd is None                              # NOT fabricated to ~$50k
    assert abs(out.total_value_usd - 2.0) < 1e-6               # unvalued token doesn't inflate total


def test_ensure_sell_approval_noop_off_mainnet():
    # Off live mainnet (chain 97), approval is a safe no-op (no CLI calls).
    from yeaster.execution import twak
    out = twak.ensure_sell_approval("CAKE", 97)
    assert out.get("skipped") is True and out.get("ok") is False


def test_kill_switch_password_gate():
    locked = {"locked": True, "kill_hash": _hash("secret")}
    DAEMON._check_password(locked, "secret")              # correct → no raise
    DAEMON._check_password({"locked": False}, None)       # unlocked, no operator pw → no raise
    with pytest.raises(KillSwitchError):
        DAEMON._check_password(locked, "wrong")
    with pytest.raises(KillSwitchError):
        DAEMON._check_password(locked, None)


def test_operator_password_gates_kill_not_casual_stop(monkeypatch):
    from yeaster.core import settings as settings_mod

    class _S:
        operator_password = "opsecret"

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _S())
    # the KILL switch (require=True) always needs the operator password
    DAEMON._check_password({"locked": False}, "opsecret", require=True)
    with pytest.raises(KillSwitchError):
        DAEMON._check_password({"locked": False}, None, require=True)
    with pytest.raises(KillSwitchError):
        DAEMON._check_password({"locked": False}, "wrong", require=True)
    # a casual stop of an UNLOCKED loop (power toggle) needs no password
    DAEMON._check_password({"locked": False}, None)
    # unlocking a LOCKED run needs the password (operator pw also works)
    with pytest.raises(KillSwitchError):
        DAEMON._check_password({"locked": True, "kill_hash": _hash("runpw")}, None)
    DAEMON._check_password({"locked": True, "kill_hash": _hash("runpw")}, "opsecret")
