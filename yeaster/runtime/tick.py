"""One autonomous tick: snapshot → think → guard → execute → brackets → proof.

This is the spine the daemon and the API tick endpoint both call. It is fully
live-wired: the same wallet, the same firewall, the same proof ledger — only the
``twak_backend`` (paper / cli) and the mainnet gate decide whether a real swap
is broadcast.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from yeaster.brain import cycle
from yeaster.core.models import CommitRecord, Mandate, OrderTicket
from yeaster.core.settings import get_settings
from yeaster.core.universe import DEFAULT_RESERVE, STABLES, UNIVERSE
from yeaster.execution import brackets, twak
from yeaster.execution.approval import issue_from_guard_log
from yeaster.execution.models import (
    BSC_TESTNET_CHAIN_ID,
    SwapRequest,
    SwapStatus,
)
from yeaster.execution.twak import TwakBroker
from yeaster.guard.firewall import RuntimeState, YeasterGuard
from yeaster.market import cmc, skills
from yeaster.proof import ledger
from yeaster.runtime import state as state_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_manual(*, from_asset: str, to_asset: str, amount_pct: float, twak_backend: str = "auto",
               guard_enabled: bool = True, cmc_backend: str = "auto") -> dict[str, Any]:
    """Operator-driven swap: quote → firewall → execute → proof (no brain).

    Used by the chat ("buy 5% CAKE" / "sell CAKE"). Honors the same guard, the
    same mainnet gate, and seals a proof block like any other action.
    """
    from yeaster.core.universe import is_whitelisted
    mode = state_mod.state_mode(twak_backend)
    st = state_mod.load(mode)
    snap = cmc.build_snapshot(cmc_backend)
    by_sym = snap.by_symbol()
    twak.set_price_oracle(lambda s: getattr(by_sym.get(s.upper()), "price_usd", None))

    broker = TwakBroker(twak_backend)
    pf = broker.portfolio()
    equity = pf.total_value_usd or 0.0
    drawdown = state_mod.update_equity(st, equity)
    # Manual mandate also permits BNB (native) — manual swaps + approval only; the
    # autonomous loop can never pick it (BNB isn't in the momentum UNIVERSE).
    mandate = _build_mandate(None)
    mandate = mandate.model_copy(update={"allowed_assets": sorted({*mandate.allowed_assets, "BNB"})})

    to_asset = to_asset.upper()
    from_asset = from_asset.upper()
    if not (is_whitelisted(to_asset) or to_asset == "BNB"):
        return {"ok": False, "error": f"{to_asset} is not tradeable (whitelist + BNB for manual swaps)."}

    bal = {b.symbol.upper(): b.balance for b in pf.balances}
    p_from = getattr(by_sym.get(from_asset), "price_usd", 1.0) or 1.0
    have = bal.get(from_asset, 0.0)
    amount_in = (have * amount_pct) if from_asset not in STABLES else min(amount_pct * equity / p_from, have)
    if amount_in <= 0:
        return {"ok": False, "error": f"no {from_asset} balance to swap."}

    ticket = OrderTicket(from_asset=from_asset, to_asset=to_asset, amount_pct=amount_pct,
                         confidence=1.0, kind="exit" if to_asset in STABLES else "entry",
                         thesis="manual operator order")
    req = SwapRequest(from_asset=from_asset, to_asset=to_asset, amount_in=amount_in,
                      chain_id=_trade_chain_id(), slippage_tolerance_bps=mandate.max_slippage_bps)
    quote = broker.quote_swap(req)
    guard = YeasterGuard(mandate, safe_mode_latched=st.get("safe_mode_latched", False))
    guard_log = guard.evaluate(ticket, RuntimeState(requested_slippage_bps=quote.expected_slippage_bps,
                                                    portfolio_drawdown_pct=drawdown,
                                                    current_positions=pf.positions_pct,
                                                    safe_mode_active=st.get("safe_mode_latched", False)))
    receipt = None
    if guard_enabled and guard_log.final_decision.value == "EXECUTED":
        token = issue_from_guard_log(quote, guard_log.model_dump())
        receipt = broker.execute_approved_swap(quote, token)
        if receipt.status == SwapStatus.EXECUTED:
            # BNB and stables are not momentum positions — don't open/bracket them.
            if to_asset in STABLES or to_asset == "BNB":
                if from_asset not in STABLES and from_asset != "BNB":
                    state_mod.record_exit(st, from_asset)
            else:
                _open_position(st, broker, twak_backend, to_asset, quote, by_sym, mandate)

    commit_record = CommitRecord(snapshot_hash=snap.snapshot_hash, generated_at=_now(), posture="manual",
                                 ticket=ticket, ticket_kind=ticket.kind, conviction=1.0,
                                 rationale="manual operator order")
    block = ledger.append_proof(snapshot=snap.model_dump(), commit_record=commit_record.model_dump(),
                                guard_log=guard_log.model_dump())
    state_mod.save(st, mode)
    return {
        "ok": receipt is not None and receipt.status == SwapStatus.EXECUTED,
        "intent": f"{amount_pct:.0%} {from_asset} → {to_asset}",
        "guard": guard_log.final_decision.value, "rejection_reasons": guard_log.rejection_reasons,
        "receipt": receipt.model_dump() if receipt else None,
        "guard_bypassed": not guard_enabled,
        "proof_block_hash": block.block_hash,
    }


def _trade_chain_id() -> int:
    return 56 if get_settings().mainnet_unlocked else BSC_TESTNET_CHAIN_ID


def _build_mandate(universe) -> Mandate:
    from yeaster.core.preset import active
    from yeaster.core.universe import ALLOWLIST
    g = active()["guard"]
    # The firewall allowlist is the FULL competition whitelist (so exits to any
    # stable are always possible), regardless of the narrower screen universe.
    allowed = sorted({*ALLOWLIST, *STABLES})
    return Mandate(mandate_id="yeaster", allowed_assets=allowed, max_trade_pct=g["max_trade_pct"],
                   max_position_pct=g["max_position_pct"], max_slippage_bps=g["max_slippage_bps"],
                   hard_drawdown_pct=g["hard_drawdown_pct"])


def _choose_reserve(pf, want: str) -> tuple[str, float]:
    """The funding stable: prefer the requested reserve, else the largest stable balance."""
    bal = {b.symbol.upper(): b.balance for b in pf.balances}
    if bal.get(want.upper(), 0.0) > 0:
        return want.upper(), bal[want.upper()]
    stable_bals = {s: bal.get(s, 0.0) for s in STABLES if bal.get(s, 0.0) > 0}
    if stable_bals:
        sym = max(stable_bals, key=stable_bals.get)
        return sym, stable_bals[sym]
    return want.upper(), 0.0


def run_tick(*, cmc_backend: str = "auto", twak_backend: str = "auto", arm: Optional[str] = None,
             guard_enabled: bool = True, posture_override: Optional[str] = None,
             universe=None, hist: Optional[dict] = None, emit=None) -> dict[str, Any]:
    _emit = emit or (lambda *a: None)
    s = get_settings()
    mode = state_mod.state_mode(twak_backend)
    st = state_mod.load(mode)
    state_mod.roll_day(st)

    # mock data => fully offline/fast (no live skill calls)
    skills.set_enabled(False if cmc_backend == "mock" else None)

    # 1) market snapshot + price oracle for paper pricing
    snap = cmc.build_snapshot(cmc_backend)
    cmc.persist_snapshot(snap)
    by_sym = snap.by_symbol()
    twak.set_price_oracle(lambda sym: getattr(by_sym.get(sym.upper()), "price_usd", None))

    # 2) wallet / equity / drawdown
    broker = TwakBroker(twak_backend)
    pf = broker.portfolio()
    equity = pf.total_value_usd or 0.0
    drawdown = state_mod.update_equity(st, equity)
    mandate = _build_mandate(universe)

    # 2b) manage existing positions first (exits / trailing) — de-risk, always allowed
    from yeaster.runtime import exits as exits_mod
    exit_actions = exits_mod.reconcile(st, broker, by_sym, mandate, twak_backend, emit=_emit)
    if exit_actions:
        pf = broker.portfolio()
        equity = pf.total_value_usd or 0.0
        drawdown = state_mod.update_equity(st, equity)
    unreal = state_mod.unrealized_pnl(st, lambda s: getattr(by_sym.get(s.upper()), "price_usd", None))
    book = state_mod.book_for_llm(st, equity, drawdown, unrealized=unreal)

    # 3) posture
    posture = posture_override or (skills.market_posture().get("posture") if skills.available() else "selective")

    _emit("regime", {"text": f"posture: {posture} · equity ${equity:,.2f} · dd {drawdown:.1%}",
                     "posture": posture, "equity_usd": round(equity, 2), "drawdown_pct": round(drawdown, 4)})

    # 4) think (stream each reasoning pass) — finalized momentum preset
    from yeaster.core.preset import active
    preset = active()
    arm = arm or preset["commit_arm"]
    trace: dict[str, Any] = {}
    result: dict[str, Any] = {}
    for stage, payload in cycle.think_events(snap, hist or {}, posture=posture, equity=equity,
                                             drawdown=drawdown, book=book, arm=arm, universe=universe,
                                             detectors=set(preset["detectors"]), dims=preset["score_dims"]):
        if stage == "result":
            result = payload
        else:
            trace[stage] = payload
            _emit(stage, payload)
    result["reasoning"] = trace
    skills.set_enabled(None)   # clear the per-tick override so other endpoints see true settings

    commit_record = CommitRecord(
        snapshot_hash=snap.snapshot_hash, generated_at=_now(), posture=posture,
        ticket=OrderTicket(**result["ticket"]) if result.get("ticket") else None,
        ticket_kind="entry" if result.get("ticket") else "none",
        conviction=result.get("conviction"), rationale=result.get("rationale"),
        stand_down_reason=None if result.get("ticket") else result.get("rationale"),
        reasoning=result.get("reasoning"),
    )

    guard_log = None
    receipt = None
    quote = None

    if result.get("ticket"):
        receipt, quote, guard_log = _execute_ticket(st, broker, twak_backend, result["ticket"],
                                                    by_sym, pf, mandate, equity, drawdown, guard_enabled, _emit)

    # 4b) ≥1-trade/day compliance — if nothing traded today and the UTC day is near
    # closing, force ONE minimal, safest vetted trade. This is the ONLY place the
    # deterministic arm runs (never a silent substitute for the LLM's organic call).
    _executed = bool(receipt and receipt.status == SwapStatus.EXECUTED)
    if (not _executed and s.daily_compliance and st.get("trades_today", 0) == 0
            and datetime.now(timezone.utc).hour >= s.daily_cutoff_hour):
        from yeaster.brain import commit as commit_pass
        survivors = result.get("survivors") or []
        comp = commit_pass.commit(survivors, arm="det_safety", posture=posture,
                                  equity=equity, drawdown=drawdown, book=book)
        # Size the mandatory trade UP to clear the contest minimum (with margin) — it
        # must execute ≥ the floor, so we never use the tiny conviction-floor size here.
        comp_amt = commit_pass.compliance_amount_pct(equity)
        if comp.get("ticket") and comp_amt:
            comp_ticket = {**comp["ticket"], "amount_pct": comp_amt,
                           "thesis": "daily ≥1-trade compliance (contest minimum size)"}
            _emit("compliance", {"text": f"≥1/day compliance: {comp['pick']} @ ~${comp_amt * equity:.2f} (min trade)",
                                 "pick": comp["pick"]})
            c_receipt, c_quote, c_guard = _execute_ticket(st, broker, twak_backend, comp_ticket,
                                                          by_sym, pf, mandate, equity, drawdown, guard_enabled, _emit)
            if c_receipt:
                receipt, quote, guard_log = c_receipt, c_quote, c_guard
        else:
            st["last_compliance_note"] = "≥1/day: no vetted candidate or wallet can't fund the minimum trade"
            _emit("compliance", {"text": st["last_compliance_note"], "tone": "bad"})

    # proof
    guard_dump = guard_log.model_dump() if guard_log else {
        "mandate_id": "yeaster", "final_decision": "EVIDENCE", "rejection_reasons": [], "safe_mode_active": st.get("safe_mode_latched", False),
    }
    block = ledger.append_proof(snapshot=snap.model_dump(), commit_record=commit_record.model_dump(),
                                guard_log=guard_dump)
    _emit("proof", {"text": f"sealed block {block.block_index} · {block.block_hash[:14]}…",
                    "block_hash": block.block_hash, "block_index": block.block_index})

    st["last_tick_at"] = _now()
    state_mod.save(st, mode)

    tick_result = {
        "tick_at": st["last_tick_at"],
        "backend": {"cmc": snap.backend, "twak": broker.backend},
        "posture": posture,
        "equity_usd": round(equity, 4),
        "drawdown_pct": round(drawdown, 4),
        "reasoning": result.get("reasoning"),
        "decision": {"pick": result.get("pick"), "conviction": result.get("conviction"),
                     "arm": result.get("arm"), "rationale": result.get("rationale"),
                     "stand_down": result.get("stand_down")},
        "graded_top": result.get("graded_top"),
        "blocked": result.get("blocked"),
        "guard": guard_dump if guard_log else None,
        "quote": quote.model_dump() if quote else None,
        "receipt": receipt.model_dump() if receipt else None,
        "proof_block_hash": block.block_hash,
        "safe_mode_latched": st.get("safe_mode_latched", False),
        "positions": st.get("positions", {}),
        "exit_actions": exit_actions,
    }
    _emit("result", tick_result)
    return tick_result


def _execute_ticket(st, broker, twak_backend, ticket_dict, by_sym, pf, mandate, equity, drawdown,
                    guard_enabled, emit):
    """Quote → firewall → execute one entry ticket; open the position + ATR bracket on a fill.
    Shared by the organic decision and the ≥1/day compliance trade. Returns (receipt, quote, guard_log)."""
    ticket = OrderTicket(**ticket_dict)
    reserve, reserve_bal = _choose_reserve(pf, ticket.from_asset)
    ticket = ticket.model_copy(update={"from_asset": reserve})

    price_from = by_sym.get(reserve)
    p_from = price_from.price_usd if price_from else 1.0
    amount_in = min(ticket.amount_pct * equity / max(p_from, 1e-9), reserve_bal) if reserve_bal > 0 \
        else ticket.amount_pct * equity / max(p_from, 1e-9)

    receipt = quote = guard_log = None
    if amount_in <= 0:
        return receipt, quote, guard_log
    # Hard contest floor: the actual USDT spent (amount_in) must clear the minimum
    # notional, or we never place it — a sub-minimum trade risks disqualification.
    # Applies to organic AND compliance trades; the compliance path sizes up to clear it.
    floor = get_settings().min_notional_usd
    if floor > 0 and amount_in * max(p_from, 1e-9) < floor:
        emit("execute", {"text": f"stand down — ${amount_in * max(p_from, 1e-9):.2f} below the ${floor:.2f} minimum trade size",
                         "tone": "bad"})
        return receipt, quote, guard_log

    req = SwapRequest(from_asset=reserve, to_asset=ticket.to_asset, amount_in=amount_in,
                      chain_id=_trade_chain_id(), slippage_tolerance_bps=mandate.max_slippage_bps)
    quote = broker.quote_swap(req)
    runtime = RuntimeState(requested_slippage_bps=quote.expected_slippage_bps,
                           portfolio_drawdown_pct=drawdown, current_positions=pf.positions_pct,
                           safe_mode_active=st.get("safe_mode_latched", False))
    guard = YeasterGuard(mandate, safe_mode_latched=st.get("safe_mode_latched", False))
    guard_log = guard.evaluate(ticket, runtime)
    if guard_log.safe_mode_active:
        st["safe_mode_latched"] = True

    emit("guard", {"text": f"guard {guard_log.final_decision.value}"
                   + (f" — {', '.join(guard_log.rejection_reasons)}" if guard_log.rejection_reasons else ""),
                   "final_decision": guard_log.final_decision.value,
                   "rejection_reasons": guard_log.rejection_reasons})

    if guard_enabled and guard_log.final_decision.value == "EXECUTED":
        token = issue_from_guard_log(quote, guard_log.model_dump())
        receipt = broker.execute_approved_swap(quote, token)
        if receipt.status == SwapStatus.EXECUTED:
            _open_position(st, broker, twak_backend, ticket.to_asset, quote, by_sym, mandate)
            emit("execute", {"text": f"EXECUTED {receipt.amount_out:.4f} {ticket.to_asset} · tx {(receipt.tx_hash or '')[:14]}…",
                             "tx_hash": receipt.tx_hash, "explorer_url": receipt.explorer_url,
                             "amount_out": receipt.amount_out})
        else:
            emit("execute", {"text": f"execution {receipt.status.value}: {receipt.error or ''}",
                             "status": receipt.status.value, "tone": "bad"})
    return receipt, quote, guard_log


def _open_position(st, broker, twak_backend, symbol, quote, by_sym, mandate) -> None:
    """Record the entry and place native stop / take-profit brackets (finalized exit calibration)."""
    from yeaster.core.preset import active
    ex = active()["exit"]
    entry = (quote.amount_in / quote.expected_amount_out) if quote.expected_amount_out else (
        getattr(by_sym.get(symbol), "price_usd", 0.0))
    qty = quote.expected_amount_out
    stop_price = round(entry * (1.0 - ex["stop_pct"]), 10)   # 8% stop — let losers cut, winners run
    tp_price = round(entry * (1.0 + ex["tp_pct"]), 10)       # 16% target
    # Volatility yardstick for the trailing stop (0.0 -> fixed-% trail fallback).
    atr_entry = 0.0
    if ex.get("trailing_mode") == "atr":
        try:
            from yeaster.runtime.atr_provider import atr_at_entry
            atr_entry = atr_at_entry(symbol, int(ex.get("atr_period", 14)))
        except Exception:
            atr_entry = 0.0
    # Approve the just-bought token for selling NOW, so the stop / TP / ATR-trail /
    # kill-flatten can actually execute when they fire (a fresh token has 0 allowance,
    # and the first sell would otherwise revert). No-op off live mainnet.
    try:
        twak.ensure_sell_approval(symbol, _trade_chain_id())
    except Exception:
        pass

    stop_id = tp_id = None
    try:
        specs = brackets.build_bracket_specs(symbol, qty, stop_price, tp_price)
        stop_id = brackets.place(specs["stop"], twak_backend).id
        tp_id = brackets.place(specs["take_profit"], twak_backend).id
    except Exception:
        pass
    state_mod.record_entry(st, symbol, entry, qty, stop_price, tp_price, stop_id, tp_id, atr_entry=atr_entry)
