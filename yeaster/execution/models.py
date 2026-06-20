"""Execution-layer schemas — the two-step swap lifecycle and native automations.

    SwapRequest -> SwapQuote -> (YeasterGuard) -> ApprovalToken -> SwapReceipt

Yeaster defaults to BSC **testnet** (97). Mainnet (56) is rejected at the
execution boundary unless the operator has opened the YST_ double gate.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from yeaster.core.settings import get_settings

BSC_TESTNET_CHAIN_ID = 97
BSC_MAINNET_CHAIN_ID = 56
NATIVE_SYMBOL = "tBNB"
_TESTNET_EXPLORER = "https://testnet.bscscan.com/tx/"
_MAINNET_EXPLORER = "https://bscscan.com/tx/"


def permitted_chain_ids() -> tuple[int, ...]:
    """Chains the executor will broadcast to, honoring the YST_ mainnet gate."""
    return get_settings().permitted_chain_ids


def explorer_for_chain(chain_id: int) -> str:
    return _MAINNET_EXPLORER if chain_id == BSC_MAINNET_CHAIN_ID else _TESTNET_EXPLORER


def _norm_symbol(value: str) -> str:
    sym = value.strip().upper()
    if not sym:
        raise ValueError("asset symbol must be non-empty")
    return "BNB" if sym == "TBNB" else sym


class SwapStatus(str, Enum):
    QUOTED = "QUOTED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"   # blocked by firewall / approval (no chain call)
    FAILED = "FAILED"       # chain call attempted but reverted


class SwapRequest(BaseModel):
    from_asset: str
    to_asset: str
    amount_in: float = Field(gt=0.0)
    chain_id: int = BSC_TESTNET_CHAIN_ID
    slippage_tolerance_bps: int = Field(default=50, ge=0, le=5000)

    @field_validator("from_asset", "to_asset")
    @classmethod
    def _sym(cls, v: str) -> str:
        return _norm_symbol(v)

    @field_validator("chain_id")
    @classmethod
    def _chain(cls, v: int) -> int:
        permitted = permitted_chain_ids()
        if v not in permitted:
            if v == BSC_MAINNET_CHAIN_ID:
                raise ValueError(
                    "BSC Mainnet (56) is gated: set YST_MAINNET=1 and "
                    "YST_MAINNET_CONFIRM=I-UNDERSTAND-LIVE-FUNDS to enable live trading."
                )
            raise ValueError(f"Yeaster executes on permitted chains {permitted} only; got {v}.")
        return v


class SwapQuote(BaseModel):
    quote_id: str
    backend: str
    chain_id: int = BSC_TESTNET_CHAIN_ID
    from_asset: str
    to_asset: str
    amount_in: float
    expected_amount_out: float
    min_amount_out: float
    price_impact_bps: int = Field(ge=0)
    expected_slippage_bps: int = Field(ge=0)   # the number the firewall slippage check reads
    slippage_tolerance_bps: int = Field(ge=0)
    route: list[str] = Field(default_factory=list)
    quoted_at: str
    expires_at: str
    quote_hash: str = ""   # sha256 over the quote; the approval token binds to it


class ApprovalToken(BaseModel):
    token: str
    quote_hash: str
    mandate_id: str
    final_decision: str    # must be "EXECUTED"
    nonce: str
    issued_at: str
    expires_at: str


class TokenBalance(BaseModel):
    symbol: str
    balance: float
    value_usd: Optional[float] = None


class PortfolioState(BaseModel):
    address: str
    chain_id: int = BSC_TESTNET_CHAIN_ID
    native_symbol: str = NATIVE_SYMBOL
    native_balance: float = 0.0
    balances: list[TokenBalance] = Field(default_factory=list)
    total_value_usd: Optional[float] = None
    positions_pct: dict[str, float] = Field(default_factory=dict)
    captured_at: str


class SwapReceipt(BaseModel):
    status: SwapStatus
    backend: str
    chain_id: int = BSC_TESTNET_CHAIN_ID
    tx_hash: Optional[str] = None
    from_asset: str
    to_asset: str
    amount_in: float
    amount_out: Optional[float] = None
    effective_slippage_bps: Optional[int] = None
    quote_hash: str = ""
    explorer_url: Optional[str] = None
    executed_at: Optional[str] = None
    portfolio: Optional[PortfolioState] = None
    error: Optional[str] = None


# ── Native automations (TWAK limit / DCA brackets) ──────────────────────────


class AutomationKind(str, Enum):
    LIMIT = "LIMIT"   # --price + --condition (stop / take-profit / limit-entry)
    DCA = "DCA"


class AutomationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class AutomationSpec(BaseModel):
    from_asset: str
    to_asset: str
    chain_id: int = BSC_TESTNET_CHAIN_ID
    amount: float = Field(gt=0.0)
    kind: AutomationKind = AutomationKind.LIMIT
    price_usd: Optional[float] = Field(default=None, gt=0.0)
    condition: Optional[str] = None        # "above" | "below"
    interval: Optional[str] = None         # DCA
    max_runs: Optional[int] = Field(default=None, ge=1)
    expires_at: Optional[str] = None
    purpose: Optional[str] = None          # "stop" | "take_profit" | "limit_entry"
    symbol: Optional[str] = None

    @field_validator("from_asset", "to_asset")
    @classmethod
    def _sym(cls, v: str) -> str:
        return _norm_symbol(v)

    @field_validator("condition")
    @classmethod
    def _cond(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("above", "below"):
            raise ValueError("condition must be 'above' or 'below'")
        return v


class Automation(BaseModel):
    id: str
    backend: str
    kind: AutomationKind
    status: AutomationStatus = AutomationStatus.ACTIVE
    from_asset: str
    to_asset: str
    chain_id: int = BSC_TESTNET_CHAIN_ID
    amount: float
    price_usd: Optional[float] = None
    condition: Optional[str] = None
    interval: Optional[str] = None
    max_runs: Optional[int] = None
    runs_executed: int = 0
    purpose: Optional[str] = None
    symbol: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    last_run_at: Optional[str] = None
    last_tx_hash: Optional[str] = None
