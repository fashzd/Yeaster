"""The autonomous daemon — runs the tick on a cadence in a background thread.

Supports a **committed run**: start with a runtime in hours and the chat locks for
that window, the agent trades unattended, and the loop auto-stops when the timer
expires. A **password-protected kill switch** can halt a locked run early.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from yeaster.runtime import tick as tick_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON_STATE_PATH = REPO_ROOT / "data" / "state" / "daemon_state.json"

DEFAULT_CADENCE_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _hash(pw: str) -> str:
    return hashlib.sha256(("yeaster:" + pw).encode()).hexdigest()


def _load() -> dict[str, Any]:
    if DAEMON_STATE_PATH.exists():
        return json.loads(DAEMON_STATE_PATH.read_text())
    return {"enabled": False, "running": False, "locked": False, "live": False,
            "cadence_seconds": DEFAULT_CADENCE_SECONDS, "cmc_backend": "auto", "twak_backend": "auto",
            "run_until": None, "kill_hash": None, "last_loop_at": None, "last_error": None, "loops": 0}


def _save(cfg: dict[str, Any]) -> None:
    DAEMON_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DAEMON_STATE_PATH.write_text(json.dumps(cfg, indent=2))


class KillSwitchError(Exception):
    """Wrong or missing kill-switch password for a locked run."""


class Daemon:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self, *, cadence_seconds: int = DEFAULT_CADENCE_SECONDS, cmc_backend: str = "auto",
              twak_backend: str = "auto", run_hours: Optional[float] = None, lock: bool = False,
              kill_password: Optional[str] = None, live: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            cfg = _load()
            run_until = _iso(_now() + timedelta(hours=run_hours)) if run_hours else None
            cfg.update({
                "enabled": True, "running": True, "locked": bool(lock),
                "live": bool(live), "cadence_seconds": int(cadence_seconds),
                "cmc_backend": cmc_backend, "twak_backend": twak_backend,
                "run_until": run_until, "run_hours": run_hours,
                "kill_hash": _hash(kill_password) if (lock and kill_password) else None,
                "started_at": _iso(_now()), "last_error": None,
            })
            _save(cfg)
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return self.status()

    def _check_password(self, cfg: dict[str, Any], password: Optional[str], *, require: bool = False) -> None:
        """Gate unlock/kill. A correct password is the active run's kill password OR the
        configured operator password (master).

        - The **kill switch** (``require=True``) is gated whenever an operator password
          is configured — it's destructive, so never unprotected.
        - **Unlocking a committed (locked) run** is gated by that run's kill password.
        - A casual stop of an *unlocked* loop (the power toggle) needs no password.
        """
        try:
            from yeaster.core.settings import get_settings
            op = get_settings().operator_password
        except Exception:
            op = None
        kill_hash = cfg.get("kill_hash") if cfg.get("locked") else None
        need = bool(kill_hash) or (require and bool(op))
        if not need:
            return
        if password and ((op and password == op) or (kill_hash and _hash(password) == kill_hash)):
            return
        raise KillSwitchError("operator/kill-switch password required")

    def stop(self, password: Optional[str] = None) -> dict[str, Any]:
        """Graceful unlock: halt the loop and sweep ORPHANED automations, but keep
        protective brackets on open positions (they stay live on-chain)."""
        cfg = _load()
        self._check_password(cfg, password)
        self._stop.set()
        backend = cfg.get("twak_backend", "auto")
        try:
            from yeaster.execution import brackets
            from yeaster.runtime import state as state_mod
            tracked = list(state_mod.load(state_mod.state_mode(backend)).get("positions", {}).keys())
            cfg["orphans_cleaned"] = brackets.cancel_orphans(tracked, backend)
        except Exception as exc:  # noqa: BLE001 — never block the halt on cleanup
            cfg["orphans_cleaned"] = f"error: {exc}"
        cfg.update({"enabled": False, "running": False, "locked": False, "run_until": None,
                    "kill_hash": None, "stopped_at": _iso(_now())})
        _save(cfg)
        return cfg

    def kill(self, password: Optional[str] = None) -> dict[str, Any]:
        """Emergency kill switch: halt, FLATTEN every open position to USDT, and
        cancel ALL automations. ALWAYS password-gated (operator password or the
        locked run's kill password). Works on paper and live."""
        cfg = _load()
        self._check_password(cfg, password, require=True)   # kill is always gated when an operator pw is set
        self._stop.set()
        backend = cfg.get("twak_backend", "auto")
        try:
            from yeaster.runtime import flatten as flatten_mod
            cfg["flatten_result"] = flatten_mod.flatten_all(backend)
        except Exception as exc:  # noqa: BLE001
            cfg["flatten_result"] = {"error": str(exc)}
        cfg.update({"enabled": False, "running": False, "locked": False, "run_until": None,
                    "kill_hash": None, "killed_at": _iso(_now())})
        _save(cfg)
        return cfg

    def run_once(self) -> dict[str, Any]:
        return self._one(_load())

    def is_locked(self) -> bool:
        cfg = _load()
        return bool(cfg.get("running") and cfg.get("locked"))

    def status(self) -> dict[str, Any]:
        cfg = _load()
        cfg["running"] = bool(self._thread and self._thread.is_alive())
        cfg.pop("kill_hash", None)  # never expose the hash
        try:
            from yeaster.core.settings import get_settings
            cfg["mainnet_unlocked"] = get_settings().mainnet_unlocked
        except Exception:
            cfg["mainnet_unlocked"] = False
        ru = cfg.get("run_until")
        if ru:
            try:
                cfg["remaining_seconds"] = max(0, int((datetime.fromisoformat(ru) - _now()).total_seconds()))
            except ValueError:
                cfg["remaining_seconds"] = None
        return cfg

    def _expired(self, cfg: dict[str, Any]) -> bool:
        ru = cfg.get("run_until")
        if not ru:
            return False
        try:
            return _now() >= datetime.fromisoformat(ru)
        except ValueError:
            return False

    def _one(self, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            result = tick_mod.run_tick(cmc_backend=cfg.get("cmc_backend", "auto"),
                                       twak_backend=cfg.get("twak_backend", "auto"))
            cfg = _load()
            cfg["last_loop_at"] = _iso(_now())
            cfg["loops"] = cfg.get("loops", 0) + 1
            cfg["last_error"] = None
            _save(cfg)
            return result
        except Exception as exc:
            cfg = _load()
            cfg["last_error"] = str(exc)
            cfg["last_loop_at"] = _iso(_now())
            _save(cfg)
            return {"error": str(exc)}

    def _loop(self) -> None:
        while not self._stop.is_set():
            cfg = _load()
            if self._expired(cfg):
                # committed run finished — auto-stop and release the lock
                cfg.update({"enabled": False, "running": False, "locked": False, "run_until": None,
                            "kill_hash": None, "expired_at": _iso(_now())})
                _save(cfg)
                return
            self._one(cfg)
            self._stop.wait(max(15, int(cfg.get("cadence_seconds", DEFAULT_CADENCE_SECONDS))))


DAEMON = Daemon()


def auto_resume() -> None:
    cfg = _load()
    if cfg.get("enabled"):
        DAEMON.start(cadence_seconds=cfg.get("cadence_seconds", DEFAULT_CADENCE_SECONDS),
                     cmc_backend=cfg.get("cmc_backend", "auto"), twak_backend=cfg.get("twak_backend", "auto"),
                     run_hours=cfg.get("run_hours"), lock=cfg.get("locked", False), live=cfg.get("live", False))
