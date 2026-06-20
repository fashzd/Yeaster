"""Liveness and readiness endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from yeaster import __version__

router = APIRouter(tags=["health"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/health")
def health() -> dict:
    """Cheap liveness check — the process is up and serving."""
    return {"status": "ok", "service": "yeaster", "version": __version__, "checked_at": _now()}


def _x402_layer() -> dict:
    from yeaster.execution import x402
    on = x402.enabled()
    return {"live": on, "detail": (f"enabled · settled ${x402.total_settled_usd():.4f}"
                                   if on else "disabled (YST_X402)")}


@router.get("/readiness")
def readiness() -> dict:
    """Per-layer live-connection report — probes each integration."""
    import shutil

    from yeaster.core.settings import get_settings
    from yeaster.market import cmc, skills

    s = get_settings()
    cmc_backend = cmc.resolve_backend("auto")
    twak_cli = bool(shutil.which(s.twak_cli_bin))
    has_llm = bool(s.openai_api_key or s.anthropic_api_key)

    layers = {
        "api": {"live": True, "detail": "fastapi serving"},
        "cmc_market_data": {
            "live": cmc_backend in ("rest", "mcp"),
            "detail": f"backend={cmc_backend}" + ("" if cmc_backend != "mock" else " (no key — mock)"),
        },
        "cmc_skills": {
            "live": skills.available(),
            "detail": "skill-hub enabled" if skills.available() else "disabled (YST_USE_SKILLS / key)",
        },
        "llm": {"live": has_llm, "detail": f"provider={s.llm_provider}" if has_llm else "no LLM key"},
        "persistence": {"live": True, "detail": "json state under data/"},
        "twak_execution": {
            "live": twak_cli,
            "detail": "twak cli present" if twak_cli else "paper backend (no cli)",
        },
        "bnb_onchain": {
            "live": s.mainnet_unlocked,
            "detail": "mainnet gate OPEN" if s.mainnet_unlocked else "testnet only (mainnet gated)",
        },
        "x402_payments": _x402_layer(),
    }
    live_count = sum(1 for v in layers.values() if v["live"])
    return {"checked_at": _now(), "live_count": live_count, "layer_count": len(layers), "layers": layers}
