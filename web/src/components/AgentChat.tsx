"use client";

import { useEffect, useRef, useState } from "react";
import { Send, User, Bot, Loader2 } from "lucide-react";
import { api, type ChatReply } from "@/lib/api";
import TokenChart from "./TokenChart";

type Msg = {
  role: "user" | "agent";
  text: string;
  pack?: any;
  trade?: any;
};

export default function AgentChat({
  live, guardEnabled, locked = false, onRunCycle, onChanged, onGuard, onMode, onAutonomy,
}: {
  live: boolean;
  guardEnabled: boolean;
  locked?: boolean;
  onRunCycle: () => void;
  onChanged: () => void;
  onGuard: (on: boolean) => void;
  onMode: (live: boolean) => void;
  onAutonomy: (on: boolean) => void;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "agent", text: "I'm Yeaster. Ask me about the market, a token ($ETH), or tell me to buy/sell, run a cycle, or toggle guard." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function dispatch(action: { type: string; [k: string]: any }) {
    const twak_backend = live ? "auto" : "paper";
    if (action.type === "manual_trade") {
      const body =
        action.side === "buy"
          ? { from_asset: "USDC", to_asset: action.symbol, amount_pct: action.pct, twak_backend, guard_enabled: guardEnabled }
          : { from_asset: action.symbol, to_asset: "USDC", amount_pct: 1.0, twak_backend, guard_enabled: guardEnabled };
      const res = await api.manual(body).catch((e) => ({ ok: false, error: String(e) }));
      setMsgs((m) => [...m, { role: "agent", text: res.ok ? "Trade executed." : `Trade ${res.guard ?? "failed"}.`, trade: res }]);
      onChanged();
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
    if (!text || busy || locked) return;
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
        <span className="text-mute mono text-[10px]">$SYM · buy 5% CAKE · sell ETH · run a cycle · guard off</span>
      </div>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {msgs.map((m, i) => (
          <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "agent" && <div className="blob blob-pill grid h-7 w-7 shrink-0 place-items-center"><Bot size={13} className="text-[var(--violet)]" /></div>}
            <div className={`max-w-[80%] ${m.role === "user" ? "order-first" : ""}`}>
              <div
                className="rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed"
                style={{ background: m.role === "user" ? "rgba(139,123,255,0.16)" : "rgba(255,255,255,0.05)" }}
              >
                {m.text}
              </div>
              {m.pack && <PackCard pack={m.pack} />}
              {m.trade && <TradeCard trade={m.trade} />}
            </div>
            {m.role === "user" && <div className="blob blob-pill grid h-7 w-7 shrink-0 place-items-center"><User size={13} className="text-[var(--aqua)]" /></div>}
          </div>
        ))}
        {busy && <div className="text-mute flex items-center gap-2 text-xs"><Loader2 size={12} className="animate-spin" /> thinking…</div>}
        <div ref={endRef} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={locked ? "chat locked — committed run in progress" : "Message Yeaster…"}
          disabled={locked}
          className="mono flex-1 rounded-full bg-black/25 px-4 py-2.5 text-[13px] text-soft outline-none placeholder:text-[var(--ink-mute)] disabled:opacity-50"
        />
        <button onClick={send} disabled={busy || locked} className="blob blob-pill grid h-10 w-10 place-items-center disabled:opacity-50" style={{ color: "var(--aqua)" }}>
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
