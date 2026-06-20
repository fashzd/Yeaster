"""Shared contracts — the currency that flows between brain, guard, execution and proof.

No decision logic lives here; only schemas. Pydantic v2.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Posture(str, Enum):
    """The agent's stance for a tick, derived from the market regime read."""

    HUNT = "hunt"            # risk-on, deploy alpha
    SELECTIVE = "selective"  # mixed, trade only the strongest
    STAND_DOWN = "stand_down"  # risk-off, defend / de-risk


class TicketKind(str, Enum):
    ENTRY = "entry"             # stable -> risk
    EXIT = "exit"               # risk -> stable (always de-risk; firewall-exempt on caps)
    NONE = "none"               # stand pat


class OrderTicket(BaseModel):
    """A proposed trade, before any market interaction or safety check."""

    from_asset: str
    to_asset: str
    amount_pct: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    kind: TicketKind = TicketKind.ENTRY
    thesis: str = ""


class ExitPlan(BaseModel):
    """Bracket calibration for a position (the 'let winners run' profile)."""

    stop_pct: Optional[float] = Field(default=0.035, ge=0.0, le=1.0)
    take_profit_pct: Optional[float] = Field(default=None, ge=0.0)   # None => farthest ATR target
    trailing_pct: float = Field(default=0.03, ge=0.0, le=1.0)


class Mandate(BaseModel):
    """The immutable per-epoch safety contract the firewall enforces."""

    mandate_id: str
    allowed_assets: list[str]
    max_trade_pct: float = Field(default=0.12, ge=0.0, le=1.0)
    max_position_pct: float = Field(default=0.30, ge=0.0, le=1.0)
    max_slippage_bps: int = Field(default=50, ge=0, le=5000)
    hard_drawdown_pct: float = Field(default=0.15, ge=0.0, le=1.0)
    epoch_expires_at: Optional[str] = None       # ISO 8601; None => no epoch deadline
    safe_mode_enabled: bool = False


class CommitRecord(BaseModel):
    """The per-tick decision the runtime logs to the proof ledger and returns to the UI.

    (Yeaster's equivalent of a decision record — the on-disk proof key is
    ``commit_record``.)
    """

    snapshot_hash: Optional[str] = None
    generated_at: str
    posture: str                                  # hunt / selective / stand_down
    strategy: str = "Momentum Rotation"
    ticket: Optional[OrderTicket] = None
    ticket_kind: Optional[str] = None             # entry / exit / none
    conviction: Optional[float] = None
    rationale: Optional[str] = None
    stand_down_reason: Optional[str] = None
    brain: str = "cycle"                          # which brain produced it
    reasoning: Optional[dict[str, Any]] = None    # the live screen/grade/vet/commit trace
