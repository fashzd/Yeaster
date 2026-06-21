"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, Brain, ShieldCheck, Target, Lock, Coins, FileCheck2, Search,
  Gauge, Crosshair, Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import YeasterLogo from "@/components/YeasterLogo";

export default function Learn() {
  const [teaser, setTeaser] = useState<any>(null);
  useEffect(() => { api.x402Teaser().then(setTeaser).catch(() => {}); }, []);

  return (
    <main className="mx-auto min-h-screen w-full max-w-[1100px] px-5 py-6 md:px-8">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="blob blob-pill grid h-9 w-9 place-items-center text-soft" title="Back"><ArrowLeft size={16} /></Link>
          <div className="flex items-center gap-2.5">
            <div className="blob blob-pill grid h-10 w-10 place-items-center"><YeasterLogo size={24} /></div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">How Yeaster works</h1>
              <p className="text-mute text-[11px]">a self-custodial momentum agent on BNB Smart Chain</p>
            </div>
          </div>
        </div>
        <Link href="/" className="blob blob-pill px-4 py-2 text-xs font-medium text-[var(--aqua)]">open the control room →</Link>
      </header>

      {/* hero */}
      <section className="blob mt-6 p-6">
        <p className="text-soft text-[15px] leading-relaxed">
          Yeaster hunts crypto momentum on the BNB chain, fully autonomously. One mind reasons in four passes,
          decides with a god-tier-trader LLM, and executes self-custodially through Trust Wallet — every trade
          wrapped in a <span className="text-[var(--lime)]">non-bypassable firewall</span> and sealed into a
          tamper-evident <span className="text-[var(--magenta)]">proof chain</span>. It buys, brackets, and exits
          on real funds; humans can lock it into a timed run and stop it only with a password.
        </p>
      </section>

      {/* the brain */}
      <H icon={<Brain size={15} />} title="The brain — one mind, four passes" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <Step icon={<Search size={14} />} n="SCREEN" t="Scout the 135-coin momentum universe with deterministic detectors (relative strength, breakouts, accumulation, volume surges, trending runners). Only tokens it can actually buy, bracket and sell are surfaced." />
        <Step icon={<Gauge size={14} />} n="GRADE" t="Score each candidate across 8 dimensions — technicals, perps, whale flow, sector rotation, unlocks, social — weighted by how much real data backs them, plus a zero-weight scam/honeypot safety axis." />
        <Step icon={<ShieldCheck size={14} />} n="VET" t="An adversarial critic + hard safety blocks. A flagged honeypot/rug is vetoed; an unverifiable token is downgraded, never silently scored 'bad'." />
        <Step icon={<Crosshair size={14} />} n="COMMIT" t="A bold lead LLM picks ONE name (or stands down). The LLM is the decisive factor — if it's unavailable the agent stands down, never silently substituting a worse rule." />
      </div>

      {/* guardrails */}
      <H icon={<ShieldCheck size={15} />} title="Guardrails — and why they're built this way" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Rail t="Non-bypassable firewall" w="Every trade is checked for allowlist, single-trade & position caps, slippage, drawdown and Safe-Mode — by code the decision layer cannot skip. An AI should never be trusted to police its own risk." />
        <Rail t="De-risk is always allowed" w="Selling back to a stable is never blocked, even in Safe Mode. You must always be able to reduce risk." />
        <Rail t="Approve-at-entry, so exits can't fail" w="The moment a token is bought it's approved for selling. Without it the FIRST stop/TP/trail would revert — protection that only looks real is worse than none." />
        <Rail t="Only exitable tokens" w="A token is tradeable only if its on-chain contract resolves. The agent can never enter something it couldn't later sell." />
        <Rail t="R-sizing + drawdown brake" w="Bets are sized in units of risk and shrink as drawdown grows; a losing streak shrinks them further. Lose, and Yeaster gets smaller." />
        <Rail t="Volatility-scaled exits" w="An ATR-3x trailing stop + wide take-profit. A flat % trail clipped winners on daily-bar noise; ATR gives each coin room proportional to its own volatility." />
        <Rail t="≥1 trade/day, safely" w="If nothing trades by day's end, one minimal safest trade fires — so the contest's trade-frequency gate is never missed." />
        <Rail t="Mainnet double-gate + operator password" w="No real funds move until two env gates are set; the kill switch and unlock always require an operator password. Irreversible power needs deliberate, authenticated intent." />
      </div>

      {/* exits + controls */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <H icon={<Target size={15} />} title="The exit engine" />
          <div className="blob p-5 text-[13px] text-soft leading-relaxed">
            Every fill arms native on-chain brackets — <b>8% stop · 40% take-profit · ATR-3× trailing</b> — that
            fire via Trust Wallet's watcher even if the agent is offline. As price climbs, the trailing stop
            ratchets up behind it; the bracket set was re-tuned on a 135-token real-OHLC backtest.
          </div>
        </div>
        <div>
          <H icon={<Lock size={15} />} title="Operator controls" />
          <div className="blob p-5 text-[13px] text-soft leading-relaxed">
            Launch a <b>committed timed run</b> — the chat locks, a live countdown ticks down, and the agent trades
            unattended. <b>Unlock</b> (password) stops it gracefully and sweeps orphan orders but keeps protective
            brackets; the <b>kill switch</b> (password) flattens everything to USDT. Manual swaps always show a
            trade intent you must approve.
          </div>
        </div>
      </div>

      {/* sponsors + x402 */}
      <H icon={<Coins size={15} />} title="The three sponsors — fused into one agent" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Spon t="CoinMarketCap" c="var(--aqua)" w="Market regime, technicals, derivatives, whale flow, sector rotation, unlocks, social + scam-safety — fused into the grade, and historical OHLCV for the backtester." />
        <Spon t="Trust Wallet (TWAK)" c="var(--violet)" w="Self-custodial on-chain swaps + native stop/TP/ATR-trailing automations, token-risk reads, and x402 micropayments." />
        <Spon t="BNB Smart Chain" c="var(--amber)" w="The on-chain venue — chain 56. The 148-token whitelist is the hard universe; BNB is gas (and manual-only), never an autonomous trade." />
      </div>

      <div className="blob mt-3 flex flex-col items-start gap-2 p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[var(--magenta)]"><Zap size={14} /><span className="text-[11px] font-semibold uppercase tracking-[0.28em]">x402 · sell the daily alpha</span></div>
          <p className="text-soft mt-1.5 text-[13px] leading-relaxed">
            The agent monetizes its edge: anyone can buy today's top pick with a real on-chain USDT micropayment.
            Pay → the server verifies the transfer on BSC → the alpha unlocks. Every sale is logged as revenue.
          </p>
        </div>
        <div className="blob blob-tight min-w-[180px] p-3 text-[12px]">
          <div className="text-mute text-[10px] uppercase tracking-wider">today's alpha · locked</div>
          {teaser?.teaser?.available ? (
            <>
              <div className="mono mt-1 text-soft">conviction {teaser.teaser.conviction} · {teaser.teaser.posture}</div>
              <div className="mono text-[var(--lime)] mt-1">{teaser.price_usd} USDT to unlock</div>
            </>
          ) : (
            <div className="text-mute mt-1">{teaser ? "run a cycle to mint today's alpha" : "—"}</div>
          )}
        </div>
      </div>

      {/* proof */}
      <H icon={<FileCheck2 size={15} />} title="Proof — every decision is verifiable" />
      <div className="blob mb-8 p-5 text-[13px] text-soft leading-relaxed">
        Each tick — the market snapshot, the full reasoning trace, the firewall verdict, and the outcome — is
        sealed into an append-only, SHA-256-linked chain. Any later edit breaks every downstream hash, so the
        agent's track record can be independently verified, not just claimed.
      </div>

      <footer className="text-mute pb-8 text-center text-[11px]">Yeaster · self-custody · proof-secured · BNB × CMC × TWT</footer>
    </main>
  );
}

function H({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="mb-3 mt-7 flex items-center gap-2">
      <span className="blob blob-pill grid h-7 w-7 place-items-center text-[var(--aqua)]">{icon}</span>
      <h2 className="text-sm font-semibold tracking-wide">{title}</h2>
    </div>
  );
}

function Step({ icon, n, t }: { icon: React.ReactNode; n: string; t: string }) {
  return (
    <div className="blob blob-tight p-4">
      <div className="flex items-center gap-1.5 text-[var(--aqua)]">{icon}<span className="mono text-[11px] font-semibold tracking-wider">{n}</span></div>
      <p className="text-mute mt-2 text-[12px] leading-relaxed">{t}</p>
    </div>
  );
}

function Rail({ t, w }: { t: string; w: string }) {
  return (
    <div className="blob blob-tight p-4">
      <div className="flex items-center gap-1.5"><span className="pulse-dot" style={{ color: "var(--lime)" }} /><span className="text-soft text-[13px] font-medium">{t}</span></div>
      <p className="text-mute mt-1.5 text-[12px] leading-relaxed">{w}</p>
    </div>
  );
}

function Spon({ t, c, w }: { t: string; c: string; w: string }) {
  return (
    <div className="blob blob-tight p-4">
      <div className="text-[13px] font-semibold" style={{ color: c }}>{t}</div>
      <p className="text-mute mt-1.5 text-[12px] leading-relaxed">{w}</p>
    </div>
  );
}
