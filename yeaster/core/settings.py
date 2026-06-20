"""Typed runtime configuration for Yeaster.

All Yeaster-owned knobs use the ``YST_`` prefix. Third-party credentials keep
their vendor prefixes (``CMC_``, ``OPENAI_``, ``ANTHROPIC_``, ``TWAK_``, ``TW_``,
``BSC_``, ``BNBAGENT_``) because they authenticate to those services — including
the **same wallet** the agent already uses (TWAK keychain).

This is a hand-rolled frozen settings object loaded once from the environment,
deliberately dependency-light. Read it via :func:`get_settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

MAINNET_CONFIRM_PHRASE = "I-UNDERSTAND-LIVE-FUNDS"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and v != "") else default


def _flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(str(_env(name, str(default))))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(str(_env(name, str(default))))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # ── Market data (CoinMarketCap) ──────────────────────────────────────
    cmc_api_key: Optional[str]
    cmc_mcp_api_key: Optional[str]
    cmc_skill_hub_url: str

    # ── Language model backbone ──────────────────────────────────────────
    openai_api_key: Optional[str]
    anthropic_api_key: Optional[str]
    llm_provider: str          # YST_LLM_PROVIDER  → "openai" | "anthropic"
    llm_model: Optional[str]   # YST_LLM_MODEL     → override; else provider default
    commit_style: str          # YST_COMMIT_STYLE  → "aggressive" | "disciplined"

    # ── Execution / wallet (Trust Wallet AgentKit) ───────────────────────
    twak_cli_bin: str
    twak_wallet_password: Optional[str]
    bsc_testnet_wallet_address: Optional[str]
    agent_wallet: Optional[str]  # YST_AGENT_WALLET optional override

    # ── Brain / pipeline knobs (Yeaster-owned) ───────────────────────────
    use_skills: bool           # YST_USE_SKILLS
    skills_backend: str        # YST_SKILLS_BACKEND  → "auto" | "mcp" | "rest" | "mock"
    commit_arm: str            # YST_COMMIT_ARM      → which commit policy
    exit_mode: str             # YST_EXIT_MODE       → "native" | "emulated"
    grade_cap: int             # YST_GRADE_CAP       → max candidates graded per tick
    snapshot_topn: int         # YST_SNAPSHOT_TOPN
    wide_snapshot: bool        # YST_WIDE_SNAPSHOT
    guard_wide_allowlist: bool # YST_GUARD_WIDE_ALLOWLIST
    hist_refresh_seconds: int  # YST_HIST_REFRESH_SECONDS
    whale_concentration_limit_pct: float  # YST_WHALE_CONCENTRATION_LIMIT_PCT

    # ── Safety gates ─────────────────────────────────────────────────────
    approval_secret: str       # YST_APPROVAL_SECRET (HMAC permit key)
    trade_chain_id: int        # YST_TRADE_CHAIN_ID  → 97 testnet / 56 mainnet
    mainnet: bool              # YST_MAINNET
    mainnet_confirm: Optional[str]  # YST_MAINNET_CONFIRM

    @property
    def mainnet_unlocked(self) -> bool:
        """Real mainnet execution requires BOTH gates set correctly."""
        return self.mainnet and self.mainnet_confirm == MAINNET_CONFIRM_PHRASE

    @property
    def permitted_chain_ids(self) -> tuple[int, ...]:
        return (97, 56) if self.mainnet_unlocked else (97,)

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            cmc_api_key=_env("CMC_API_KEY"),
            cmc_mcp_api_key=_env("CMC_MCP_API_KEY"),
            cmc_skill_hub_url=_env(
                "CMC_SKILL_HUB_URL", "https://mcp.coinmarketcap.com/skill-hub/stream"
            ),
            openai_api_key=_env("OPENAI_API_KEY"),
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            llm_provider=(_env("YST_LLM_PROVIDER", "openai") or "openai").lower(),
            llm_model=_env("YST_LLM_MODEL"),
            commit_style=(_env("YST_COMMIT_STYLE", "aggressive") or "aggressive").lower(),
            twak_cli_bin=_env("TWAK_CLI_BIN", "twak") or "twak",
            twak_wallet_password=_env("TWAK_WALLET_PASSWORD"),
            bsc_testnet_wallet_address=_env("BSC_TESTNET_WALLET_ADDRESS"),
            agent_wallet=_env("YST_AGENT_WALLET"),
            use_skills=_flag("YST_USE_SKILLS", False),
            skills_backend=(_env("YST_SKILLS_BACKEND", "auto") or "auto").lower(),
            commit_arm=_env("YST_COMMIT_ARM", "llm_lead") or "llm_lead",
            exit_mode=(_env("YST_EXIT_MODE", "native") or "native").lower(),
            grade_cap=_int("YST_GRADE_CAP", 12),
            snapshot_topn=_int("YST_SNAPSHOT_TOPN", 150),
            wide_snapshot=_flag("YST_WIDE_SNAPSHOT", True),
            guard_wide_allowlist=_flag("YST_GUARD_WIDE_ALLOWLIST", True),
            hist_refresh_seconds=_int("YST_HIST_REFRESH_SECONDS", 21600),
            whale_concentration_limit_pct=_float("YST_WHALE_CONCENTRATION_LIMIT_PCT", 30.0),
            approval_secret=_env("YST_APPROVAL_SECRET", "yeaster-dev-approval-secret")
            or "yeaster-dev-approval-secret",
            trade_chain_id=_int("YST_TRADE_CHAIN_ID", 56),
            mainnet=_flag("YST_MAINNET", False),
            mainnet_confirm=_env("YST_MAINNET_CONFIRM"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded once from the environment."""
    return Settings.load()
