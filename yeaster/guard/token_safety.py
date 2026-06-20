"""Token-safety due diligence — holder distribution + liquidity floor.

Evaluated BEFORE any swap is cleared for signing. Deterministic and network-free:
the caller fetches the token profile (skill pipeline) and passes it in; this only
applies thresholds and merges the result into the guard log. Missing telemetry
FAILS (no data = no clearance) — an unverifiable asset must not reach signing.
"""

from __future__ import annotations

from typing import Any, Optional

from yeaster.core.settings import get_settings
from yeaster.guard.firewall import CheckResult, FinalDecision, GuardLog

DEFAULT_MIN_LIQUIDITY_USD = 500_000.0
STABLE_SYMBOLS = frozenset({"USDT", "USDC", "DAI", "TUSD", "FDUSD", "USD1", "USDD", "FRAX"})


def _whale_limit() -> float:
    return get_settings().whale_concentration_limit_pct


def build_token_safety_checks(
    symbol: str,
    whale_concentration_pct: Optional[float],
    liquidity_usd: Optional[float],
    min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD,
    whale_limit_pct: Optional[float] = None,
) -> dict[str, CheckResult]:
    sym = symbol.upper()
    limit = whale_limit_pct if whale_limit_pct is not None else _whale_limit()

    if sym in STABLE_SYMBOLS:
        whale = CheckResult(passed=True, observed=whale_concentration_pct, threshold=limit,
                            message=f"{sym} is a stablecoin; issuer-treasury concentration is exempt.")
    elif whale_concentration_pct is None:
        whale = CheckResult(passed=False, observed=None, threshold=limit,
                            message=f"No holder-distribution telemetry for {sym}; refusing unverified asset.")
    else:
        ok = whale_concentration_pct <= limit
        whale = CheckResult(passed=ok, observed=round(whale_concentration_pct, 2), threshold=limit,
                            message=(f"{sym} whale concentration {whale_concentration_pct:.1f}% within {limit:.0f}% limit."
                                     if ok else f"{sym} whale concentration {whale_concentration_pct:.1f}% exceeds {limit:.0f}% limit."))

    if liquidity_usd is None:
        liq = CheckResult(passed=False, observed=None, threshold=min_liquidity_usd,
                          message=f"No liquidity telemetry for {sym}; refusing unverified asset.")
    else:
        ok = liquidity_usd >= min_liquidity_usd
        liq = CheckResult(passed=ok, observed=round(liquidity_usd, 2), threshold=min_liquidity_usd,
                          message=(f"{sym} liquidity ${liquidity_usd:,.0f} clears the floor."
                                   if ok else f"{sym} liquidity ${liquidity_usd:,.0f} below floor ${min_liquidity_usd:,.0f}."))

    return {"whale_concentration": whale, "liquidity_floor": liq}


def evaluate_with_token_safety(
    log: GuardLog,
    target_asset: str,
    token_profile: Optional[dict[str, Any]] = None,
    min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD,
    whale_limit_pct: Optional[float] = None,
) -> GuardLog:
    """Merge token-safety checks into an existing guard log; a failure flips to REJECTED."""
    profile = token_profile or {}
    safety = build_token_safety_checks(
        symbol=target_asset,
        whale_concentration_pct=profile.get("whale_concentration_pct"),
        liquidity_usd=profile.get("liquidity_usd"),
        min_liquidity_usd=min_liquidity_usd, whale_limit_pct=whale_limit_pct,
    )
    checks = dict(log.checks)
    checks.update(safety)
    reasons = list(log.rejection_reasons)
    for name, r in safety.items():
        if not r.passed and name not in reasons:
            reasons.append(name)
    final = FinalDecision.REJECTED if reasons else log.final_decision
    return log.model_copy(update={"checks": checks, "rejection_reasons": reasons, "final_decision": final})
