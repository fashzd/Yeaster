"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

export default function TokenChart({ symbol, height = 160 }: { symbol: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let chart: any;

    (async () => {
      const el = ref.current;
      if (!el) return;
      const lw = await import("lightweight-charts");
      const data = await api.series(symbol).catch(() => null);
      if (disposed || !el || !data) return;
      el.innerHTML = "";

      chart = lw.createChart(el, {
        width: el.clientWidth,
        height,
        layout: { background: { color: "transparent" }, textColor: "#aeb9d6", attributionLogo: false },
        grid: { vertLines: { visible: false }, horzLines: { color: "rgba(150,180,255,0.06)" } },
        rightPriceScale: { borderVisible: false },
        timeScale: { visible: false, borderVisible: false },
        crosshair: { mode: 0 },
        handleScroll: false,
        handleScale: false,
      });

      const series = chart.addSeries(lw.AreaSeries, {
        lineColor: "#34e7e4",
        topColor: "rgba(52,231,228,0.28)",
        bottomColor: "rgba(52,231,228,0.02)",
        lineWidth: 2,
        priceLineVisible: false,
      });
      const now = Math.floor(Date.now() / 1000);
      series.setData(
        data.points.map((p, i) => ({
          time: (now - (data.points.length - i) * 3600) as any,
          value: p.price,
        })),
      );

      for (const m of data.markers) {
        const color = m.side === "stop" ? "#ff6f7d" : m.side === "tp" ? "#57e7a6" : "#8b7bff";
        series.createPriceLine({
          price: m.price,
          color,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: m.label,
        });
      }
      chart.timeScale().fitContent();
    })();

    return () => {
      disposed = true;
      if (chart) chart.remove();
    };
  }, [symbol, height]);

  return <div ref={ref} style={{ width: "100%", height }} />;
}
