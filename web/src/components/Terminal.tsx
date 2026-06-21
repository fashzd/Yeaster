"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Loader2, Radio, Lock } from "lucide-react";
import { streamTick, type Thought, type ThoughtStage } from "@/lib/api";

function fmtClock(s?: number | null): string {
  if (s == null) return "--:--:--";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(h)}:${p(m)}:${p(sec)}`;
}

const STAGE_COLOR: Record<string, string> = {
  regime: "var(--aqua)",
  screen: "var(--aqua)",
  grade: "var(--violet)",
  vet: "var(--amber)",
  commit: "var(--lime)",
  guard: "var(--violet)",
  execute: "var(--lime)",
  exit: "var(--rose)",
  trail: "var(--aqua)",
  proof: "var(--magenta)",
  result: "var(--lime)",
  error: "var(--neg)",
};

type Line = { stage: ThoughtStage; text: string; tone?: string };

export default function Terminal({
  live, guardEnabled, runSignal, onResult, onBusy, locked = false, remaining, loops = 0,
}: {
  live: boolean;
  guardEnabled: boolean;
  runSignal?: number;
  onResult?: (r: any) => void;
  onBusy?: (b: boolean) => void;
  locked?: boolean;            // autonomous loop running — manual ticks disabled
  remaining?: number | null;   // committed-run seconds left (for the countdown)
  loops?: number;
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [running, setRunning] = useState(false);
  const [count, setCount] = useState<number | null>(remaining ?? null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [lines]);

  useEffect(() => { onBusy?.(running); }, [running, onBusy]);
  useEffect(() => { setCount(remaining ?? null); }, [remaining]);
  useEffect(() => {
    if (!locked) return;
    const t = setInterval(() => setCount((x) => (x == null ? x : Math.max(0, x - 1))), 1000);
    return () => clearInterval(t);
  }, [locked]);

  // allow the chat ("run a cycle") to trigger a tick
  useEffect(() => {
    if (runSignal) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runSignal]);

  async function run() {
    if (running || locked) return;   // no manual ticks while the autonomous loop owns the agent
    setRunning(true);
    setLines([]);
    const body = live
      ? { cmc_backend: "auto", twak_backend: "auto", guard_enabled: guardEnabled }
      : { cmc_backend: "mock", twak_backend: "paper", arm: "det_safety", guard_enabled: guardEnabled };
    try {
      await streamTick(body, (t: Thought) => {
        if (t.stage === "result") {
          onResult?.(t.payload);
          return;
        }
        setLines((prev) => [
          ...prev,
          { stage: t.stage, text: t.payload?.text ?? JSON.stringify(t.payload), tone: t.payload?.tone },
        ]);
      });
    } catch (e) {
      setLines((prev) => [...prev, { stage: "error", text: String(e) }]);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="blob flex h-full flex-col p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Radio size={16} className="text-[var(--aqua)]" />
          <h2 className="text-sm font-medium tracking-wide">Agent Terminal</h2>
          <span className="text-mute mono text-[10px]">screen · grade · vet · commit</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-mute mono text-[10px]">{live ? "live data" : "paper · fast"}</span>
          <button
            onClick={run}
            disabled={running || locked}
            className="blob blob-pill flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium disabled:opacity-50"
            style={{ color: locked ? "var(--rose)" : "var(--lime)" }}
          >
            {locked ? <Lock size={13} /> : running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {locked ? "locked" : running ? "thinking…" : "run tick"}
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="mono mt-4 flex-1 space-y-2 overflow-y-auto rounded-3xl bg-black/20 p-4 text-[12.5px] leading-relaxed"
        style={{ minHeight: 320 }}
      >
        {locked && (
          <div className="mb-2 flex items-center justify-between rounded-2xl px-3 py-1.5"
            style={{ background: "rgba(255,122,138,0.08)" }}>
            <span className="flex items-center gap-1.5 text-[11px] text-[var(--rose)]">
              <Lock size={12} /> autonomous mode · manual run disabled
            </span>
            <span className="mono text-[11px] text-[var(--rose)]">{count != null ? fmtClock(count) : `${loops} cycles`}</span>
          </div>
        )}
        {lines.length === 0 && !running && (
          <p className="text-mute">
            {locked
              ? "The autonomous loop is running server-side. The reasoning log appears here when you run a manual tick (disabled while locked)."
              : <>The agent is idle. Press <span className="text-soft">run tick</span> to watch it reason through a full screen → grade → vet → commit cycle and seal a proof block.</>}
          </p>
        )}
        {lines.map((l, i) => (
          <div key={i} className="flex gap-2.5">
            <span
              className="shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider"
              style={{ color: STAGE_COLOR[l.stage] ?? "var(--ink-soft)", background: "rgba(255,255,255,0.05)" }}
            >
              {l.stage}
            </span>
            <span className={l.tone === "bad" ? "text-[var(--neg)]" : "text-soft"}>{l.text}</span>
          </div>
        ))}
        {running && (
          <div className="text-mute flex items-center gap-2 pt-1">
            <Loader2 size={12} className="animate-spin" /> reasoning…
          </div>
        )}
      </div>
    </div>
  );
}
