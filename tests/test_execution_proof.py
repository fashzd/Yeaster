"""Phase 2 parity + integrity tests: indicators, approval permits, paper execution, proof chain."""

from __future__ import annotations

import pytest

from yeaster.execution import twak
from yeaster.execution.approval import (
    ApprovalError,
    issue_approval_token,
    verify_approval_token,
)
from yeaster.execution.models import SwapRequest
from yeaster.execution.twak import TwakBroker
from yeaster.market import indicators as ind
from yeaster.proof import ledger


# ── indicators ───────────────────────────────────────────────────────────────

def test_rsi_all_gains_is_100():
    assert ind.rsi([float(i) for i in range(1, 30)]) == 100.0


def test_rsi_all_losses_is_0():
    assert ind.rsi([float(i) for i in range(30, 1, -1)]) == 0.0


def test_rsi_insufficient_data_none():
    assert ind.rsi([1.0, 2.0, 3.0]) is None


def test_ema_and_macd_shapes():
    series = [float(i) for i in range(1, 60)]
    assert ind.ema(series, 12) is not None
    m = ind.macd(series)
    assert set(m.keys()) == {"macd", "signal", "histogram"}


# ── approval permits ─────────────────────────────────────────────────────────

def _quote(broker: TwakBroker):
    return broker.quote_swap(SwapRequest(from_asset="USDC", to_asset="CAKE", amount_in=100.0))


def test_token_mints_only_on_executed():
    broker = TwakBroker(backend="mock")
    q = _quote(broker)
    with pytest.raises(ApprovalError):
        issue_approval_token(q, final_decision="REJECTED", mandate_id="m1")
    tok = issue_approval_token(q, final_decision="EXECUTED", mandate_id="m1")
    verify_approval_token(tok, q)  # no raise


def test_token_replay_on_other_quote_rejected():
    broker = TwakBroker(backend="mock")
    q1 = _quote(broker)
    q2 = broker.quote_swap(SwapRequest(from_asset="USDC", to_asset="LINK", amount_in=100.0))
    tok = issue_approval_token(q1, final_decision="EXECUTED", mandate_id="m1")
    with pytest.raises(ApprovalError):
        verify_approval_token(tok, q2)


def test_forged_token_rejected():
    broker = TwakBroker(backend="mock")
    q = _quote(broker)
    tok = issue_approval_token(q, final_decision="EXECUTED", mandate_id="m1")
    tok.token = "0xdeadbeef"
    with pytest.raises(ApprovalError):
        verify_approval_token(tok, q)


# ── paper execution ──────────────────────────────────────────────────────────

def test_paper_execution_updates_wallet(tmp_path, monkeypatch):
    monkeypatch.setattr(twak, "PAPER_WALLET_PATH", tmp_path / "paper.json")
    twak.seed_paper(1000.0)
    broker = TwakBroker(backend="paper")
    before = {b.symbol: b.balance for b in broker.portfolio().balances}
    assert before.get("USDC", 0) > 0

    q = broker.quote_swap(SwapRequest(from_asset="USDC", to_asset="CAKE", amount_in=200.0))
    tok = issue_approval_token(q, final_decision="EXECUTED", mandate_id="m1")
    receipt = broker.execute_approved_swap(q, tok)

    assert receipt.status.value == "EXECUTED"
    assert receipt.tx_hash and receipt.tx_hash.startswith("0x")
    after = {b.symbol: b.balance for b in broker.portfolio().balances}
    assert after.get("CAKE", 0) > 0
    assert after["USDC"] < before["USDC"]


def test_paper_insufficient_balance_clean_reject(tmp_path, monkeypatch):
    monkeypatch.setattr(twak, "PAPER_WALLET_PATH", tmp_path / "paper.json")
    twak.seed_paper(50.0, stable="USDC")
    broker = TwakBroker(backend="paper")
    q = broker.quote_swap(SwapRequest(from_asset="USDC", to_asset="CAKE", amount_in=999.0))
    tok = issue_approval_token(q, final_decision="EXECUTED", mandate_id="m1")
    receipt = broker.execute_approved_swap(q, tok)
    assert receipt.status.value == "REJECTED"
    assert "Insufficient" in (receipt.error or "")


# ── proof chain ──────────────────────────────────────────────────────────────

def test_proof_chain_append_and_verify(tmp_path):
    chain = tmp_path / "chain.jsonl"
    for i in range(3):
        ledger.append_proof(
            snapshot={"snapshot_hash": f"0xsnap{i}"},
            commit_record={"posture": "hunt", "conviction": 0.5},
            guard_log={"mandate_id": "m1", "final_decision": "EXECUTED", "rejection_reasons": []},
            chain_path=chain,
        )
    blocks = ledger.load_chain(chain)
    assert len(blocks) == 3
    assert blocks[0].previous_block_hash == "GENESIS"
    assert blocks[1].previous_block_hash == blocks[0].block_hash
    assert ledger.verify_chain(chain) is True


def test_proof_chain_tamper_detected(tmp_path):
    chain = tmp_path / "chain.jsonl"
    ledger.append_proof(
        snapshot={"snapshot_hash": "0xsnap"},
        commit_record={"posture": "hunt"},
        guard_log={"mandate_id": "m1", "final_decision": "EXECUTED"},
        chain_path=chain,
    )
    text = chain.read_text().replace("0xsnap", "0xTAMPERED")
    chain.write_text(text)
    assert ledger.verify_chain(chain) is False
