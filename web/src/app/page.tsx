"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Wallet, ShieldCheck, Boxes, Link2, Power, TrendingUp, Settings, BarChart3,
  Copy, Check, Lock, Timer, X, GraduationCap, Coins, ArrowLeft,
} from "lucide-react";
import Terminal from "@/components/Terminal";
import AgentChat from "@/components/AgentChat";
import YeasterLogo from "@/components/YeasterLogo";
import {
  api, type AgentStatus, type Brackets, type DaemonStatus, type Overview,
  type ProofChain, type Readiness, type Wallet as WalletT,
} from "@/lib/api";

export default function Home() {
  const [online, setOnline] = useState(false);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [agent, setAgent] = useState<AgentStatus | null>(null);
  const [book, setBook] = useState<WalletT | null>(null);        // active trading book (paper/live)
  const [realWallet, setRealWallet] = useState<WalletT | null>(null); // real TWAK self-custody wallet
  const [market, setMarket] = useState<Overview | null>(null);
  const [brackets, setBrackets] = useState<Brackets | null>(null);
  const [proof, setProof] = useState<ProofChain | null>(null);
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null);

  const [live, setLive] = useState(false);
  const [guardEnabled, setGuardEnabled] = useState(true);
  const [runSignal, setRunSignal] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const locked = !!daemon?.locked && !!daemon?.running;

  // chat is busy-locked while a tick streams in the terminal OR the autonomous loop runs
  const [terminalBusy, setTerminalBusy] = useState(false);
  const agentBusy = terminalBusy || (!!daemon?.running && !locked);

  const refresh = useCallback(async () => {
    try {
      await api.health();
      setOnline(true);
      const mode = live ? "live" : "paper";
      const bookBackend = live ? "cli" : "paper";
      const [r, a, b, w, p, d] = await Promise.allSettled([
        api.readiness(), api.agent(mode), api.wallet(bookBackend), api.walletReal(), api.proof(), api.daemon(),
      ]);
      if (r.status === "fulfilled") setReady(r.value);
      if (a.status === "fulfilled") setAgent(a.value);
      if (b.status === "fulfilled") setBook(b.value);
      if (w.status === "fulfilled") setRealWallet(w.value);
      if (p.status === "fulfilled") setProof(p.value);
      if (d.status === "fulfilled") setDaemon(d.value);
    } catch { setOnline(false); }
  }, [live]);

  const refreshMarket = useCallback(async () => {
    const [m, bk] = await Promise.allSettled([api.overview(), api.brackets(live ? "cli" : "paper")]);
    if (m.status === "fulfilled") setMarket(m.value);
    if (bk.status === "fulfilled") setBrackets(bk.value);
  }, [live]);

  useEffect(() => {
    refresh(); refreshMarket();
    const t1 = setInterval(refresh, 8000);
    const t2 = setInterval(refreshMarket, 20000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [refresh, refreshMarket]);

  // the book IS the active mode's wallet (paper store or live chain), fully separated
  const equity = book?.total_value_usd ?? 0;
  const pnl = agent?.realized_pnl_usd ?? 0;

  async function toggleDaemon(force?: boolean) {
    const want = force ?? !daemon?.running;
    // live checks every 2h (after an immediate first tick) so it isn't churning; paper stays fast for demos
    if (!want) await api.daemonStop();
    else await api.daemonStart({ cadence_seconds: live ? 7200 : 120, cmc_backend: live ? "auto" : "mock", twak_backend: live ? "auto" : "paper" });
    refresh();
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-[1500px] px-5 py-6 md:px-8">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="blob blob-pill grid h-11 w-11 place-items-center" style={{ boxShadow: "0 0 18px rgba(52,231,228,0.35)" }}>
            <YeasterLogo size={26} />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Yeaster</h1>
            <p className="text-mute text-[11px]">autonomous trading agent on the BNB chain</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/alpha" className="blob blob-pill flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-[var(--magenta)]" title="Buy the daily alpha (x402)">
            <Coins size={13} /> buy alpha
          </Link>
          <Link href="/learn" className="blob blob-pill flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-[var(--lime)]" title="How Yeaster works">
            <GraduationCap size={13} /> learn
          </Link>
          <Link href="/intelligence" className="blob blob-pill flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-[var(--violet)]" title="Market Intelligence">
            <BarChart3 size={13} /> intel
          </Link>
          <Toggle on={live} onClick={() => !locked && setLive((v) => !v)} onColor="var(--rose)" offColor="var(--aqua)"
            label={live ? "● live" : "○ paper"} title="Live (real CMC + wallet) vs paper" />
          <Toggle on={guardEnabled} onClick={() => !locked && setGuardEnabled((v) => !v)} onColor="var(--lime)" offColor="var(--warn)"
            icon={<ShieldCheck size={13} />} label={`guard ${guardEnabled ? "on" : "off"}`} title="Firewall on/off" />
          <Toggle on={!!daemon?.running} onClick={() => (locked ? setSettingsOpen(true) : toggleDaemon())}
            onColor={locked ? "var(--rose)" : "var(--lime)"} offColor="var(--ink-mute)"
            icon={locked ? <Lock size={13} /> : <Power size={13} />}
            label={daemon?.running ? (locked ? `locked · ${fmtRemain(daemon.remaining_seconds)}` : `auto · ${daemon.loops}`) : "auto off"}
            title="Autonomous loop" />
          <button onClick={() => setSettingsOpen(true)} className="blob blob-pill grid h-9 w-9 place-items-center text-soft" title="Settings">
            <Settings size={15} />
          </button>
          {ready && (
            <div className="blob blob-pill flex items-center gap-1.5 px-3.5 py-2" title={Object.entries(ready.layers).map(([k, v]) => `${k}: ${v.detail}`).join("\n")}>
              <Link2 size={12} className="text-[var(--aqua)]" />
              <span className="mono text-[11px] text-soft">{ready.live_count}/{ready.layer_count}</span>
            </div>
          )}
          <div className="blob blob-pill flex items-center gap-2 px-3.5 py-2">
            <span className="pulse-dot" style={{ color: online ? "var(--pos)" : "var(--neg)" }} />
            <span className="mono text-[11px] text-soft">{online ? "online" : "offline"}</span>
            <span className="blink-blue" title="live link" />
          </div>
        </div>
      </header>

      {/* ── Stat strip ─────────────────────────────────────────── */}
      <section className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label={`book · ${live ? "live" : "paper"}`} value={`$${equity.toFixed(2)}`} />
        <Stat label="P&L" value={`${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}`} tone={pnl >= 0 ? "var(--pos)" : "var(--neg)"} />
        <Stat label="posture" value={market?.posture?.posture ?? "—"} />
        <Stat label="Fear & Greed" value={`${market?.structure?.fear_greed_index ?? "—"}`}
          tone={(market?.structure?.fear_greed_index ?? 50) < 45 ? "var(--neg)" : (market?.structure?.fear_greed_index ?? 50) > 55 ? "var(--pos)" : "var(--warn)"} />
        <Stat label="positions" value={`${agent?.open_positions ?? 0}`} />
        <Stat label="proof" value={proof ? (proof.verified ? `✓ ${proof.count}` : "✗") : "—"}
          tone={proof?.verified ? "var(--pos)" : "var(--neg)"} />
      </section>

      {locked && <LockCountdown remaining={daemon?.remaining_seconds} />}

      {/* ── Terminal + Chat side by side ───────────────────────── */}
      <section className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="h-[540px]">
          <Terminal live={live} guardEnabled={guardEnabled} runSignal={runSignal}
            onBusy={setTerminalBusy} locked={!!daemon?.running}
            remaining={daemon?.remaining_seconds} loops={daemon?.loops}
            onResult={() => { refresh(); refreshMarket(); }} />
        </div>
        <div className="h-[540px]">
          <AgentChat live={live} guardEnabled={guardEnabled} locked={locked} agentBusy={agentBusy}
            onRunCycle={() => setRunSignal((x) => x + 1)}
            onChanged={() => { refresh(); refreshMarket(); }}
            onGuard={setGuardEnabled} onMode={setLive} onAutonomy={(on) => toggleDaemon(on)} />
        </div>
      </section>

      {/* ── Dashboard row ──────────────────────────────────────── */}
      <section className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
        <AgentWalletBlob real={realWallet} book={book} live={live} />
        <MarketBlob market={market} />
        <BracketsBlob brackets={brackets} />
        <ProofBlob proof={proof} />
      </section>

      <footer className="text-mute mt-7 text-center text-[11px]">
        Yeaster · self-custody · 148-token whitelist · mainnet {agent?.mainnet_unlocked ? "OPEN" : "gated"} · proof-secured
      </footer>

      {settingsOpen && (
        <SettingsModal daemon={daemon} live={live} onClose={() => setSettingsOpen(false)}
          onChanged={() => { refresh(); refreshMarket(); }} />
      )}
    </main>
  );
}

function fmtClock(s?: number | null): string {
  if (s == null) return "--:--:--";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(h)}:${p(m)}:${p(sec)}`;
}

// Isolated so its 1Hz tick only re-renders the countdown — not the whole page (kept the
// settings modal / chat / terminal from re-rendering every second, which felt laggy).
function LockCountdown({ remaining }: { remaining?: number | null }) {
  const [s, setS] = useState<number | null>(remaining ?? null);
  useEffect(() => { setS(remaining ?? null); }, [remaining]);
  useEffect(() => {
    const t = setInterval(() => setS((x) => (x == null ? x : Math.max(0, x - 1))), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="blob mt-4 flex flex-col items-center justify-center gap-1.5 px-4 py-5"
      style={{ borderColor: "rgba(255,122,138,0.4)" }}>
      <div className="flex items-center gap-2 text-[var(--rose)]">
        <span className="pulse-dot" style={{ color: "var(--rose)" }} />
        <Lock size={14} />
        <span className="text-[11px] font-semibold uppercase tracking-[0.32em]">Agent Locked · committed run</span>
      </div>
      <div className="mono text-5xl font-bold tabular-nums leading-none" style={{ color: "var(--rose)" }}>{fmtClock(s)}</div>
      <div className="text-mute text-[11px]">trading unattended · chat locked · unlock / kill switch in settings (password required)</div>
    </div>
  );
}

function fmtRemain(s?: number | null): string {
  if (s == null) return "—";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function SettingsModal({ daemon, live, onClose, onChanged }:
  { daemon: DaemonStatus | null; live: boolean; onClose: () => void; onChanged: () => void }) {
  const [hours, setHours] = useState(4);
  const [lockLive, setLockLive] = useState(live);
  const [killPw, setKillPw] = useState("");
  const [stopPw, setStopPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const running = !!daemon?.running;
  const lockedRun = running && !!daemon?.locked;

  async function startCommitted() {
    setBusy(true); setErr(null);
    try {
      await api.daemonStart({
        cadence_seconds: lockLive ? 7200 : 120, live: lockLive,
        cmc_backend: lockLive ? "auto" : "mock", twak_backend: lockLive ? "auto" : "paper",
        run_hours: hours, lock: true, kill_password: killPw || undefined,
      });
      onChanged(); onClose();
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }

  async function unlock() {
    // graceful: halt the loop, sweep orphaned automations, KEEP protective brackets
    setBusy(true); setErr(null);
    try {
      await api.daemonStop(stopPw || undefined);
      onChanged(); onClose();
    } catch (e) { setErr("wrong kill-switch password"); } finally { setBusy(false); }
  }

  async function killFlatten() {
    // emergency: flatten every open position to USDT + cancel ALL automations
    if (typeof window !== "undefined" &&
        !window.confirm("KILL SWITCH: market-sell every open position to USDT and cancel all automations. Continue?")) return;
    setBusy(true); setErr(null);
    try {
      await api.daemonKill(stopPw || undefined);
      onChanged(); onClose();
    } catch (e) { setErr("wrong kill-switch password / kill failed"); } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div className="blob w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5"><Settings size={16} className="text-[var(--aqua)]" /><h2 className="text-base font-semibold">Agent settings</h2></div>
          <button onClick={onClose} className="text-mute"><X size={18} /></button>
        </div>

        {running ? (
          <div className="mt-5 space-y-3">
            <button onClick={onClose} className="text-mute flex items-center gap-1 text-[12px] hover:text-soft">
              <ArrowLeft size={13} /> back to dashboard (keep the run going)
            </button>
            {lockedRun
              ? <div className="text-soft text-sm">Committed run active — <span className="mono">{fmtRemain(daemon?.remaining_seconds)}</span> remaining. The chat is locked.</div>
              : <div className="text-soft text-sm">Autonomous loop running ({daemon?.loops ?? 0} loops).</div>}
            {daemon?.last_error && <div className="text-[var(--warn)] text-xs">⚠ last alert: {daemon.last_error}</div>}
            <div>
              <label className="text-mute block text-[11px] uppercase tracking-wider">{lockedRun ? "kill-switch password" : "password (if locked)"}</label>
              <input type="password" value={stopPw} onChange={(e) => setStopPw(e.target.value)}
                className="mono mt-1 w-full rounded-full bg-black/30 px-4 py-2.5 text-sm text-soft outline-none" placeholder="password" />
            </div>
            <button onClick={unlock} disabled={busy} className="blob blob-pill w-full py-2.5 text-sm font-medium" style={{ color: "var(--aqua)" }}>
              <Lock size={13} className="mr-1.5 inline" /> unlock — stop & keep positions protected
            </button>
            <button onClick={killFlatten} disabled={busy} className="blob blob-pill w-full py-2.5 text-sm font-bold" style={{ color: "var(--rose)" }}>
              <X size={13} className="mr-1.5 inline" /> KILL SWITCH — flatten all to USDT
            </button>
            <p className="text-mute text-[11px]">Unlock halts the loop, sweeps orphaned automations, and KEEPS protective brackets on open positions. The kill switch additionally market-sells every position to USDT and cancels all automations.</p>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            <div>
              <label className="text-mute block text-[11px] uppercase tracking-wider">commit live trading</label>
              <button onClick={() => setLockLive((v) => !v)} className="blob blob-pill mt-1.5 px-4 py-2 text-xs font-medium" style={{ color: lockLive ? "var(--rose)" : "var(--aqua)" }}>
                {lockLive ? "● live (real funds)" : "○ paper"}
              </button>
              {lockLive && daemon && daemon.mainnet_unlocked === false &&
                <p className="text-[var(--warn)] mt-1 text-[11px]">⚠ mainnet gate is CLOSED on the server — live trades won't broadcast until YST_MAINNET is set there.</p>}
            </div>
            <div>
              <label className="text-mute block text-[11px] uppercase tracking-wider"><Timer size={11} className="mr-1 inline" />run for (hours)</label>
              <input type="number" min={0.05} step={0.5} value={hours} onChange={(e) => setHours(parseFloat(e.target.value) || 0)}
                className="mono mt-1.5 w-full rounded-full bg-black/30 px-4 py-2.5 text-sm text-soft outline-none" />
              <p className="text-mute mt-1 text-[11px]">The agent runs unattended for this window; the chat locks until it ends.</p>
            </div>
            <div>
              <label className="text-mute block text-[11px] uppercase tracking-wider">kill-switch password</label>
              <input type="password" value={killPw} onChange={(e) => setKillPw(e.target.value)}
                className="mono mt-1.5 w-full rounded-full bg-black/30 px-4 py-2.5 text-sm text-soft outline-none" placeholder="required to halt early" />
            </div>
            <button onClick={startCommitted} disabled={busy || hours <= 0} className="blob blob-pill w-full py-2.5 text-sm font-medium disabled:opacity-50" style={{ color: "var(--lime)" }}>
              <Power size={13} className="mr-1.5 inline" /> start committed run
            </button>
          </div>
        )}
        {err && <div className="text-[var(--neg)] mt-3 text-xs">{err}</div>}
      </div>
    </div>
  );
}

/* ── primitives ───────────────────────────────────────────────── */

function Toggle({ on, onClick, label, icon, onColor, offColor, title }:
  { on: boolean; onClick: () => void; label: string; icon?: React.ReactNode; onColor: string; offColor: string; title?: string }) {
  return (
    <button onClick={onClick} title={title}
      className="blob blob-pill flex items-center gap-1.5 px-4 py-2 text-xs font-medium"
      style={{ color: on ? onColor : offColor }}>
      {icon} {label}
    </button>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="blob blob-tight px-4 py-3">
      <div className="text-mute text-[10px] uppercase tracking-wider">{label}</div>
      <div className="mono mt-1 truncate text-lg" style={{ color: tone }}>{value}</div>
    </div>
  );
}

function Panel({ icon, title, right, children }:
  { icon: React.ReactNode; title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="blob flex h-[280px] flex-col p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="blob blob-pill grid h-8 w-8 place-items-center">{icon}</div>
          <h3 className="text-[13px] font-medium">{title}</h3>
        </div>
        {right}
      </div>
      <div className="mt-3 flex-1 overflow-y-auto pr-1">{children}</div>
    </div>
  );
}

function AgentWalletBlob({ real, book, live }: { real: WalletT | null; book: WalletT | null; live: boolean }) {
  const w = real;
  const [copied, setCopied] = useState(false);
  async function copy() {
    if (!w?.address) return;
    try { await navigator.clipboard.writeText(w.address); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* */ }
  }
  return (
    <Panel icon={<Wallet size={15} className="text-[var(--lime)]" />} title="Agent Wallet · self-custody"
      right={<span className="mono text-mute text-[10px]">{w?.backend === "cli" || w?.backend === "rest" ? "live" : w?.backend ? "paper" : "—"}</span>}>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="mono text-2xl" style={{ color: "var(--lime)" }}>${(w?.total_value_usd ?? 0).toFixed(2)}</span>
        <button onClick={copy} disabled={!w?.address} className="text-mute mono flex items-center gap-1 text-[10px] hover:text-[var(--aqua)]" title="copy address">
          {w?.address ? `${w.address.slice(0, 8)}…${w.address.slice(-4)}` : "—"}
          {copied ? <Check size={11} className="text-[var(--pos)]" /> : <Copy size={11} />}
        </button>
      </div>
      <div className="space-y-1">
        {(w?.tokens ?? []).map((t) => (
          <div key={t.symbol} className="flex items-center justify-between text-[12.5px]">
            <span className="mono text-soft">{t.symbol}</span>
            <span className="mono text-mute">{(t.balance ?? 0).toFixed(4)} · ${(t.value_usd ?? 0).toFixed(2)}</span>
          </div>
        ))}
        {(!w || w.tokens.length === 0) && <p className="text-mute text-xs">connect a funded wallet (cli backend)</p>}
      </div>
      <div className="text-mute mono mt-3 border-t border-white/5 pt-2 text-[10px]">
        trading book ({live ? "live" : "paper"}): ${(book?.total_value_usd ?? 0).toFixed(2)}
      </div>
    </Panel>
  );
}

function MarketBlob({ market }: { market: Overview | null }) {
  return (
    <Panel icon={<TrendingUp size={15} className="text-[var(--aqua)]" />} title="Market · CMC"
      right={<span className="mono text-[10px]" style={{ color: "var(--aqua)" }}>{market?.structure?.regime_hint ?? "—"}</span>}>
      <div className="space-y-1">
        {(market?.top_movers ?? []).map((m) => (
          <div key={m.symbol} className="flex items-center justify-between text-[12.5px]">
            <span className="mono text-soft">{m.symbol}</span>
            <span className="mono" style={{ color: (m.pct_24h ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
              {(m.pct_24h ?? 0) >= 0 ? "+" : ""}{(m.pct_24h ?? 0).toFixed(1)}%
            </span>
          </div>
        ))}
        {!market && <p className="text-mute text-xs">loading…</p>}
      </div>
    </Panel>
  );
}

function BracketsBlob({ brackets }: { brackets: Brackets | null }) {
  return (
    <Panel icon={<Boxes size={15} className="text-[var(--violet)]" />} title="Native brackets · TWAK"
      right={<span className="mono text-mute text-[10px]">{brackets?.count ?? 0}</span>}>
      <div className="space-y-2">
        {(brackets?.automations ?? []).map((a) => (
          <div key={a.id} className="flex items-center justify-between text-[12px]">
            <span className="mono text-soft">{a.symbol} · {a.purpose}</span>
            <span className="mono text-mute">{a.condition} ${(a.price_usd ?? 0).toFixed(4)}</span>
          </div>
        ))}
        {(!brackets || brackets.count === 0) && <p className="text-mute text-xs">no active exit orders</p>}
      </div>
    </Panel>
  );
}

function ProofBlob({ proof }: { proof: ProofChain | null }) {
  return (
    <Panel icon={<ShieldCheck size={15} className="text-[var(--magenta)]" />} title="Proof chain"
      right={proof && <span className="mono text-[10px]" style={{ color: proof.verified ? "var(--pos)" : "var(--neg)" }}>{proof.verified ? "✓ verified" : "✗"}</span>}>
      <div className="space-y-1.5">
        {(proof?.blocks ?? []).map((b) => (
          <div key={b.block_hash} className="flex items-center justify-between text-[12px]">
            <span className="mono text-soft">#{b.block_index} {b.final_decision}</span>
            <span className="mono text-mute">{b.pick ?? "—"}</span>
          </div>
        ))}
        {(!proof || proof.count === 0) && <p className="text-mute text-xs">no blocks yet</p>}
      </div>
    </Panel>
  );
}
