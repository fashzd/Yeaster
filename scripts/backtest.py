#!/usr/bin/env python3
"""Yeaster native backtester — pull real CMC OHLC, replay the brain, sweep exits.

Reads the live SCREEN detectors + sizing rails + finalized preset and replays
them over historical daily OHLC (point-in-time, costs + exits modeled). It NEVER
touches the live trading path and only uses OHLCV-reconstructible signals.

    # 1) cache real daily OHLC for the tradeable whitelist (needs CMC_API_KEY)
    python scripts/backtest.py --pull
    python scripts/backtest.py --pull --symbols CAKE,AVAX,INJ --count 400

    # 2) one backtest of the finalized preset on the cached bars
    python scripts/backtest.py --run

    # 3) the trailing-stop study (the headline question)
    python scripts/backtest.py --sweep-trailing

Reports are written under data/backtests/reports/.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Populate os.environ from .env (repo root) for keys not already set, BEFORE
    yeaster.core.settings is imported/cached. Dependency-free."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

from yeaster.backtest import data as bt_data  # noqa: E402
from yeaster.backtest.data import CACHE_DIR, CachedSource  # noqa: E402
from yeaster.backtest.engine import BacktestConfig, preset_exit, run_backtest  # noqa: E402
from yeaster.backtest.exits import ExitConfig  # noqa: E402
from yeaster.backtest.report import (  # noqa: E402
    result_to_json, sweep_table, sweep_to_json, text_summary,
)
from yeaster.backtest.sweep import sweep_brackets, sweep_trailing  # noqa: E402
from yeaster.core.settings import get_settings  # noqa: E402
from yeaster.core.universe import UNIVERSE  # noqa: E402

REPORT_DIR = _REPO_ROOT / "data" / "backtests" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _write(name: str, text: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def cmd_pull(args) -> int:
    key = get_settings().cmc_api_key
    if not key:
        print("CMC_API_KEY not set (put it in .env or the environment).", file=sys.stderr)
        return 2
    syms = ([s.strip().upper() for s in args.symbols.split(",") if s.strip()]
            if args.symbols else list(UNIVERSE))
    print(f"Pulling daily OHLC for {len(syms)} symbols (count={args.count}) -> {CACHE_DIR}")
    counts = bt_data.pull_universe(syms, key, count=args.count)
    ok = sum(1 for n in counts.values() if n > 0)
    print(f"\nCached {ok}/{len(syms)} symbols with data.")
    return 0


def _base_config(args) -> BacktestConfig:
    return BacktestConfig(
        start=args.start, end=args.end,
        fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
        max_open_positions=args.max_open, starting_equity=args.equity,
    )


def cmd_run(args) -> int:
    source = CachedSource()
    if not source.symbols():
        print("No cached OHLC. Run `--pull` first.", file=sys.stderr)
        return 2
    cfg = _base_config(args)
    if args.trailing is not None:
        ex = preset_exit()
        cfg = BacktestConfig(**{**cfg.__dict__, "exit": ExitConfig(
            stop_pct=ex.stop_pct, tp_pct=ex.tp_pct, trailing_pct=args.trailing, trailing_mode="fixed")})
    result = run_backtest(source, cfg)
    print(text_summary(result))
    path = _write(f"run-{_stamp()}.json", result_to_json(result))
    print(f"\n  JSON: {path}")
    return 0


def cmd_sweep(args) -> int:
    source = CachedSource()
    if not source.symbols():
        print("No cached OHLC. Run `--pull` first.", file=sys.stderr)
        return 2
    rows = sweep_trailing(source, _base_config(args))
    print(sweep_table(rows))
    path = _write(f"sweep-trailing-{_stamp()}.json", sweep_to_json(rows))
    print(f"\n  JSON: {path}")
    return 0


def cmd_sweep_brackets(args) -> int:
    source = CachedSource()
    if not source.symbols():
        print("No cached OHLC. Run `--pull` first.", file=sys.stderr)
        return 2
    rows = sweep_brackets(source, _base_config(args))
    print(sweep_table(rows))
    path = _write(f"sweep-brackets-{_stamp()}.json", sweep_to_json(rows))
    print(f"\n  JSON: {path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Yeaster native backtester")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--pull", action="store_true", help="fetch + cache real CMC OHLC")
    g.add_argument("--run", action="store_true", help="run one backtest of the preset")
    g.add_argument("--sweep-trailing", dest="sweep", action="store_true", help="trailing-stop study")
    g.add_argument("--sweep-brackets", dest="sweep_brackets", action="store_true",
                   help="full exit-bracket study (stop x take-profit, ATR trail)")
    p.add_argument("--symbols", help="comma-separated symbols (pull); default = tradeable whitelist")
    p.add_argument("--count", type=int, default=400, help="daily bars to pull per symbol")
    p.add_argument("--start", help="ISO start date (YYYY-MM-DD)")
    p.add_argument("--end", help="ISO end date (YYYY-MM-DD)")
    p.add_argument("--fee-bps", type=float, default=25.0)
    p.add_argument("--slippage-bps", type=float, default=25.0)
    p.add_argument("--max-open", type=int, default=5)
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--trailing", type=float, help="override trailing_pct for --run (fraction, e.g. 0.10)")
    args = p.parse_args()

    if args.pull:
        return cmd_pull(args)
    if args.run:
        return cmd_run(args)
    if args.sweep:
        return cmd_sweep(args)
    if args.sweep_brackets:
        return cmd_sweep_brackets(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
