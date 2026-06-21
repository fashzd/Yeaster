"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Coins, Lock, Unlock, Loader2, Copy, Check, Zap } from "lucide-react";
import { api } from "@/lib/api";

export default function BuyAlpha() {
  const [info, setInfo] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [tx, setTx] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => {
    api.x402Teaser().then(setInfo).catch(() => {});
    api.x402().then(setStatus).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  async function unlock() {
    if (!tx.trim()) return;
    setBusy(true); setErr(null); setResult(null);
    try {
      const { status: code, body } = await api.x402Buy(tx.trim());
      if (code === 200 && body.paid) { setResult(body); load(); }
      else setErr(body.error || `HTTP ${code}`);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }

  const payTo = info?.pay_to ?? "—";
  const price = info?.price_usd ?? "—";
  const enabled = info?.enabled;
  const t = info?.teaser;

  return (
    <main className="mx-auto min-h-screen w-full max-w-[820px] px-5 py-6 md:px-8">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="blob blob-pill grid h-9 w-9 place-items-center text-soft" title="Back"><ArrowLeft size={16} /></Link>
          <div className="flex items-center gap-2.5">
            <div className="blob blob-pill grid h-10 w-10 place-items-center"><Coins size={17} className="text-[var(--magenta)]" /></div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Buy the daily alpha</h1>
              <p className="text-mute text-[11px]">x402 · pay on-chain, unlock the agent's top pick</p>
            </div>
          </div>
        </div>
        <Link href="/learn" className="blob blob-pill px-4 py-2 text-xs font-medium text-[var(--lime)]">how it works →</Link>
      </header>

      {!enabled && (
        <div className="blob mt-6 p-5 text-[13px]" style={{ color: "var(--warn)" }}>
          x402 alpha sales are currently <b>disabled</b>. Start the API with <span className="mono">YST_X402=1</span> to enable.
        </div>
      )}

      {/* the offer */}
      <section className="blob mt-6 p-6">
        <div className="flex items-center gap-2 text-[var(--magenta)]"><Zap size={14} /><span className="text-[11px] font-semibold uppercase tracking-[0.28em]">today's signal · paywalled</span></div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="blob blob-tight p-4">
            <div className="text-mute text-[10px] uppercase tracking-wider">locked preview</div>
            {t?.available ? (
              <div className="mt-2 space-y-1 text-[13px]">
                <Row k="posture" v={t.posture} />
                <Row k="conviction" v={t.conviction} />
                <Row k="minted" v={(t.generated_at || "").slice(0, 10)} />
                <Row k="proof" v={(t.proof_block_hash || "").slice(0, 14) + "…"} />
                <div className="mt-2 flex items-center gap-1.5 text-[var(--rose)]"><Lock size={12} /> <span className="text-[12px]">symbol + thesis hidden until paid</span></div>
              </div>
            ) : (
              <div className="text-mute mt-2 text-[12px]">{info ? "no alpha yet — run a cycle to mint today's pick" : "loading…"}</div>
            )}
          </div>

          <div className="blob blob-tight p-4">
            <div className="text-mute text-[10px] uppercase tracking-wider">how to pay</div>
            <div className="mt-2 text-[13px] text-soft leading-relaxed">
              Send <b className="text-[var(--lime)]">{price} USDT</b> on BSC to:
            </div>
            <button
              onClick={() => { navigator.clipboard?.writeText(payTo); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
              className="blob blob-pill mono mt-2 flex w-full items-center justify-between gap-2 px-3 py-2 text-[11px] text-soft">
              <span className="truncate">{payTo}</span>
              {copied ? <Check size={12} className="text-[var(--lime)]" /> : <Copy size={12} className="text-mute" />}
            </button>
            <div className="text-mute mt-2 text-[11px]">…then paste your payment tx hash below to unlock. Verified on-chain; each tx redeems once.</div>
          </div>
        </div>

        {/* redeem */}
        <div className="mt-4 flex items-center gap-2">
          <input value={tx} onChange={(e) => setTx(e.target.value)} placeholder="0x… payment tx hash"
            disabled={!enabled || busy}
            className="mono flex-1 rounded-full bg-black/25 px-4 py-2.5 text-[12px] text-soft outline-none placeholder:text-[var(--ink-mute)] disabled:opacity-50" />
          <button onClick={unlock} disabled={!enabled || busy || !tx.trim()}
            className="blob blob-pill flex items-center gap-1.5 px-5 py-2.5 text-sm font-medium disabled:opacity-40" style={{ color: "var(--magenta)" }}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Unlock size={14} />} unlock
          </button>
        </div>
        {err && <div className="text-[var(--neg)] mt-2 text-[12px]">{err}</div>}

        {result?.alpha && (
          <div className="blob mt-4 p-4" style={{ borderColor: "rgba(124,245,168,0.4)" }}>
            <div className="flex items-center gap-2 text-[var(--lime)]"><Unlock size={14} /><span className="text-[11px] font-semibold uppercase tracking-[0.24em]">unlocked · paid {result.amount_usd} USDT</span></div>
            <div className="mono mt-2 text-2xl font-bold text-soft">{result.alpha.symbol}</div>
            <div className="text-mute text-[12px]">conviction {result.alpha.conviction} · {result.alpha.posture}</div>
            <div className="text-soft mt-2 text-[13px] leading-relaxed">{result.alpha.thesis}</div>
            <div className="text-mute mono mt-2 text-[10px]">proof {result.alpha.proof_block_hash?.slice(0, 24)}…</div>
          </div>
        )}
      </section>

      {/* revenue */}
      <section className="blob mt-4 p-5">
        <div className="flex items-center justify-between">
          <span className="text-soft text-sm font-medium">Revenue trail</span>
          <span className="mono text-[var(--lime)] text-sm">${status?.total_settled_usd ?? 0} settled</span>
        </div>
        <div className="mt-3 space-y-1.5">
          {(status?.settlements ?? []).slice().reverse().slice(0, 8).map((s: any, i: number) => (
            <div key={i} className="flex items-center justify-between text-[12px]">
              <span className="mono text-mute">{(s.tx_hash || s.request_id || "—").slice(0, 18)}…</span>
              <span className="mono text-soft">{s.amount_usd} {s.asset || "USDT"}</span>
            </div>
          ))}
          {(!status?.settlements || status.settlements.length === 0) && <div className="text-mute text-[12px]">no sales yet</div>}
        </div>
      </section>

      <footer className="text-mute mt-7 pb-8 text-center text-[11px]">x402 micropayments · real on-chain settlement · BNB Smart Chain</footer>
    </main>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-mute">{k}</span>
      <span className="mono text-soft">{v ?? "—"}</span>
    </div>
  );
}
