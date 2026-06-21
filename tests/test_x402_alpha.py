"""x402 daily-alpha sales: on-chain verification, anti-replay, 402 gating, alpha pick."""

from __future__ import annotations

from yeaster.execution import x402


# ── on-chain verification (mocked RPC) ───────────────────────────────────────


def _receipt(to_addr, value_wei, *, token=x402.USDT_BSC, status="0x1"):
    topic_to = "0x" + "0" * 24 + to_addr[2:].lower()
    topic_from = "0x" + "0" * 24 + "1" * 40
    return {"status": status, "logs": [{
        "address": token,
        "topics": [x402._TRANSFER_TOPIC, topic_from, topic_to],
        "data": hex(value_wei),
    }]}


def test_verify_onchain_payment_ok(monkeypatch):
    pay_to = "0xA498bd02403161cF5eAfC17CaC76073A279D171C"
    monkeypatch.setattr(x402, "_bsc_rpc", lambda m, p: _receipt(pay_to, 10**17))  # 0.1 USDT (18 dec)
    v = x402.verify_onchain_payment("0xabc", pay_to, 0.10)
    assert v["ok"] is True and abs(v["amount_usd"] - 0.1) < 1e-6


def test_verify_rejects_underpayment(monkeypatch):
    pay_to = "0xA498bd02403161cF5eAfC17CaC76073A279D171C"
    monkeypatch.setattr(x402, "_bsc_rpc", lambda m, p: _receipt(pay_to, 10**16))  # 0.01 < 0.10
    assert x402.verify_onchain_payment("0xabc", pay_to, 0.10)["ok"] is False


def test_verify_rejects_wrong_recipient(monkeypatch):
    monkeypatch.setattr(x402, "_bsc_rpc", lambda m, p: _receipt("0x" + "9" * 40, 10**18))
    assert x402.verify_onchain_payment("0xabc", "0x" + "a" * 40, 0.10)["ok"] is False


def test_anti_replay(tmp_path):
    log = tmp_path / "settle.jsonl"
    assert x402.is_tx_consumed("0xfeed", log) is False
    x402.record_alpha_sale("0xFEED", 0.1, "0xpayer", "0xpayto", log)
    assert x402.is_tx_consumed("0xfeed", log) is True   # case-insensitive


# ── endpoint gating (TestClient) ─────────────────────────────────────────────


def test_alpha_endpoint_402_without_payment(monkeypatch):
    monkeypatch.setenv("YST_X402", "1")
    from fastapi.testclient import TestClient
    from yeaster.api.app import app
    c = TestClient(app)
    r = c.post("/api/x402/alpha", json={})
    assert r.status_code == 402
    body = r.json()
    assert body.get("asset") == "USDT" and "pay_to" in body and body.get("price_usd")


def test_alpha_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.delenv("YST_X402", raising=False)
    from fastapi.testclient import TestClient
    from yeaster.api.app import app
    c = TestClient(app)
    r = c.post("/api/x402/alpha", json={})
    assert r.status_code == 404


# ── alpha selection ──────────────────────────────────────────────────────────


def test_daily_alpha_picks_strongest_graded(monkeypatch):
    from yeaster.brain import alpha
    from yeaster.proof import ledger
    blk = ledger.ProofBlock(
        block_index=1, block_timestamp="2026-06-21T00:00:00Z", previous_block_hash="x",
        block_hash="0xhash", mandate_id="m", final_decision="EXECUTED",
        commit_record={"posture": "hunt", "conviction": 0.7, "rationale": "APE breakout thesis",
                       "ticket": {"to_asset": "APE", "thesis": "t"},
                       "reasoning": {"grade": {"top": [
                           {"symbol": "APE", "composite": 0.52, "coverage": 0.9, "kind": "breakout"},
                           {"symbol": "DOT", "composite": 0.10, "coverage": 0.8, "kind": "rel_strength"},
                       ]}}})
    monkeypatch.setattr(ledger, "load_chain", lambda *a, **k: [blk])
    a = alpha.daily_alpha()
    assert a["available"] and a["symbol"] == "APE"          # highest composite
    assert a["composite"] == 0.52 and a["thesis"] == "APE breakout thesis"
    # teaser hides symbol/thesis but shows quality signals
    t = alpha.teaser(a)
    assert t["locked"] is True and "symbol" not in t and t["composite"] == 0.52
