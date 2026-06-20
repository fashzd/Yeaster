"use client";

import { useEffect, useRef } from "react";

declare global {
  interface Window { TradingView?: any }
}

let scriptPromise: Promise<void> | null = null;
function loadTV(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.TradingView) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = "https://s3.tradingview.com/tv.js";
      s.async = true;
      s.onload = () => resolve();
      document.head.appendChild(s);
    });
  }
  return scriptPromise;
}

export default function TradingViewChart({ symbol, height = 420 }: { symbol: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = `tv_${symbol.replace(/[^A-Za-z0-9]/g, "")}`;

  useEffect(() => {
    let cancelled = false;
    loadTV().then(() => {
      if (cancelled || !ref.current || !window.TradingView) return;
      ref.current.innerHTML = "";
      // Trust Wallet / BNB ecosystem tokens trade on Binance; default the exchange to BINANCE.
      const tvSymbol = symbol.includes(":") ? symbol : `BINANCE:${symbol.toUpperCase()}USDT`;
      // eslint-disable-next-line new-cap
      new window.TradingView.widget({
        symbol: tvSymbol,
        container_id: id,
        autosize: true,
        interval: "60",
        timezone: "Etc/UTC",
        theme: "dark",
        style: "1",
        locale: "en",
        hide_side_toolbar: true,
        allow_symbol_change: true,
        backgroundColor: "rgba(7,11,26,0.0)",
        gridColor: "rgba(150,180,255,0.06)",
      });
    });
    return () => { cancelled = true; };
  }, [symbol, id]);

  return <div id={id} ref={ref} style={{ height, width: "100%" }} />;
}
