"""CoinMarketCap Skill Hub client.

The Skill Hub (separate from the Data MCP) runs rich server-side analytical
pipelines via ``execute_skill(unique_name, parameters)``. Skill ``unique_name``s
are the hub's API and are kept verbatim; the wrapper functions here are Yeaster's
own. Each wrapper returns a normalized evidence read, failing OPEN where a skill
outage must not freeze the agent.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, Optional

import requests

from yeaster.core.settings import get_settings
from yeaster.core.universe import STABLES

HTTP_TIMEOUT = 60


# A runtime override lets a tick force skills off (e.g. mock/offline mode) without
# touching settings. None => honor settings.
_ENABLED_OVERRIDE: Optional[bool] = None


def set_enabled(flag: Optional[bool]) -> None:
    global _ENABLED_OVERRIDE
    _ENABLED_OVERRIDE = flag


def available() -> bool:
    if _ENABLED_OVERRIDE is not None:
        return _ENABLED_OVERRIDE
    s = get_settings()
    return bool(s.use_skills and (s.cmc_mcp_api_key or s.cmc_api_key))


def _key() -> Optional[str]:
    s = get_settings()
    return s.cmc_mcp_api_key or s.cmc_api_key


def call_skill(unique_name: str, parameters: Optional[dict] = None, timeout: int = HTTP_TIMEOUT) -> dict[str, Any]:
    """Run a Skill Hub skill, returning its parsed evidence pack (dict)."""
    key = _key()
    if not key:
        raise RuntimeError("CMC key not set")
    headers = {"X-CMC-MCP-API-KEY": key, "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "execute_skill",
                          "arguments": {"unique_name": unique_name, "parameters": parameters or {}}}}
    url = get_settings().cmc_skill_hub_url
    # x402: when enabled, settle a per-request micropayment for the premium skill
    # call by attaching a signed X-PAYMENT header (eager) and logging the receipt.
    from yeaster.execution import x402
    if x402.enabled():
        r = x402.X402Interceptor().request("POST", url, json_body=payload, headers=headers, timeout=timeout)
    else:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    body = r.text
    if "text/event-stream" in r.headers.get("Content-Type", ""):
        for ln in body.splitlines():
            s = ln.strip()
            if s.startswith("data:"):
                c = s[5:].strip()
                if c and c != "[DONE]":
                    body = c
    msg = json.loads(body)
    if "error" in msg:
        raise RuntimeError(f"skill-hub error: {msg['error']}")
    content = (msg.get("result") or {}).get("content") or []
    txt = next((b.get("text") for b in content if b.get("type") == "text"), "")
    if not txt:
        return {}
    outer = json.loads(txt)
    inner = outer.get("result", outer) if isinstance(outer, dict) else {}
    out = inner.get("output") if isinstance(inner, dict) else None
    if isinstance(out, str):
        try:
            return json.loads(out)
        except Exception:
            return {"raw": out}
    return inner if isinstance(inner, dict) and inner else (outer if isinstance(outer, dict) else {})


def _data(d: dict) -> dict:
    """Unwrap the inconsistent {output|result|data} envelope to the evidence dict."""
    for _ in range(8):
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                return {}
        if not isinstance(d, dict):
            return {}
        for k in ("output", "result", "data"):
            if isinstance(d.get(k), (str, dict)):
                d = d[k]
                break
        else:
            return d
    return d if isinstance(d, dict) else {}


# ── posture / regime ─────────────────────────────────────────────────────────

_REGIME_GO = {"trend_expansion"}
_REGIME_STANDDOWN = {"range_chop", "liquidation_stress", "overheated_longs", "mixed_distribution"}


def market_posture(time_window: str = "7d") -> dict[str, Any]:
    """Top posture: hunt / selective / stand_down. Fails OPEN to selective."""
    try:
        d = _data(call_skill("detect_market_regime", {"time_window": time_window}))
    except Exception as e:
        return {"regime": None, "posture": "selective", "error": f"{type(e).__name__}: {str(e)[:70]}"}
    rep = d.get("report") or {}
    reg = (rep.get("market_regime") or "").lower()
    posture = "hunt" if reg in _REGIME_GO else "stand_down" if reg in _REGIME_STANDDOWN else "selective"
    return {"regime": reg, "conviction": rep.get("conviction"),
            "action": (d.get("action_guidance") or {}).get("primary_action"), "posture": posture}


# ── discovery ────────────────────────────────────────────────────────────────

_CAND_KEYS = ("symbol", "ticker", "coinSymbol", "asset", "name")


def scan_breakouts(whitelist: set[str], top_n: int = 8) -> list[dict[str, Any]]:
    """Live breakout discovery across the whole market, intersected with the universe."""
    try:
        d = call_skill("scan_spot_altcoin_breakout_with_social_confirmation",
                       {"top_n": top_n, "listing_timeframe": "24h", "ohlcv_timeframe": "4h", "limit": 300})
    except Exception:
        return []
    rep = (_data(d) or {}).get("report") or {}
    out, seen = [], set()
    wl = {s.upper() for s in whitelist}
    for bucket, src in (("analyzed_top", "scanner"), ("backup_candidates", "scanner_backup")):
        for c in rep.get(bucket) or []:
            sym = next((str(c[k]).upper() for k in _CAND_KEYS if isinstance(c, dict) and c.get(k)), None)
            if not sym or sym in seen or sym not in wl or sym in STABLES:
                continue
            seen.add(sym)
            out.append({"symbol": sym, "source": src, "vol_ratio": c.get("volume_ratio"),
                        "rsi_delta": c.get("rsi_delta"), "narrative": c.get("narrative_status")})
    return out


def overview_candidates(whitelist: set[str]) -> list[dict[str, Any]]:
    """daily_market_overview multi-lane candidate queue, intersected with the universe."""
    try:
        d = _data(call_skill("daily_market_overview", {"preview": True}))
    except Exception:
        return []
    wl = {s.upper() for s in whitelist}
    out, seen = [], set()
    for bucket, lane in (("watchlist", "overview_watch"), ("trader_readouts", "overview_readout")):
        for c in d.get(bucket) or []:
            sym = str(c.get("symbol", "")).upper()
            if sym and sym in wl and sym not in STABLES and sym not in seen:
                seen.add(sym)
                out.append({"symbol": sym, "lane": lane,
                            "thesis": c.get("thesis") or c.get("setup_type")})
    return out


# ── per-token reads ──────────────────────────────────────────────────────────


def transition(symbol: str, lookback_days: int = 14) -> dict[str, Any]:
    """Accumulation→breakout transition state, or None when no data (skip)."""
    try:
        d = call_skill("detect_accumulation_breakout_transition",
                       {"symbol": symbol, "lookback_days": lookback_days})
    except Exception as e:
        return {"symbol": symbol, "state": None, "error": f"{type(e).__name__}: {str(e)[:80]}"}
    data = _data(d)
    rep = data.get("report") or {}
    dm = data.get("derived_metrics") or {}
    state = rep.get("transition_state")
    if not state:
        return {"symbol": symbol, "state": None, "error": "no-data"}
    return {"symbol": symbol, "state": state, "distance_to_high_pct": dm.get("distance_to_range_high_pct"),
            "range_pct": dm.get("range_pct"), "vol_ratio": dm.get("volume_breakout_ratio"),
            "oi_change_pct": dm.get("oi_change_pct"), "funding": dm.get("funding_rate_latest"),
            "risk_flags": data.get("risk_flags") or []}


def perp_read(symbol: str) -> dict[str, Any]:
    """Light perp-structure read → score: crowded/squeeze −2, bullish +1, bearish −1."""
    try:
        d = _data(call_skill("perp_contract_analysis", {"symbol": symbol, "timeframe": "4h"}))
    except Exception:
        return {"score": 0, "bias": None}
    rep = d.get("report") or d
    bias = str((d.get("action_guidance") or {}).get("bias") or rep.get("perp_bias") or "").lower()
    crowd = str(rep.get("crowding_state") or rep.get("market_state") or "").lower()
    if "squeeze" in crowd or "crowded" in crowd:
        score = -2
    elif any(w in bias for w in ("bull", "up", "long")):
        score = 1
    elif any(w in bias for w in ("bear", "down", "short")):
        score = -1
    else:
        score = 0
    return {"score": score, "bias": bias, "crowding": crowd}


def _profile_text(skill: str, symbol: str) -> tuple[str, dict]:
    try:
        d = _data(call_skill(skill, {"symbol": symbol}))
    except Exception:
        return "", {}
    dr = d.get("decision_report") or {}
    return " ".join(str(dr.get(k, "")) for k in ("conclusion", "analysis")), d


def token_risk(symbol: str) -> Optional[dict]:
    """TWAK native token-risk scorecard {level, audit, provider, warnings} (best-effort)."""
    s = get_settings()
    if not s.use_skills or not shutil.which(s.twak_cli_bin):
        return None
    try:
        proc = subprocess.run([s.twak_cli_bin, "risk", symbol, "--json"],
                              capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return None
        return json.loads(proc.stdout.strip())
    except Exception:
        return None


def token_quality(symbol: str) -> dict[str, Any]:
    """GRADED token quality — a SEPARATE informational axis, NEVER a veto (the SIREN fix).

    Parses the security CLASSIFICATION phrase (negation-safe), so "no honeypot / rug pull"
    boilerplate cannot invert a SAFE verdict. Missing data → low coverage + a soft
    ``holder_unverified`` flag with a NEUTRAL score, never a negative.
    Returns {quality_score:[-1,1], coverage:[0,1], risk_flags:[...], evidence}.
    """
    o_text, _ = _profile_text("onchain_memecoin_analysis", symbol)
    g_text, _ = _profile_text("altcoin_token_profile", symbol)
    tl = (o_text + " " + g_text).lower()
    flags: list[str] = []
    quality = 0.0
    covered = bool(o_text or g_text)

    sec = None
    m = re.search(r"security assessment returns (?:a |an )?['\"]?(safe|unsafe|high[- ]risk|caution)", tl)
    if m:
        sec = m.group(1)
        if sec == "safe":
            quality += 0.4
        else:
            quality -= 0.6
            flags.append("security_flagged")
    if re.search(r"honeypot (?:risk )?(?:detected|present|flagged|:\s*yes|=\s*true)", tl):
        flags.append("honeypot_detected"); quality -= 0.6
    if re.search(r"(?:liquidity (?:is )?(?:not locked|unlocked)|lp (?:is )?not locked|"
                 r"unlocked liquidity (?:detected|present|flagged))", tl):
        flags.append("liquidity_unlocked"); quality -= 0.3

    top10 = None
    for pat in (r"([0-9.]+)\s*%\s*(?:for|of)\s*the\s*top[\s-]*10",
                r"top[\s-]*10[^0-9]{0,18}([0-9.]+)\s*%", r"top10 hold[\s]*([0-9.]+)\s*%"):
        mm = re.search(pat, tl)
        if mm:
            top10 = float(mm.group(1)); break
    if top10 is not None:
        if top10 >= 60:
            flags.append("top10_high"); quality -= 0.4
        elif top10 <= 35:
            quality += 0.2

    tax = None
    mt = re.search(r"([0-9.]+)\s*%\s*buy and sell tax", tl) or re.search(r"\btax[^0-9]{0,12}([0-9.]+)\s*%", tl)
    if mt:
        tax = float(mt.group(1))
        if tax >= 10:
            flags.append("tax_high"); quality -= 0.5

    twak_ev: dict[str, Any] = {}
    twak = token_risk(symbol)
    if twak:
        warns = [str(w).lower() for w in (twak.get("warnings") or [])]
        lvl = (twak.get("level") or "").lower()
        is_honeypot = any("honeypot" in w for w in warns)
        is_malicious = any(k in w for w in warns for k in ("malicious", "scam", "rug"))
        if is_honeypot and "honeypot_detected" not in flags:
            flags.append("honeypot_detected"); quality -= 0.6
        if is_malicious:
            flags.append("twak_malicious")
            if "security_flagged" not in flags:
                flags.append("security_flagged"); quality -= 0.6
        if not (is_honeypot or is_malicious):
            if lvl == "high":
                flags.append("twak_high_risk")
            elif lvl == "medium":
                flags.append("twak_caution")
            if any("proxy" in w for w in warns):
                flags.append("twak_proxy")
        twak_ev = {"twak_level": twak.get("level"), "twak_audit": twak.get("audit"),
                   "twak_provider": twak.get("provider"), "twak_warnings": twak.get("warnings")}

    holder_verified = top10 is not None or ("holder" in tl and "%" in tl)
    if not holder_verified:
        flags.append("holder_unverified")
    coverage = 1.0 if (sec is not None and holder_verified) else 0.5 if covered else 0.0
    quality = max(-1.0, min(1.0, quality))
    return {"quality_score": quality, "coverage": coverage, "risk_flags": flags,
            "evidence": {"security": sec, "top10_share": top10, "tax": tax, "verified": holder_verified, **twak_ev}}


HARD_BLOCK_FLAGS = {"security_flagged", "honeypot_detected", "tax_high", "liquidity_unlocked"}
