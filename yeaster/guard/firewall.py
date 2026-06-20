"""YeasterGuard — the deterministic policy firewall.

Evaluates an :class:`OrderTicket` against a :class:`Mandate`. Never executes;
returns a structured, auditable decision (EXECUTED / REJECTED). The checks:
allowlist, single-trade cap, position cap, slippage, epoch, hard-drawdown, and
Safe Mode — with a de-risk carve-out so a risk→stable exit can never be trapped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from yeaster.core.models import Mandate, OrderTicket

# Risk→stable strictly reduces exposure: exempt from size caps and the Safe-Mode
# freeze (never from allowlist/slippage). Refusing an exit is how a drawdown
# breach becomes a blow-up.
DE_RISK_STABLES = frozenset(
    {"USDC", "USDT", "BUSD", "DAI", "FDUSD", "TUSD", "USD1", "USDD", "FRAX", "FRXUSD"}
)


class FinalDecision(str, Enum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class RuntimeState(BaseModel):
    now: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requested_slippage_bps: int = Field(default=0, ge=0)
    portfolio_drawdown_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    current_positions: dict[str, float] = Field(default_factory=dict)
    safe_mode_active: bool = False


class CheckResult(BaseModel):
    passed: bool
    observed: Any
    threshold: Any
    message: str


class GuardLog(BaseModel):
    timestamp: str
    mandate_id: str
    safe_mode_active: bool
    intent: dict[str, Any]
    checks: dict[str, CheckResult]
    rejection_reasons: list[str]
    final_decision: FinalDecision


class YeasterGuard:
    """Rebuilt each tick; latched Safe-Mode state is injected by the caller."""

    def __init__(self, mandate: Mandate, safe_mode_latched: bool = False) -> None:
        self.mandate = mandate
        self._allowed = {a.upper() for a in mandate.allowed_assets}
        self._safe_mode_active = mandate.safe_mode_enabled or safe_mode_latched

    @staticmethod
    def _is_de_risk(ticket: OrderTicket) -> bool:
        return (
            ticket.to_asset.upper() in DE_RISK_STABLES
            and ticket.from_asset.upper() not in DE_RISK_STABLES
        )

    def evaluate(self, ticket: OrderTicket, runtime: Optional[RuntimeState] = None) -> GuardLog:
        runtime = runtime or RuntimeState()
        de_risk = self._is_de_risk(ticket)
        checks = self._build_checks(ticket, runtime, de_risk)
        rejection_reasons = [name for name, r in checks.items() if not r.passed]

        if checks["hard_drawdown"].passed is False:
            self._safe_mode_active = True

        safe_mode_engaged = self._safe_mode_active or runtime.safe_mode_active
        if safe_mode_engaged and not de_risk and "safe_mode" not in rejection_reasons:
            rejection_reasons.append("safe_mode")

        if de_risk:
            for exempt in ("hard_drawdown", "safe_mode"):
                if exempt in rejection_reasons:
                    rejection_reasons.remove(exempt)

        final = (
            FinalDecision.EXECUTED
            if not rejection_reasons and not (safe_mode_engaged and not de_risk)
            else FinalDecision.REJECTED
        )

        if safe_mode_engaged and de_risk:
            checks["safe_mode"] = CheckResult(passed=True, observed=True, threshold=False,
                                              message="Safe Mode active, but de-risk exits remain permitted.")
        elif safe_mode_engaged:
            checks["safe_mode"] = CheckResult(passed=False, observed=True, threshold=False,
                                              message="Safe Mode is active; new entries are frozen.")
        else:
            checks["safe_mode"] = CheckResult(passed=True, observed=False, threshold=False,
                                              message="Safe Mode inactive; new entries may proceed.")

        return GuardLog(
            timestamp=runtime.now.astimezone(timezone.utc).isoformat(),
            mandate_id=self.mandate.mandate_id, safe_mode_active=self._safe_mode_active,
            intent=ticket.model_dump(), checks=checks, rejection_reasons=rejection_reasons,
            final_decision=final,
        )

    def evaluate_placement(self, from_asset: str, to_asset: str, *, amount_pct: float = 1.0,
                           runtime: Optional[RuntimeState] = None, purpose: str = "order") -> GuardLog:
        """Gate a bracket PLACEMENT by the swap it will fire. Protective legs are de-risk."""
        ticket = OrderTicket(from_asset=from_asset, to_asset=to_asset,
                             amount_pct=max(0.0, min(1.0, amount_pct)), confidence=1.0,
                             thesis=f"automation_placement:{purpose}")
        return self.evaluate(ticket, runtime)

    def _trade_portfolio_pct(self, ticket: OrderTicket, runtime: RuntimeState) -> float:
        """amount_pct is a fraction of the SOURCE balance; scale to a portfolio fraction."""
        weight = runtime.current_positions.get(ticket.from_asset.upper())
        return ticket.amount_pct if weight is None else ticket.amount_pct * weight

    def _epoch_active(self, now: datetime) -> tuple[bool, str]:
        if not self.mandate.epoch_expires_at:
            return True, "no epoch deadline"
        try:
            deadline = datetime.fromisoformat(self.mandate.epoch_expires_at)
        except ValueError:
            return True, "unparseable epoch (treated active)"
        return now <= deadline, self.mandate.epoch_expires_at

    def _build_checks(self, ticket: OrderTicket, runtime: RuntimeState, de_risk: bool) -> dict[str, CheckResult]:
        target = ticket.to_asset.upper()
        trade_pct = self._trade_portfolio_pct(ticket, runtime)
        position_pct = runtime.current_positions.get(target, 0.0) + trade_pct
        breached = runtime.portfolio_drawdown_pct >= self.mandate.hard_drawdown_pct
        epoch_ok, epoch_threshold = self._epoch_active(runtime.now)

        return {
            "allowlist": CheckResult(
                passed=target in self._allowed, observed=target, threshold=sorted(self._allowed),
                message=f"{target} {'is approved' if target in self._allowed else 'is NOT on the allowlist'}.",
            ),
            "max_trade_limit": CheckResult(
                passed=de_risk or trade_pct <= self.mandate.max_trade_pct,
                observed=round(trade_pct, 4), threshold=self.mandate.max_trade_pct,
                message="de-risk exempt" if de_risk else "within single-trade cap"
                if trade_pct <= self.mandate.max_trade_pct else "exceeds single-trade cap",
            ),
            "max_position_limit": CheckResult(
                passed=de_risk or position_pct <= self.mandate.max_position_pct,
                observed=round(position_pct, 4), threshold=self.mandate.max_position_pct,
                message="de-risk exempt" if de_risk else "within position cap"
                if position_pct <= self.mandate.max_position_pct else "breaches position cap",
            ),
            "slippage_limit": CheckResult(
                passed=runtime.requested_slippage_bps <= self.mandate.max_slippage_bps,
                observed=runtime.requested_slippage_bps, threshold=self.mandate.max_slippage_bps,
                message="slippage within tolerance"
                if runtime.requested_slippage_bps <= self.mandate.max_slippage_bps else "slippage exceeds tolerance",
            ),
            "epoch_active": CheckResult(
                passed=epoch_ok, observed=runtime.now.astimezone(timezone.utc).isoformat(),
                threshold=epoch_threshold, message="epoch active" if epoch_ok else "epoch expired",
            ),
            "hard_drawdown": CheckResult(
                passed=not breached, observed=round(runtime.portfolio_drawdown_pct, 4),
                threshold=self.mandate.hard_drawdown_pct,
                message="drawdown within limit" if not breached else "HARD drawdown breached; Safe Mode engages",
            ),
            "safe_mode": CheckResult(
                passed=not (self._safe_mode_active or runtime.safe_mode_active),
                observed=self._safe_mode_active or runtime.safe_mode_active, threshold=False,
                message="Safe Mode inactive" if not (self._safe_mode_active or runtime.safe_mode_active)
                else "Safe Mode active",
            ),
        }
