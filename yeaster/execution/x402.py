"""Binance x402 micropayment middleware.

Implements the HTTP-402 "Payment Required" standard so the agent can settle
per-request fees for premium analytical data (e.g. premium CMC skills) inside its
own loop — a TWAK hackathon capability.

Two modes, one interceptor:
  * **eager** — every request to a paid endpoint carries a pre-signed
    ``X-PAYMENT`` header ($0.01 USDC/request by default).
  * **challenge** — on a ``402`` with payment requirements, sign an authorization
    matching the challenge and retry once.

Self-custody: authorizations are HMAC-SHA256 signed locally with ``YST_X402_SECRET``
(host-isolated, never a cloud signer). Every settlement appends a hashed
``PaymentReceipt`` to ``data/proof/x402_settlements.jsonl`` — the micropayment
trail is part of the mission's audit evidence. Enable with ``YST_X402=1``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTLEMENT_LOG_PATH = REPO_ROOT / "data" / "proof" / "x402_settlements.jsonl"

X402_VERSION = "1"
X402_SCHEME = "exact"
_DEV_SECRET = "yeaster-dev-x402-secret"
DEFAULT_PAY_TO = "0xC0FFEE00000000000000000000000000000000CC"


class X402Error(Exception):
    """Payment could not be authorized or settled."""


class X402Config(BaseModel):
    price_usd: float = Field(default=0.01, gt=0)
    asset: str = "USDC"
    network: str = "bsc"
    pay_to: str = DEFAULT_PAY_TO
    payer: str = "yeaster-agent-wallet"
    max_price_usd: float = Field(default=0.05, gt=0)


class PaymentReceipt(BaseModel):
    request_id: str
    url: str
    mode: str           # 'eager' | 'challenge'
    amount_usd: float
    asset: str
    network: str
    payer: str
    pay_to: str
    nonce: str
    signed_at: str
    signature: str
    receipt_hash: Optional[str] = None


def enabled() -> bool:
    return os.getenv("YST_X402", "").strip().lower() in {"1", "true", "yes", "on"}


def _secret() -> bytes:
    return os.environ.get("YST_X402_SECRET", _DEV_SECRET).encode()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sign_payment_payload(payload: dict[str, Any]) -> str:
    return "0x" + hmac.new(_secret(), _canonical(payload).encode(), hashlib.sha256).hexdigest()


def build_payment_header(url: str, config: X402Config, nonce: Optional[str] = None,
                         amount_usd: Optional[float] = None, pay_to: Optional[str] = None) -> tuple[str, dict]:
    signed_at = _now_iso()
    nonce = nonce or hashlib.sha256(f"{url}:{signed_at}".encode()).hexdigest()[:16]
    auth = {
        "x402Version": X402_VERSION, "scheme": X402_SCHEME, "network": config.network,
        "asset": config.asset, "amountUsd": round(amount_usd if amount_usd is not None else config.price_usd, 6),
        "payTo": pay_to or config.pay_to, "payer": config.payer, "resource": url,
        "nonce": nonce, "signedAt": signed_at,
    }
    auth["signature"] = sign_payment_payload({k: v for k, v in auth.items() if k != "signature"})
    return base64.b64encode(_canonical(auth).encode()).decode(), auth


def verify_payment_header(header: str) -> bool:
    payload = json.loads(base64.b64decode(header.encode()).decode())
    sig = payload.pop("signature", None)
    return sig == sign_payment_payload(payload)


def _finalize(receipt: PaymentReceipt) -> PaymentReceipt:
    body = receipt.model_dump()
    body.pop("receipt_hash", None)
    receipt.receipt_hash = "0x" + hashlib.sha256(_canonical(body).encode()).hexdigest()
    return receipt


def append_settlement(receipt: PaymentReceipt, log_path: Path = SETTLEMENT_LOG_PATH) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as fh:
        fh.write(receipt.model_dump_json() + "\n")
    return log_path


def list_settlements(limit: int = 50, log_path: Path = SETTLEMENT_LOG_PATH) -> list[dict]:
    if not log_path.exists():
        return []
    rows = [json.loads(ln) for ln in log_path.read_text().splitlines() if ln.strip()]
    return rows[-limit:]


# ── Real on-chain payment verification (selling the daily alpha) ─────────────
# Buyers pay in USDT on BSC; the server verifies the transfer before releasing the
# alpha. This is the *inbound* (seller) side of x402, vs. the outbound interceptor.
USDT_BSC = "0x55d398326f99059fF775485246999027B3197955"   # 18 decimals on BSC
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
_BSC_RPCS = ("https://bsc-dataseed.binance.org/", "https://bsc-dataseed1.defibit.io/")


def alpha_price_usd() -> float:
    try:
        return float(os.environ.get("YST_X402_PRICE_USD", "0.10"))
    except ValueError:
        return 0.10


def alpha_pay_to() -> str:
    return (os.environ.get("YST_X402_PAYTO") or os.environ.get("YST_AGENT_WALLET")
            or os.environ.get("BSC_TESTNET_WALLET_ADDRESS") or DEFAULT_PAY_TO)


def _bsc_rpc(method: str, params: list) -> Any:
    import requests
    for url in _BSC_RPCS:
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=15)
            r.raise_for_status()
            return r.json().get("result")
        except Exception:
            continue
    return None


def is_tx_consumed(tx_hash: str, log_path: Path = SETTLEMENT_LOG_PATH) -> bool:
    """True if this payment tx was already redeemed (anti-replay)."""
    th = (tx_hash or "").lower()
    return any((row.get("tx_hash") or "").lower() == th for row in list_settlements(100_000, log_path))


def verify_onchain_payment(tx_hash: str, pay_to: str, min_usd: float, *, token: str = USDT_BSC) -> dict:
    """Verify a real BSC ERC-20 (USDT) transfer of >= ``min_usd`` to ``pay_to`` in
    ``tx_hash``. Returns {ok, amount_usd, payer, reason}."""
    if not tx_hash or not str(tx_hash).startswith("0x"):
        return {"ok": False, "reason": "missing or invalid tx hash"}
    rcpt = _bsc_rpc("eth_getTransactionReceipt", [tx_hash])
    if not rcpt:
        return {"ok": False, "reason": "tx not found or not yet mined"}
    if str(rcpt.get("status", "")).lower() not in ("0x1", "1"):
        return {"ok": False, "reason": "tx reverted on-chain"}
    pay_to_l, token_l = pay_to.lower(), token.lower()
    for log in rcpt.get("logs", []):
        if str(log.get("address", "")).lower() != token_l:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3 or str(topics[0]).lower() != _TRANSFER_TOPIC:
            continue
        if ("0x" + topics[2][-40:]).lower() != pay_to_l:
            continue
        value = int(log.get("data", "0x0"), 16) / 1e18   # USDT on BSC = 18 decimals
        if value + 1e-9 >= min_usd:
            return {"ok": True, "amount_usd": round(value, 6), "payer": "0x" + topics[1][-40:]}
    return {"ok": False, "reason": f"no USDT transfer >= ${min_usd} to {pay_to} found in tx"}


def record_alpha_sale(tx_hash: str, amount_usd: float, payer: str, pay_to: str,
                      log_path: Path = SETTLEMENT_LOG_PATH) -> dict:
    rec = {"kind": "alpha_sale", "tx_hash": tx_hash, "amount_usd": round(amount_usd, 6),
           "payer": payer, "pay_to": pay_to, "asset": "USDT", "network": "bsc", "at": _now_iso()}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def total_settled_usd(log_path: Path = SETTLEMENT_LOG_PATH) -> float:
    return round(sum(float(r.get("amount_usd", 0)) for r in list_settlements(10_000, log_path)), 6)


class X402Interceptor:
    def __init__(self, config: Optional[X402Config] = None, transport: Optional[Callable[..., Any]] = None,
                 log_path: Path = SETTLEMENT_LOG_PATH) -> None:
        self.config = config or X402Config()
        self.log_path = log_path
        if transport is None:
            import requests

            def transport(method, url, json_body, headers, timeout):  # noqa: ANN001
                return requests.request(method, url, json=json_body, headers=headers, timeout=timeout)
        self.transport = transport

    def request(self, method: str, url: str, json_body: Optional[dict] = None,
                headers: Optional[dict[str, str]] = None, timeout: int = 120, eager: bool = True):
        headers = dict(headers or {})
        if eager:
            header, auth = build_payment_header(url, self.config)
            headers["X-PAYMENT"] = header
            headers["X-PAYMENT-SCHEME"] = X402_SCHEME
            response = self.transport(method, url, json_body, headers, timeout)
            if response.status_code != 402:
                self._settle(url, "eager", auth)
                return response
        else:
            response = self.transport(method, url, json_body, headers, timeout)
            if response.status_code != 402:
                return response

        challenge = self._parse_challenge(response)
        amount = float(challenge.get("amountUsd", self.config.price_usd))
        if amount > self.config.max_price_usd:
            raise X402Error(f"Provider demands ${amount}, above ceiling ${self.config.max_price_usd}; refusing.")
        header, auth = build_payment_header(url, self.config, nonce=challenge.get("nonce"),
                                            amount_usd=amount, pay_to=challenge.get("payTo"))
        headers["X-PAYMENT"] = header
        headers["X-PAYMENT-SCHEME"] = str(challenge.get("scheme", X402_SCHEME))
        retried = self.transport(method, url, json_body, headers, timeout)
        if retried.status_code == 402:
            raise X402Error(f"Payment not accepted by {url} after challenge retry.")
        self._settle(url, "challenge", auth)
        return retried

    def _parse_challenge(self, response) -> dict:
        try:
            body = response.json()
        except Exception:
            return {}
        return body.get("accepts", body) if isinstance(body, dict) else {}

    def _settle(self, url: str, mode: str, auth: dict) -> PaymentReceipt:
        receipt = _finalize(PaymentReceipt(
            request_id=auth["nonce"], url=url, mode=mode, amount_usd=auth["amountUsd"],
            asset=auth["asset"], network=auth["network"], payer=auth["payer"], pay_to=auth["payTo"],
            nonce=auth["nonce"], signed_at=auth["signedAt"], signature=auth["signature"],
        ))
        append_settlement(receipt, self.log_path)
        return receipt
