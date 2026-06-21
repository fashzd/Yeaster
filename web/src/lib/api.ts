// Yeaster API client — typed fetchers + the live reasoning stream.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export type Health = { status: string; version: string };
export type Readiness = {
  live_count: number;
  layer_count: number;
  layers: Record<string, { live: boolean; detail: string }>;
};
export type Wallet = {
  backend: string;
  address: string;
  total_value_usd: number | null;
  positions_pct: Record<string, number>;
  tokens: { symbol: string; balance: number; value_usd: number | null }[];
};
export type Overview = {
  backend: string;
  structure: {
    regime_hint: string;
    breadth: number | null;
    fear_greed_index: number | null;
    btc_direction: string;
    btc_dominance_pct: number | null;
  };
  posture: { posture: string; regime: string | null };
  scanner: { symbol: string; source: string }[];
  skills_enabled: boolean;
  top_movers: {
    symbol: string;
    price_usd: number;
    pct_24h: number | null;
    pct_7d: number | null;
    rsi_14: number | null;
    ema_trend: string;
  }[];
};
export type AgentStatus = {
  commit_arm: string;
  commit_style: string;
  mainnet_unlocked: boolean;
  peak_equity_usd: number | null;
  safe_mode_latched: boolean;
  trades_today: number;
  open_positions: number;
  realized_pnl_usd?: number;
  wins?: number;
  losses?: number;
  win_rate?: number | null;
  recent_exits?: { symbol: string; pnl_usd: number; reason: string }[];
  last_tick_at: string | null;
};
export type Brackets = {
  count: number;
  automations: {
    id: string;
    symbol: string | null;
    purpose: string | null;
    price_usd: number | null;
    condition: string | null;
    status: string;
  }[];
};
export type ProofChain = {
  count: number;
  verified: boolean;
  blocks: {
    block_index: number;
    block_hash: string;
    final_decision: string;
    posture: string | null;
    pick: string | null;
    rationale: string | null;
  }[];
};
export type DaemonStatus = {
  enabled: boolean;
  running: boolean;
  locked: boolean;
  live: boolean;
  cadence_seconds: number;
  loops: number;
  run_until: string | null;
  remaining_seconds?: number | null;
  last_loop_at: string | null;
  last_error: string | null;
  mainnet_unlocked?: boolean;
  orphans_cleaned?: number | string;
  flatten_result?: { flattened?: { symbol: string; sold: boolean }[]; automations_cancelled?: number };
};
export type Trending = {
  count: number;
  trending: { symbol: string; name?: string; change_24h?: number; category?: string; whitelisted: boolean; tradeable: boolean }[];
};
export type Intelligence = {
  backend: string;
  posture: { posture: string; regime: string | null };
  structure: {
    regime_hint: string; breadth: number | null; fear_greed: number | null; fear_greed_label: string | null;
    btc_direction: string; btc_dominance: number | null; total_mcap: number | null;
  };
  scanner: { symbol: string; source: string }[];
  readiness: { symbol: string; pct_24h: number | null; pct_7d: number | null; ema_trend: string; rsi_14: number | null; on_scanner: boolean; verdict: string }[];
  skills_enabled: boolean;
};

export type ChatReply = {
  reply: string;
  action?: { type: string; [k: string]: any };
  pack?: { kind: string; [k: string]: any };
};
export type Series = {
  symbol: string;
  current_price: number;
  points: { t: number; price: number }[];
  markers: { side: string; price: number; label: string }[];
};

export const api = {
  health: () => getJSON<Health>("/api/health"),
  chat: (messages: { role: string; text: string }[], context?: object) =>
    postJSON<ChatReply>("/api/chat", { messages, context }),
  manual: (body: object) => postJSON<any>("/api/agent/manual", body),
  tick: (body: object) => postJSON<any>("/api/agent/tick", body),
  series: (symbol: string, mode = "paper") => getJSON<Series>(`/api/market/series?symbol=${symbol}&mode=${mode}`),
  token: (symbol: string) => getJSON<ChatReply>(`/api/market/token/${symbol}`),
  readiness: () => getJSON<Readiness>("/api/readiness"),
  // mode-scoped so paper and live books never mix (with the gate open, "auto"
  // resolves to live everywhere, so we always pass an explicit backend/mode).
  wallet: (backend = "paper") => getJSON<Wallet>(`/api/wallet?backend=${backend}`),
  walletReal: () => getJSON<Wallet>("/api/wallet?backend=cli"),
  overview: () => getJSON<Overview>("/api/market/overview"),
  agent: (mode = "paper") => getJSON<AgentStatus>(`/api/agent?mode=${mode}`),
  activity: (mode = "paper") => getJSON<{ activity: any[] }>(`/api/agent/activity?mode=${mode}`),
  brackets: (backend = "paper") => getJSON<Brackets>(`/api/wallet/brackets?backend=${backend}`),
  proof: () => getJSON<ProofChain>("/api/proof?limit=12"),
  daemon: () => getJSON<DaemonStatus>("/api/daemon/status"),
  daemonStart: (body: object) => postJSON<DaemonStatus>("/api/daemon/start", body),
  daemonStop: (password?: string) => postJSON<DaemonStatus>("/api/daemon/stop", { password }),
  daemonKill: (password?: string) => postJSON<DaemonStatus>("/api/daemon/kill", { password }),
  trending: () => getJSON<Trending>("/api/market/trending"),
  intelligence: () => getJSON<Intelligence>("/api/market/intelligence"),
  x402: () => getJSON<any>("/api/x402"),
  x402Teaser: () => getJSON<any>("/api/x402/alpha/teaser"),
  x402Buy: (payment_tx: string) =>
    fetch(`${API_BASE}/api/x402/alpha`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment_tx }),
    }).then(async (r) => ({ status: r.status, body: await r.json() })),
};

export type ThoughtStage =
  | "regime" | "screen" | "grade" | "vet" | "commit"
  | "guard" | "execute" | "exit" | "trail" | "proof" | "result" | "error";

export type Thought = { stage: ThoughtStage; payload: any };

// Stream a tick's reasoning passes via SSE (POST + ReadableStream).
export async function streamTick(
  body: object,
  onThought: (t: Thought) => void,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/agent/tick/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.body) throw new Error("no stream body");
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop() ?? "";
    for (const chunk of chunks) {
      let stage: string | null = null;
      let data: string | null = null;
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) stage = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (stage && data) {
        try {
          onThought({ stage: stage as ThoughtStage, payload: JSON.parse(data) });
        } catch {
          /* ignore partial */
        }
      }
    }
  }
}
