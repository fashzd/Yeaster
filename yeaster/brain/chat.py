"""The conversational agent — talk to Yeaster, or command it.

Hybrid: fast deterministic parsing for explicit commands (buy/sell, guard, mode,
run, $SYM lookups), and an LLM-driven turn for everything else — context-aware
(wallet, positions, posture), returning {reply, pack, action} like a desk analyst.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from yeaster.brain import llm
from yeaster.core.universe import ALLOWLIST, is_whitelisted
from yeaster.execution.twak import TwakBroker
from yeaster.market import cmc, skills
from yeaster.runtime import state as state_mod

PERSONA = (
    "You are Yeaster, an autonomous momentum trading agent on BNB Smart Chain, talking to your operator in "
    "a compact chat UI. You reason in four passes — SCREEN (scout candidates), GRADE (rate them across "
    "technicals, derivatives, whale flow, sector rotation, unlocks, social + an always-on scam/honeypot "
    "safety axis), VET (adversarial critic + hard safety blocks), COMMIT (a bold lead AI picks one and "
    "sizes it). You execute via Trust Wallet self-custody with native auto-brackets (8% stop, 16% "
    "take-profit, 3% trailing), behind a non-bypassable firewall. You can ONLY trade the 148 "
    "competition-whitelisted tokens (BNB/BTCB excluded). You run on paper until the operator opens the "
    "mainnet gate.\n\n"
    "STYLE: `reply` is 1-3 SHORT sentences — answer the question, no lectures, no capability lists. Put "
    "analytical content (numbers, comparisons, reads) into `pack.rows` (3-7 short label/value rows + a one-"
    "line `read`), NOT into prose. Greetings get a friendly one-liner, pack=null. Be a sharp analyst, honest "
    "about risk; 'do nothing' is valid.\n\n"
    "Answer wallet/balance/holdings questions DIRECTLY from context.wallet (total_usd + tokens). Answer "
    "follow-ups from earlier [card] lines. Respond with ONE JSON object: "
    '{"reply":"...","pack":{"source":"...","rows":[{"label":"..","value":"..","tone":"positive|negative|neutral"}],'
    '"read":".."} or null, "action":{"type":"<run_cycle|manual_trade|market_overview|deep_analysis|none>",'
    '"symbol":"..","from_asset":"..","to_asset":"..","amount_pct":0.05}}'
)


def _last_user(messages: list[dict]) -> str:
    for m in reversed(messages or []):
        if (m.get("role") or "") in ("user", "human"):
            return str(m.get("text") or m.get("content") or "")
    return ""


def _live_context(context: dict) -> dict[str, Any]:
    ctx: dict[str, Any] = {"guard_enabled": context.get("guard_enabled", True),
                           "mode": "live" if context.get("live") else "paper",
                           "whitelist_count": len(ALLOWLIST)}
    try:
        snap = cmc.build_snapshot("auto")
        s = snap.structure
        ctx["market"] = {"regime": s.regime_hint, "breadth": s.breadth, "fear_greed": s.fear_greed_index,
                         "btc": s.btc_direction}
        if skills.available():
            ctx["posture"] = skills.market_posture().get("posture")
    except Exception:
        pass
    try:
        broker = TwakBroker("cli" if context.get("live") else "auto")
        pf = broker.portfolio()
        ctx["wallet"] = {"address": pf.address, "total_usd": pf.total_value_usd,
                         "tokens": [{"symbol": b.symbol, "balance": b.balance, "value_usd": b.value_usd} for b in pf.balances]}
    except Exception:
        pass
    st = state_mod.load()
    if st.get("positions"):
        ctx["positions"] = list(st["positions"].keys())
    return ctx


def respond(messages: list[dict], context: Optional[dict] = None) -> dict[str, Any]:
    context = context or {}
    text = _last_user(messages).strip()
    low = text.lower()

    # ── fast deterministic commands ──────────────────────────────────────
    m = re.match(r"^buy\s+(\d+(?:\.\d+)?)\s*%\s+\$?([a-z0-9]{2,12})$", low)
    if m:
        sym = m.group(2).upper()
        if context.get("guard_enabled", True) and not is_whitelisted(sym):
            return {"reply": f"{sym} isn't on the 148-token whitelist — switch Guard OFF to trade it, or name a whitelisted symbol."}
        return {"reply": f"Placing a {m.group(1)}% buy into {sym}.",
                "action": {"type": "manual_trade", "side": "buy", "symbol": sym, "pct": float(m.group(1)) / 100.0}}

    m = re.match(r"^sell\s+(?:all\s+)?\$?([a-z0-9]{2,12})$", low)
    if m:
        return {"reply": f"Selling {m.group(1).upper()} back to the reserve.",
                "action": {"type": "manual_trade", "side": "sell", "symbol": m.group(1).upper(), "pct": 1.0}}

    if re.search(r"\bguard\s+(on|off)\b", low):
        on = "on" in re.search(r"\bguard\s+(on|off)\b", low).group(1)
        return {"reply": f"Firewall {'ON — every trade checked.' if on else 'OFF — operator override (still logged to proof).'}",
                "action": {"type": "guard_toggle", "enabled": on}}

    if re.search(r"\bswitch\b.*\b(live|paper)\b|\b(go\s+)?(live|paper)\s+mode\b", low):
        live = "live" in low
        return {"reply": f"Switched to {'LIVE' if live else 'PAPER'} trading.",
                "action": {"type": "mode_toggle", "live": live}}

    if re.search(r"\b(run|start|execute|do)\b.*\b(cycle|tick|trade)\b", low):
        return {"reply": "Running a full reasoning cycle — watch the terminal.", "action": {"type": "run_cycle"}}

    if re.search(r"\bautonom", low) and re.search(r"\b(on|off|start|stop)\b", low):
        on = bool(re.search(r"\b(on|start)\b", low))
        return {"reply": f"Autonomous loop {'started' if on else 'stopped'}.",
                "action": {"type": "autonomy_toggle", "enabled": on}}

    if re.search(r"(market overview|morning brief|how.?s the (market|tape)|what.?s the market)", low):
        return {"reply": _overview_reply(), "pack": _market_pack()}

    m = re.match(r"^\$?([a-z0-9]{2,12})\??$", low)
    if m and is_whitelisted(m.group(1).upper()):
        return _token_pack(m.group(1).upper())

    # ── LLM-driven turn (context-aware Q&A + analysis) ───────────────────
    if not text:
        return {"reply": "Ask me about the market, a token ($ETH), or tell me to buy/sell, run a cycle, or toggle guard/mode."}
    if not llm.available():
        return {"reply": "My language model isn't reachable, but my trading brain runs. Try: $ETH, 'market overview', 'buy 5% CAKE', 'run a cycle', or 'guard off'."}

    ctx = _live_context(context)
    convo = [f"{('assistant' if x.get('role') in ('agent','assistant') else 'user')}: {x.get('text') or x.get('content')}"
             for x in (messages or [])[-10:]]
    user = "Context:\n" + json.dumps(ctx, default=str)[:5000] + "\n\nConversation:\n" + "\n".join(convo)
    try:
        out = llm.complete_json(PERSONA, user)
    except llm.LLMUnavailable:
        return {"reply": "Couldn't reach my language model — try $ETH or 'market overview'."}

    reply = str(out.get("reply") or "").strip() or "—"
    action = out.get("action") if isinstance(out.get("action"), dict) else None
    pack = _clean_pack(out.get("pack"))

    # resolve data actions server-side so a real card appears
    if action and action.get("type") == "deep_analysis" and action.get("symbol"):
        tp = _token_pack(str(action["symbol"]).upper())
        return {"reply": reply, "pack": tp.get("pack")}
    if action and action.get("type") == "market_overview":
        return {"reply": reply, "pack": _market_pack()}
    if action and action.get("type") == "manual_trade" and not context.get("guard_enabled", True) is False:
        sym = str(action.get("symbol") or action.get("to_asset") or "").upper()
        if sym and (is_whitelisted(sym) or not context.get("guard_enabled", True)):
            return {"reply": reply, "action": {"type": "manual_trade", "side": "buy",
                    "symbol": sym, "pct": float(action.get("amount_pct") or 0.05)}}
    if action and action.get("type") in ("run_cycle", "guard_toggle", "mode_toggle", "autonomy_toggle"):
        return {"reply": reply, "action": action}
    return {"reply": reply, "pack": pack}


def _clean_pack(pack: Any) -> Optional[dict]:
    if not isinstance(pack, dict) or not isinstance(pack.get("rows"), list):
        return None
    rows = [[str(r.get("label", ""))[:60], str(r.get("value", ""))[:120],
             r.get("tone") if r.get("tone") in ("positive", "negative", "neutral") else "neutral"]
            for r in pack["rows"][:8] if isinstance(r, dict) and r.get("label")]
    if not rows:
        return None
    return {"kind": "analysis", "source": str(pack.get("source") or "analysis")[:60], "rows": rows,
            "read": str(pack.get("read") or "")[:240] or None}


# ── data cards ───────────────────────────────────────────────────────────────


def _market_pack() -> dict[str, Any]:
    snap = cmc.build_snapshot("auto")
    s = snap.structure
    posture = skills.market_posture() if skills.available() else {"posture": "selective", "regime": None}
    movers = sorted((a for a in snap.assets if not a.is_stablecoin and a.percent_change_24h is not None),
                    key=lambda a: a.percent_change_24h or 0, reverse=True)[:6]
    return {"kind": "market", "posture": posture,
            "structure": {"regime_hint": s.regime_hint, "breadth": s.breadth, "fear_greed": s.fear_greed_index,
                          "btc_direction": s.btc_direction, "btc_dominance": s.btc_dominance_pct},
            "movers": [{"symbol": a.symbol, "pct_24h": a.percent_change_24h, "pct_7d": a.percent_change_7d} for a in movers]}


def _overview_reply() -> str:
    try:
        snap = cmc.build_snapshot("auto")
        s = snap.structure
        p = (skills.market_posture().get("posture") if skills.available() else "selective")
        return (f"regime {s.regime_hint}, posture {p}, breadth {(s.breadth or 0) * 100:.0f}%, "
                f"Fear&Greed {s.fear_greed_index}, BTC {s.btc_direction}.")
    except Exception:
        return "market read unavailable."


def _token_pack(sym: str) -> dict[str, Any]:
    snap = cmc.build_snapshot("auto")
    a = snap.by_symbol().get(sym)
    if not a:
        return {"reply": f"No live data for {sym} right now."}
    rows = [
        ["price", f"${a.price_usd:,.6f}".rstrip("0").rstrip("."), "neutral"],
        ["24h", f"{a.percent_change_24h:+.2f}%" if a.percent_change_24h is not None else "—",
         "positive" if (a.percent_change_24h or 0) >= 0 else "negative"],
        ["7d", f"{a.percent_change_7d:+.2f}%" if a.percent_change_7d is not None else "—",
         "positive" if (a.percent_change_7d or 0) >= 0 else "negative"],
        ["trend", a.ema_trend, "positive" if a.ema_trend == "bullish" else "negative" if a.ema_trend == "bearish" else "neutral"],
    ]
    read = f"{sym}: {a.ema_trend} structure, 24h {a.percent_change_24h:+.1f}%." if a.percent_change_24h is not None else sym
    if skills.available():
        try:
            q = skills.token_quality(sym)
            flags = q.get("risk_flags") or []
            hard = any(f in skills.HARD_BLOCK_FLAGS for f in flags)
            rows.append(["safety", f"q{q['quality_score']:+.1f} · {', '.join(flags) if flags else 'clear'}",
                         "negative" if hard else "positive"])
            read += " ⚠ safety flag" if hard else ""
        except Exception:
            pass
        try:
            t = skills.transition(sym)
            if t.get("state"):
                rows.append(["transition", t["state"], "neutral"])
        except Exception:
            pass
    return {"reply": read, "pack": {"kind": "token", "symbol": sym, "chart_symbol": sym, "rows": rows}}
