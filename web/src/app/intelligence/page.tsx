"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Activity, Flame, Radar, Gauge } from "lucide-react";
import TradingViewChart from "@/components/TradingViewChart";
import { api, type Intelligence, type Trending } from "@/lib/api";

export default function IntelligencePage() {
  const [intel, setIntel] = useState<Intelligence | null>(null);
  const [trend, setTrend] = useState<Trending | null>(null);
  const [symbol, setSymbol] = useState("BNB");

  useEffect(() => {
    const load = async () => {
      const [i, t] = await Promise.allSettled([api.intelligence(), api.trending()]);
      if (i.status === "fulfilled") {
        setIntel(i.value);
        if (i.value.readiness?.[0]) setSymbol((s) => (s === "BNB" ? i.value.readiness[0].symbol : s));
      }
      if (t.status === "fulfilled") setTrend(t.value);
    };
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  const s = intel?.structure;
  const fg = s?.fear_greed ?? null;
  const fgColor = fg == null ? "var(--ink-mute)" : fg < 45 ? "var(--neg)" : fg > 55 ? "var(--pos)" : "var(--warn)";

  return (
    <main className="mx-auto min-h-screen w-full max-w-[1500px] px-5 py-6 md:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="blob blob-pill grid h-10 w-10 place-items-center text-soft"><ArrowLeft size={17} /></Link>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Market Intelligence</h1>
            <p className="text-mute text-[11px]">CMC Agent Hub · Trust Wallet trending · TradingView</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Pill label="regime" value={s?.regime_hint ?? "—"} />
          <Pill label="posture" value={intel?.posture?.posture ?? "—"} />
          <Pill label="breadth" value={s?.breadth != null ? `${(s.breadth * 100).toFixed(0)}%` : "—"} />
          <Pill label="BTC dom" value={s?.btc_dominance != null ? `${s.btc_dominance.toFixed(1)}%` : "—"} />
        </div>
      </header>

      {/* Fear&Greed + chart */}
      <section className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="blob p-6">
          <div className="flex items-center gap-2.5">
            <div className="blob blob-pill grid h-8 w-8 place-items-center"><Gauge size={15} className="text-[var(--amber)]" /></div>
            <h3 className="text-[13px] font-medium">Fear & Greed</h3>
          </div>
          <div className="mt-5 flex items-end gap-3">
            <div className="mono text-5xl" style={{ color: fgColor }}>{fg ?? "—"}</div>
            <div className="text-soft pb-1.5 text-sm">{s?.fear_greed_label ?? ""}</div>
          </div>
          <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-black/30">
            <div className="h-full rounded-full" style={{ width: `${fg ?? 0}%`, background: fgColor }} />
          </div>
          <div className="text-mute mono mt-4 space-y-1 text-[11px]">
            <div>BTC direction · <span className="text-soft">{s?.btc_direction ?? "—"}</span></div>
            <div>total mcap · <span className="text-soft">{s?.total_mcap ? `$${(s.total_mcap / 1e12).toFixed(2)}T` : "—"}</span></div>
            <div>skills · <span className="text-soft">{intel?.skills_enabled ? "on" : "off"}</span></div>
          </div>
        </div>

        <div className="blob p-5 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="blob blob-pill grid h-8 w-8 place-items-center"><Activity size={15} className="text-[var(--aqua)]" /></div>
              <h3 className="text-[13px] font-medium">{symbol} · TradingView</h3>
            </div>
            <span className="text-mute mono text-[10px]">BINANCE:{symbol}USDT</span>
          </div>
          <TradingViewChart symbol={symbol} height={420} />
        </div>
      </section>

      {/* Readiness screener + scanner + trending */}
      <section className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="blob p-5 lg:col-span-2">
          <div className="flex items-center gap-2.5">
            <div className="blob blob-pill grid h-8 w-8 place-items-center"><Radar size={15} className="text-[var(--violet)]" /></div>
            <h3 className="text-[13px] font-medium">Readiness screener · CMC</h3>
            <span className="text-mute mono text-[10px]">click a row to chart it</span>
          </div>
          <div className="mt-3 max-h-[360px] overflow-y-auto">
            <table className="w-full text-[12.5px]">
              <thead className="text-mute text-[10px] uppercase tracking-wider">
                <tr className="text-left"><th className="pb-2">token</th><th>24h</th><th>7d</th><th>RSI</th><th>trend</th><th>scan</th><th>verdict</th></tr>
              </thead>
              <tbody className="mono">
                {(intel?.readiness ?? []).map((r) => (
                  <tr key={r.symbol} onClick={() => setSymbol(r.symbol)}
                    className="cursor-pointer border-t border-white/5 hover:bg-white/5">
                    <td className="py-1.5 text-soft">{r.symbol}</td>
                    <td style={{ color: (r.pct_24h ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>{(r.pct_24h ?? 0).toFixed(1)}%</td>
                    <td className="text-mute">{r.pct_7d != null ? `${r.pct_7d.toFixed(1)}%` : "—"}</td>
                    <td className="text-mute">{r.rsi_14 != null ? r.rsi_14.toFixed(0) : "—"}</td>
                    <td style={{ color: r.ema_trend === "bullish" ? "var(--pos)" : r.ema_trend === "bearish" ? "var(--neg)" : "var(--ink-mute)" }}>{r.ema_trend}</td>
                    <td>{r.on_scanner ? "●" : "·"}</td>
                    <td style={{ color: r.verdict === "WATCH" ? "var(--aqua)" : "var(--ink-mute)" }}>{r.verdict}</td>
                  </tr>
                ))}
                {!intel && <tr><td className="text-mute py-3" colSpan={7}>loading…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="blob p-5">
          <div className="flex items-center gap-2.5">
            <div className="blob blob-pill grid h-8 w-8 place-items-center"><Flame size={15} className="text-[var(--rose)]" /></div>
            <h3 className="text-[13px] font-medium">Trending · Trust Wallet</h3>
          </div>
          <div className="mt-3 max-h-[360px] space-y-1.5 overflow-y-auto">
            {(trend?.trending ?? []).map((t) => (
              <button key={t.symbol} onClick={() => setSymbol(t.symbol)}
                className="flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-left text-[12.5px] hover:bg-white/5">
                <span className="mono text-soft">{t.symbol} {t.tradeable && <span className="text-[var(--lime)]">✓</span>}</span>
                <span className="mono" style={{ color: (t.change_24h ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
                  {t.change_24h != null ? `${(t.change_24h ?? 0) >= 0 ? "+" : ""}${t.change_24h}%` : t.category ?? ""}
                </span>
              </button>
            ))}
            {(!trend || trend.count === 0) && <p className="text-mute text-xs">no trending feed (twak trending unavailable)</p>}
          </div>
          {intel?.scanner && intel.scanner.length > 0 && (
            <div className="mt-3 border-t border-white/5 pt-3">
              <div className="text-mute mb-1.5 text-[10px] uppercase tracking-wider">breakout scanner</div>
              <div className="flex flex-wrap gap-1.5">
                {intel.scanner.map((c) => (
                  <button key={c.symbol} onClick={() => setSymbol(c.symbol)} className="blob blob-pill px-2.5 py-1 text-[11px] text-[var(--aqua)]">{c.symbol}</button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <div className="blob blob-pill px-3.5 py-2">
      <span className="text-mute text-[10px] uppercase tracking-wider">{label} </span>
      <span className="mono text-xs text-soft">{value}</span>
    </div>
  );
}
