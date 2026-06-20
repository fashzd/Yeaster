"""Native exit brackets — TWAK limit automations (stop / take-profit) + reconcile.

On entry the agent places a Guard-gated stop and take-profit as ``twak automate``
limit legs (paper store or live CLI). The watcher fires a leg when price crosses;
:func:`reconcile` detects a filled leg, cancels its sibling (no native OCO), and
:func:`trail` ratchets stops upward as price makes new highs.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from yeaster.core.settings import get_settings
from yeaster.execution.models import (
    Automation,
    AutomationKind,
    AutomationSpec,
    AutomationStatus,
)
from yeaster.execution.twak import resolve_backend

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_AUTO_PATH = REPO_ROOT / "data" / "wallet" / "paper_automations.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_bracket_specs(symbol: str, qty: float, stop_price: float, tp_price: float,
                        reserve: str = "USDC", expires_at: Optional[str] = None) -> dict[str, AutomationSpec]:
    """Stop (sell below) + take-profit (sell above) legs for a long position."""
    common = dict(from_asset=symbol, to_asset=reserve, amount=qty,
                  kind=AutomationKind.LIMIT, max_runs=1, expires_at=expires_at, symbol=symbol)
    return {
        "stop": AutomationSpec(price_usd=stop_price, condition="below", purpose="stop", **common),
        "take_profit": AutomationSpec(price_usd=tp_price, condition="above", purpose="take_profit", **common),
    }


# ── paper automation store ───────────────────────────────────────────────────


def _load() -> list[dict]:
    if PAPER_AUTO_PATH.exists():
        return json.loads(PAPER_AUTO_PATH.read_text())
    return []


def _save(rows: list[dict]) -> None:
    PAPER_AUTO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_AUTO_PATH.write_text(json.dumps(rows, indent=2))


def _paper_place(spec: AutomationSpec) -> Automation:
    rows = _load()
    auto = Automation(
        id=f"auto-{len(rows)+1}-{spec.purpose}", backend="paper", kind=spec.kind,
        from_asset=spec.from_asset, to_asset=spec.to_asset, amount=spec.amount,
        price_usd=spec.price_usd, condition=spec.condition, max_runs=spec.max_runs,
        purpose=spec.purpose, symbol=spec.symbol, created_at=_now(), expires_at=spec.expires_at,
    )
    rows.append(auto.model_dump())
    _save(rows)
    return auto


def _cli(args: list[str]) -> dict:
    proc = subprocess.run([get_settings().twak_cli_bin, *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"raw": proc.stdout.strip()}


def place(spec: AutomationSpec, backend: str = "auto") -> Automation:
    if resolve_backend(backend) == "cli":
        chain = "bsc" if spec.chain_id != 97 else "bsc-testnet"
        args = ["automate", "add", "--from", spec.from_asset, "--to", spec.to_asset,
                "--chain", chain, "--amount", str(spec.amount)]
        if spec.price_usd:
            args += ["--price", str(spec.price_usd)]
        if spec.condition:
            args += ["--condition", spec.condition]
        if spec.max_runs:
            args += ["--max-runs", str(spec.max_runs)]
        if spec.expires_at:
            args += ["--expires", spec.expires_at]
        raw = _cli([*args, "--json"])
        return Automation(
            id=str(raw.get("id") or f"cli-{spec.purpose}"), backend="cli", kind=spec.kind,
            from_asset=spec.from_asset, to_asset=spec.to_asset, amount=spec.amount,
            price_usd=spec.price_usd, condition=spec.condition, purpose=spec.purpose,
            symbol=spec.symbol, created_at=_now(), expires_at=spec.expires_at,
        )
    return _paper_place(spec)


def list_automations(backend: str = "auto") -> list[Automation]:
    if resolve_backend(backend) == "cli":
        try:
            raw = _cli(["automate", "list", "--json"])
        except Exception:
            return []
        rows = raw if isinstance(raw, list) else raw.get("automations") or []
        out = []
        for r in rows:
            try:
                out.append(Automation(**{**r, "backend": "cli"}))
            except Exception:
                continue
        return out
    return [Automation(**r) for r in _load() if r.get("status", "ACTIVE") == "ACTIVE"]


def cancel(automation_id: str, backend: str = "auto") -> bool:
    if resolve_backend(backend) == "cli":
        try:
            _cli(["automate", "delete", automation_id])
            return True
        except Exception:
            return False
    rows = _load()
    changed = False
    for r in rows:
        if r["id"] == automation_id and r.get("status") == "ACTIVE":
            r["status"] = AutomationStatus.CANCELLED.value
            changed = True
    _save(rows)
    return changed
