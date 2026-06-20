"""Approval-token layer — the execution firewall handshake.

The YeasterGuard decides EXECUTED or REJECTED; this turns an EXECUTED decision
into a tamper-evident, quote-bound permit the executor verifies before it will
broadcast a single transaction.

Properties: unforgeable (HMAC-SHA256 keyed by ``YST_APPROVAL_SECRET``),
quote-bound (signature covers ``quote_hash`` — no replay onto a worse quote),
gated on EXECUTED, and expiring (TTL).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from yeaster.core.settings import get_settings
from yeaster.execution.models import ApprovalToken, SwapQuote

DEFAULT_TTL_SECONDS = 120


class ApprovalError(Exception):
    """Raised when a token cannot be minted or fails verification."""


def _secret() -> bytes:
    return get_settings().approval_secret.encode()


def _sign(claims: dict[str, Any]) -> str:
    canonical = json.dumps(claims, sort_keys=True, separators=(",", ":"))
    return "0x" + hmac.new(_secret(), canonical.encode(), hashlib.sha256).hexdigest()


def _nonce(quote_hash: str, issued_at: str) -> str:
    return hashlib.sha256(f"{quote_hash}:{issued_at}".encode()).hexdigest()[:16]


def _normalize_decision(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def issue_approval_token(
    quote: SwapQuote,
    *,
    final_decision: str,
    mandate_id: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: Optional[datetime] = None,
) -> ApprovalToken:
    """Mint a permit for ``quote``. Refuses unless the guard decision is EXECUTED."""
    final_decision = _normalize_decision(final_decision)
    if final_decision != "EXECUTED":
        raise ApprovalError(f"Guard decision is '{final_decision}', not EXECUTED; no token issued.")
    if not quote.quote_hash:
        raise ApprovalError("Quote is missing quote_hash; cannot bind an approval token.")

    now = now or datetime.now(timezone.utc)
    issued_at = now.astimezone(timezone.utc).isoformat()
    expires_at = (now + timedelta(seconds=ttl_seconds)).astimezone(timezone.utc).isoformat()
    nonce = _nonce(quote.quote_hash, issued_at)

    claims = {
        "quote_hash": quote.quote_hash,
        "mandate_id": mandate_id,
        "final_decision": final_decision,
        "nonce": nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    return ApprovalToken(token=_sign(claims), **claims)


def issue_from_guard_log(
    quote: SwapQuote,
    guard_log: dict[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: Optional[datetime] = None,
) -> ApprovalToken:
    return issue_approval_token(
        quote,
        final_decision=_normalize_decision(guard_log.get("final_decision")),
        mandate_id=str(guard_log.get("mandate_id", "unknown-mandate")),
        ttl_seconds=ttl_seconds,
        now=now,
    )


def verify_approval_token(token: ApprovalToken, quote: SwapQuote, *, now: Optional[datetime] = None) -> None:
    """Raise ``ApprovalError`` unless ``token`` is a valid permit for ``quote``."""
    if token.final_decision != "EXECUTED":
        raise ApprovalError("Approval token does not certify an EXECUTED decision.")
    if token.quote_hash != quote.quote_hash:
        raise ApprovalError("Approval token bound to a different quote (quote_hash mismatch) — possible replay.")

    expected = _sign({
        "quote_hash": token.quote_hash,
        "mandate_id": token.mandate_id,
        "final_decision": token.final_decision,
        "nonce": token.nonce,
        "issued_at": token.issued_at,
        "expires_at": token.expires_at,
    })
    if not hmac.compare_digest(expected, token.token):
        raise ApprovalError("Approval token signature is invalid — forged or tampered.")

    now = now or datetime.now(timezone.utc)
    if now > datetime.fromisoformat(token.expires_at):
        raise ApprovalError("Approval token has expired.")
