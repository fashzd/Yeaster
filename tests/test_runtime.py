"""Phase 5: exit reconciliation (stop/TP + trailing) and the autonomous loop."""

from __future__ import annotations

from yeaster.core.models import Mandate
from yeaster.execution import brackets, twak
from yeaster.execution.twak import TwakBroker
from yeaster.market.cmc import build_snapshot
from yeaster.runtime import exits, state as state_mod, tick as tick_mod


def _mandate():
    return Mandate(mandate_id="m", allowed_assets=["BCH", "USDC", "USDT", "CAKE"],
                   max_trade_pct=0.12, max_position_pct=0.30, max_slippage_bps=50, hard_drawdown_pct=0.15)


def test_stop_exit_fires(tmp_path, monkeypatch):
    monkeypatch.setattr(twak, "PAPER_WALLET_PATH", tmp_path / "paper.json")
    monkeypatch.setattr(brackets, "PAPER_AUTO_PATH", tmp_path / "auto.json")
    twak.seed_paper(1000.0)

    snap = build_snapshot("mock")
    by_sym = snap.by_symbol()
    price = by_sym["BCH"].price_usd
    # fund the wallet with the BCH we "hold"
    w = twak._load_paper(); w["balances"]["BCH"] = 3.0; twak._save_paper(w)

    broker = TwakBroker(backend="paper")
    state = dict(state_mod._DEFAULT)
    state["positions"] = {"BCH": {"entry_price": price, "peak_price": price, "qty": 3.0,
                                  "stop_price": price * 1.05, "tp_price": price * 2,  # stop ABOVE price → triggers
                                  "stop_id": None, "tp_id": None}}
    actions = exits.reconcile(state, broker, by_sym, _mandate(), "paper")
    assert any(a["action"].startswith("exit") for a in actions)
    assert "BCH" not in state["positions"]


def test_trailing_stop_ratchets_up(tmp_path, monkeypatch):
    monkeypatch.setattr(twak, "PAPER_WALLET_PATH", tmp_path / "paper.json")
    monkeypatch.setattr(brackets, "PAPER_AUTO_PATH", tmp_path / "auto.json")
    twak.seed_paper(1000.0)
    snap = build_snapshot("mock")
    by_sym = snap.by_symbol()
    price = by_sym["BCH"].price_usd

    broker = TwakBroker(backend="paper")
    state = dict(state_mod._DEFAULT)
    # stop far below price → no exit; trailing should lift it toward price*(1-3%)
    state["positions"] = {"BCH": {"entry_price": price * 0.8, "peak_price": price * 0.8, "qty": 3.0,
                                  "stop_price": price * 0.5, "tp_price": price * 2,
                                  "stop_id": None, "tp_id": None}}
    actions = exits.reconcile(state, broker, by_sym, _mandate(), "paper")
    assert any(a["action"] == "trail" for a in actions)
    assert state["positions"]["BCH"]["stop_price"] > price * 0.5


def test_daemon_run_once(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(twak, "PAPER_WALLET_PATH", tmp_path / "paper.json")
    from yeaster.proof import ledger
    monkeypatch.setattr(ledger, "DEFAULT_CHAIN_PATH", tmp_path / "chain.jsonl")
    twak.seed_paper(1000.0)

    # one autonomous tick in mock/paper completes and seals a verifiable block
    result = tick_mod.run_tick(cmc_backend="mock", twak_backend="paper", arm="det_top")
    assert "proof_block_hash" in result
    assert ledger.verify_chain(tmp_path / "chain.jsonl") is True
