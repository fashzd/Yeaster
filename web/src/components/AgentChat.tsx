"use client";

import { useEffect, useRef, useState } from "react";
import { Send, User, Bot, Loader2, Trash2 } from "lucide-react";
import { api, type ChatReply } from "@/lib/api";
import TokenChart from "./TokenChart";

type Msg = {
  role: "user" | "agent";
  text: string;
  pack?: any;
  trade?: any;
  pending?: any;        // a proposed manual swap awaiting operator approval
  activity?: any;       // an executed trade event (entry/exit) from any path
};

const GREETING: Msg = {
  role: "agent",
  text: "I'm Yeaster. Ask me about the market, a token ($ETH), or tell me to buy/sell, run a cycle, or toggle guard.",
};

const BUSY_LINES = [
  "Yeaster is busy hunting your next trade…",
  "Crunching the tape — back in a sec…",
  "Heads down in the order book…",
  "Reasoning through screen → grade → vet → commit…",
  "On the hunt — chat reopens when the run finishes.",
];

export default function AgentChat({
  live, guardEnabled, locked = false, agentBusy = false, onRunCycle, onChanged, onGuard, onMode, onAutonomy,
}: {
  live: boolean;
  guardEnabled: boolean;
  locked?: boolean;
  agentBusy?: boolean;
  onRunCycle: () => void;
  onChanged: () => void;
  onGuard: (on: boolean) => void;
  onMode: (live: boolean) => void;
  onAutonomy: (on: boolean) => void;
}) {
  const [busyLine] = useState(() => BUSY_LINES[Math.floor(Date.now() / 1000) % BUSY_LINES.length]);
  const blocked = locked || agentBusy;
  // persist the conversation across refreshes (memory-aware: the history is sent to the LLM each turn)
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    if (typeof window !== "undefined") {
      try { const j = localStorage.getItem("yeaster-chat"); if (j) return JSON.parse(j); } catch { /* */ }
    }
    return [GREETING];
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { try { localStorage.setItem("yeaster-chat", JSON.stringify(msgs.slice(-60))); } catch { /* */ } }, [msgs]);

  function clearChat() {
    setMsgs([GREETING]);
    try { localStorage.removeItem("yeaster-chat"); } catch { /* */ }
  }

  // Poll the unified (per-mode) trade feed and surface NEW entries/exits as cards —
  // covers autonomous, manual, and run-a-tick trades. Seed `seen` from the restored
  // history so a refresh never replays old cards; re-prime when the mode flips.
  const seen = useRef<Set<string>>(new Set(msgs.filter((m) => m.activity).map((m) => m.activity.id)));
  const primed = useRef(false);
  useEffect(() => {
    primed.current = false;   // re-prime on mode change so paper/live feeds stay separate
    let stop = false;
    async function poll() {
      const r = await api.activity(live ? "live" : "paper").catch(() => null);
      if (stop || !r) return;
      const events = r.activity || [];
      if (!primed.current) { events.forEach((e: any) => seen.current.add(e.id)); primed.current = true; return; }
      const fresh = events.filter((e: any) => !seen.current.has(e.id));
      if (fresh.length) {
        fresh.forEach((e: any) => seen.current.add(e.id));
        setMsgs((m) => [...m, ...fresh.map((e: any) => ({ role: "agent" as const, text: "", activity: e }))]);
      }
    }
    poll();
    const t = setInterval(poll, 5000);
    return () => { stop = true; clearInterval(t); };
  }, [live]);

  async function executeTrade(action: { type: string; [k: string]: any }) {
    const twak_backend = live ? "auto" : "paper";
    const body =
      action.side === "buy"
        ? { from_asset: "USDT", to_asset: action.symbol, amount_pct: action.pct, twak_backend, guard_enabled: guardEnabled }
        : { from_asset: action.symbol, to_asset: "USDT", amount_pct: 1.0, twak_backend, guard_enabled: guardEnabled };
    const res = await api.manual(body).catch((e) => ({ ok: false, error: String(e) }));
    // executed trades surface via the activity feed (uniform across all paths);
    // only show an immediate card when the trade did NOT go through (guard reject / error).
    if (!res.ok) setMsgs((m) => [...m, { role: "agent", text: `Trade ${res.guard ?? "failed"}.`, trade: res }]);
    onChanged();
  }

  async function resolvePending(idx: number, approved: boolean) {
    const action = msgs[idx]?.pending;
    setMsgs((m) => m.map((x, i) => (i === idx ? { ...x, pending: { ...x.pending, _resolved: approved ? "approved" : "cancelled" } } : x)));
    if (approved && action) await executeTrade(action);
  }

  async function dispatch(action: { type: string; [k: string]: any }) {
    if (action.type === "manual_trade_pending") {
      setMsgs((m) => [...m, { role: "agent", text: "Review and approve this swap to execute:", pending: action }]);
    } else if (action.type === "manual_trade") {
      await executeTrade(action);                 // legacy direct path
    } else if (action.type === "run_cycle") {
      onRunCycle();
    } else if (action.type === "guard_toggle") {
      onGuard(!!action.enabled);
    } else if (action.type === "mode_toggle") {
      onMode(!!action.live);
    } else if (action.type === "autonomy_toggle") {
      onAutonomy(!!action.enabled);
      onChanged();
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || busy || blocked) return;
    setInput("");
    const next = [...msgs, { role: "user" as const, text }];
    setMsgs(next);
    setBusy(true);
    try {
      const r: ChatReply = await api.chat(
        next.map((m) => ({ role: m.role === "agent" ? "assistant" : "user", text: m.text })),
        { live, guard_enabled: guardEnabled },
      );
      setMsgs((m) => [...m, { role: "agent", text: r.reply, pack: r.pack }]);
      if (r.action) await dispatch(r.action);
    } catch (e) {
      setMsgs((m) => [...m, { role: "agent", text: `Error: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="blob flex h-full flex-col p-5" style={{ minHeight: 460 }}>
      <div className="flex items-center gap-2.5">
        <Bot size={16} className="text-[var(--violet)]" />
        <h2 className="text-sm font-medium tracking-wide">Talk to Yeaster</h2>
        <span className="text-mute mono hidden text-[10px] sm:inline">$SYM · buy 5% CAKE · sell ETH · run a cycle</span>
        <button onClick={clearChat} title="Clear chat" className="text-mute ml-auto hover:text-[var(--rose)]">
          <Trash2 size={14} />
        </button>
      </div>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {msgs.map((m, i) => (
          <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "agent" && <div className="blob blob-pill grid h-7 w-7 shrink-0 place-items-center"><Bot size={13} className="text-[var(--violet)]" /></div>}
            <div className={`max-w-[80%] ${m.role === "user" ? "order-first" : ""}`}>
              {m.text && (
                <div
                  className="rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed"
                  style={{ background: m.role === "user" ? "rgba(139,123,255,0.16)" : "rgba(255,255,255,0.05)" }}
                >
                  {m.text}
                </div>
              )}
              {m.activity && <ActivityCard e={m.activity} />}
              {m.pack && <PackCard pack={m.pack} />}
              {m.pending && <PendingCard p={m.pending} locked={locked} live={live} onResolve={(ok) => resolvePending(i, ok)} />}
              {m.trade && <TradeCard trade={m.trade} />}
            </div>
            {m.role === "user" && <div className="blob blob-pill grid h-7 w-7 shrink-0 place-items-center"><User size={13} className="text-[var(--aqua)]" /></div>}
          </div>
        ))}
        {busy && <div className="text-mute flex items-center gap-2 text-xs"><Loader2 size={12} className="animate-spin" /> thinking…</div>}
        <div ref={endRef} />
      </div>

      {blocked && (
        <div className="text-mute mt-2 flex items-center gap-2 text-[12px]" style={{ color: locked ? "var(--rose)" : "var(--amber)" }}>
          <Loader2 size={12} className="animate-spin" />
          {locked ? "chat locked — committed run in progress" : busyLine}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={locked ? "chat locked — committed run" : agentBusy ? "Yeaster is busy on your task…" : "Message Yeaster…"}
          disabled={blocked}
          className="mono flex-1 rounded-full bg-black/25 px-4 py-2.5 text-[13px] text-soft outline-none placeholder:text-[var(--ink-mute)] disabled:opacity-50"
        />
        <button onClick={send} disabled={busy || blocked} className="blob blob-pill grid h-10 w-10 place-items-center disabled:opacity-50" style={{ color: "var(--aqua)" }}>
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}

function PackCard({ pack }: { pack: any }) {
  if (pack.kind === "analysis") {
    return (
      <div className="blob blob-tight mt-2 p-3">
        <div className="text-mute mb-1.5 text-[10px] uppercase tracking-wider">{pack.source}</div>
        <div className="space-y-1">
          {pack.rows.map((r: any[], i: number) => (
            <div key={i} className="flex items-center justify-between text-[12px]">
              <span className="text-mute">{r[0]}</span>
              <span className="mono text-right" style={{ color: r[2] === "positive" ? "var(--pos)" : r[2] === "negative" ? "var(--neg)" : "var(--ink-soft)" }}>{r[1]}</span>
            </div>
          ))}
        </div>
        {pack.read && <div className="text-soft mt-2 border-t border-white/5 pt-2 text-[12px]">{pack.read}</div>}
      </div>
    );
  }
  if (pack.kind === "token") {
    return (
      <div className="blob blob-tight mt-2 p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="mono text-sm text-soft">{pack.symbol}</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {pack.rows.map((r: any[], i: number) => (
            <div key={i} className="flex items-center justify-between text-[12px]">
              <span className="text-mute">{r[0]}</span>
              <span className="mono" style={{ color: r[2] === "positive" ? "var(--pos)" : r[2] === "negative" ? "var(--neg)" : "var(--ink-soft)" }}>{r[1]}</span>
            </div>
          ))}
        </div>
        <div className="mt-2"><TokenChart symbol={pack.chart_symbol} height={120} /></div>
      </div>
    );
  }
  if (pack.kind === "market") {
    const s = pack.structure;
    return (
      <div className="blob blob-tight mt-2 p-3">
        <div className="grid grid-cols-3 gap-2 text-[12px]">
          <Cell k="regime" v={s.regime_hint} />
          <Cell k="posture" v={pack.posture?.posture} />
          <Cell k="breadth" v={s.breadth != null ? `${(s.breadth * 100).toFixed(0)}%` : "—"} />
          <Cell k="F&G" v={`${s.fear_greed ?? "—"}`} />
          <Cell k="BTC" v={s.btc_direction} />
          <Cell k="dom" v={s.btc_dominance != null ? `${s.btc_dominance.toFixed(1)}%` : "—"} />
        </div>
        <div className="mt-2 space-y-1">
          {(pack.movers ?? []).map((m: any) => (
            <div key={m.symbol} className="flex justify-between text-[12px]">
              <span className="mono text-soft">{m.symbol}</span>
              <span className="mono" style={{ color: (m.pct_24h ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>{(m.pct_24h ?? 0) >= 0 ? "+" : ""}{(m.pct_24h ?? 0).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
}

function Cell({ k, v }: { k: string; v: any }) {
  return (
    <div>
      <div className="text-mute text-[9px] uppercase tracking-wider">{k}</div>
      <div className="mono text-soft">{v ?? "—"}</div>
    </div>
  );
}

function ActivityCard({ e }: { e: any }) {
  const isEntry = e.kind === "entry";
  const pnl = e.pnl_usd;
  const win = pnl != null && pnl >= 0;
  const accent = isEntry ? "var(--aqua)" : win ? "var(--pos)" : pnl != null ? "var(--neg)" : "var(--violet)";
  const title = isEntry ? `Bought ${e.symbol}` : `Sold ${e.symbol}`;
  const reasonLabel: Record<string, string> = {
    stop: "stop-loss", take_profit: "take-profit", trail: "trailing stop", flatten: "kill-switch", mark_out: "closed", exit: "exit",
  };
  return (
    <div className="blob blob-tight mt-2 p-3 text-[12px]" style={{ borderColor: `${accent}55` }}>
      <div className="flex items-center justify-between">
        <span className="font-medium" style={{ color: accent }}>{title}</span>
        {!isEntry && pnl != null && (
          <span className="mono font-semibold" style={{ color: win ? "var(--pos)" : "var(--neg)" }}>
            {win ? "+" : ""}${pnl.toFixed(2)}
          </span>
        )}
      </div>
      <div className="text-mute mt-0.5">
        {isEntry
          ? <>entry @ <span className="mono">${Number(e.price ?? 0).toFixed(4)}</span></>
          : <>{reasonLabel[e.reason] ?? e.reason}</>}
        {e.at && <span className="mono"> · {new Date(e.at).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}

function PendingCard({ p, locked, live, onResolve }:
  { p: any; locked: boolean; live: boolean; onResolve: (ok: boolean) => void }) {
  const verb = p.side === "buy" ? `buy ${(p.pct * 100).toFixed(p.pct < 0.01 ? 2 : 0)}%` : "sell";
  const resolved = p._resolved;
  return (
    <div className="blob blob-tight mt-2 p-3 text-[12px]" style={{ borderColor: "rgba(255,207,106,0.35)" }}>
      <div className="text-mute mb-1 text-[10px] uppercase tracking-wider">trade intent · approval required</div>
      <div className="mono text-soft">{verb} {p.symbol} <span className="text-mute">· {live ? "LIVE" : "paper"}</span></div>
      {!resolved ? (
        <div className="mt-2 flex gap-2">
          <button onClick={() => onResolve(true)} disabled={locked}
            className="blob blob-pill flex-1 py-1.5 text-[12px] font-medium disabled:opacity-40" style={{ color: "var(--lime)" }}>
            ✓ approve
          </button>
          <button onClick={() => onResolve(false)}
            className="blob blob-pill flex-1 py-1.5 text-[12px] font-medium" style={{ color: "var(--rose)" }}>
            ✕ cancel
          </button>
        </div>
      ) : (
        <div className="mt-1.5 text-[11px]" style={{ color: resolved === "approved" ? "var(--lime)" : "var(--mute)" }}>
          {resolved === "approved" ? "approved — executing" : "cancelled"}
        </div>
      )}
    </div>
  );
}

function TradeCard({ trade }: { trade: any }) {
  const r = trade.receipt;
  const ok = trade.ok;
  return (
    <div className="blob blob-tight mt-2 p-3 text-[12px]">
      <div className="flex items-center justify-between">
        <span className="mono text-soft">{trade.intent ?? "trade"}</span>
        <span className="mono" style={{ color: ok ? "var(--pos)" : "var(--warn)" }}>{trade.guard ?? (ok ? "EXECUTED" : "—")}</span>
      </div>
      {trade.rejection_reasons?.length > 0 && <div className="text-mute mt-1">blocked: {trade.rejection_reasons.join(", ")}</div>}
      {r?.tx_hash && (
        <a href={r.explorer_url} target="_blank" rel="noreferrer" className="mono mt-1 block text-[11px] text-[var(--aqua)]">
          tx {r.tx_hash.slice(0, 18)}…
        </a>
      )}
      {trade.proof_block_hash && <div className="text-mute mono mt-1 text-[10px]">proof {trade.proof_block_hash.slice(0, 16)}…</div>}
      {trade.guard_bypassed && <div className="text-[var(--warn)] mt-1 text-[11px]">guard bypassed (logged)</div>}
    </div>
  );
}
