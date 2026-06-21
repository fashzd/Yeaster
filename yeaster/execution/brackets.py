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
from yeaster.core.universe import DEFAULT_RESERVE
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


def _trade_chain_id() -> int:
    """The chain the live position actually sits on — mainnet when the gate is
    open, else testnet. Brackets must match it or the CLI rejects the chain."""
    return 56 if get_settings().mainnet_unlocked else 97


def build_bracket_specs(symbol: str, qty: float, stop_price: float, tp_price: float,
                        reserve: str = DEFAULT_RESERVE, expires_at: Optional[str] = None) -> dict[str, AutomationSpec]:
    """Stop (sell below) + take-profit (sell above) legs for a long position."""
    common = dict(from_asset=symbol, to_asset=reserve, amount=qty, chain_id=_trade_chain_id(),
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


def _tok_arg(symbol: str, chain_id: int) -> str:
    """Resolve a token to what the CLI needs to EXECUTE: the contract address on
    mainnet, else the symbol. A bracket stored as the bare symbol 'CAKE' makes the
    watcher fail with 'Unknown token: CAKE on bsc' when it fires — it must be the
    contract, exactly like a swap."""
    if chain_id == 56:
        try:
            from yeaster.core.addresses import token_arg
            return token_arg(symbol)
        except Exception:
            return symbol
    return symbol


def place(spec: AutomationSpec, backend: str = "auto") -> Automation:
    if resolve_backend(backend) == "cli":
        chain = "bsc" if spec.chain_id != 97 else "bsc-testnet"
        from_arg = _tok_arg(spec.from_asset, spec.chain_id)
        to_arg = _tok_arg(spec.to_asset, spec.chain_id)
        args = ["automate", "add", "--from", from_arg, "--to", to_arg,
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


def _cli_list_raw() -> list[dict]:
    """Raw CLI automation rows (camelCase: id/fromToken/toToken/...). The typed
    ``list_automations`` can't parse these, so cleanup operates on the raw dicts."""
    try:
        raw = _cli(["automate", "list", "--json"])
    except Exception:
        return []
    rows = raw if isinstance(raw, list) else (raw.get("automations") or raw.get("data") or [])
    return [r for r in rows if isinstance(r, dict)]


def _tracked_keys(symbols) -> set[str]:
    """Match keys for tracked positions: their symbols AND resolved contracts
    (the CLI stores a leg's ``fromToken`` as either a symbol or a contract)."""
    keys = {str(s).upper() for s in symbols}
    for s in symbols:
        try:
            from yeaster.core.addresses import token_arg
            keys.add(str(token_arg(s)).lower())
        except Exception:
            pass
    return keys


def _is_tracked(from_token, keys: set[str]) -> bool:
    ft = str(from_token or "")
    return ft.upper() in keys or ft.lower() in keys


def cancel_all(backend: str = "auto") -> int:
    """Cancel EVERY active automation. Returns the count cancelled."""
    if resolve_backend(backend) == "cli":
        n = 0
        for r in _cli_list_raw():
            if r.get("id") and cancel(r["id"], "cli"):
                n += 1
        return n
    rows = _load()
    n = 0
    for r in rows:
        if r.get("status", "ACTIVE") == "ACTIVE":
            r["status"] = AutomationStatus.CANCELLED.value
            n += 1
    _save(rows)
    return n


def cancel_orphans(tracked_symbols, backend: str = "auto") -> int:
    """Cancel automations NOT tied to a currently-tracked position (orphans).
    Legit stop/TP brackets on held positions are kept. Returns the count cancelled."""
    keys = _tracked_keys(tracked_symbols)
    if resolve_backend(backend) == "cli":
        n = 0
        for r in _cli_list_raw():
            if r.get("id") and not _is_tracked(r.get("fromToken"), keys):
                if cancel(r["id"], "cli"):
                    n += 1
        return n
    rows = _load()
    n = 0
    for r in rows:
        if r.get("status", "ACTIVE") != "ACTIVE":
            continue
        if not _is_tracked(r.get("from_asset") or r.get("symbol"), keys):
            r["status"] = AutomationStatus.CANCELLED.value
            n += 1
    _save(rows)
    return n
