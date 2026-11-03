export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export const PIECES = [
  { id: "meta", label: "Meta feed ad" },
  { id: "google", label: "Google search ad" },
  { id: "linkedin", label: "LinkedIn ad" },
  { id: "hero", label: "Landing page hero" },
  { id: "email1", label: "Email 1" },
  { id: "email2", label: "Email 2" },
  { id: "email3", label: "Email 3" },
] as const;
export type PieceId = (typeof PIECES)[number]["id"];

export type PageInfo = {
  url: string;
  domain: string;
  title: string;
  description: string;
  image: string;
};
export type Brief = {
  product: string;
  one_liner: string;
  category: string;
  audience: string;
  offer: string;
  proof: string[];
  tone: string;
  queries: string[];
};
export type Competitor = {
  name: string;
  url: string;
  claim: string;
  target: string;
  price: string;
  x: number;
  y: number;
};
export type Market = {
  competitors: Competitor[];
  axes: { x: { low: string; high: string }; y: { low: string; high: string } };
  product: { x: number; y: number };
  gap: { angle: string; why: string; evidence: string; verified: boolean };
  sources: { title: string; url: string }[];
};
export type Buyer = {
  id: string;
  name: string;
  role: string;
  cares: string;
  uses_today: string;
  doubt: string;
  style: string;
  model: string;
  model_label: string;
};
// Fields differ per piece; every value is a string or a list of strings.
export type Piece = { angle: string; addresses?: string } & Record<
  string,
  string | string[]
>;
export type Reaction = {
  piece: string;
  click: boolean;
  score: number;
  objection: string;
  reason: string;
};
export type Score = { avg: number; clicks: number; n: number; spread: number };
export type Step = {
  id: string;
  status: "running" | "done" | "skipped" | "error";
  label: string;
  detail: string | null;
};

export type RunEvent =
  | ({ type: "step" } & Step)
  | { type: "page"; value: PageInfo }
  | { type: "brief"; value: Brief }
  | { type: "market"; value: Market }
  | { type: "panel"; value: Buyer[] }
  | { type: "drafts"; value: Record<PieceId, Piece> }
  | {
      type: "reaction";
      round: number;
      buyer: string;
      value: Reaction[];
      error: string | null;
    }
  | { type: "scores"; round: number; value: Partial<Record<PieceId, Score>> }
  | { type: "rewrites"; value: Partial<Record<PieceId, Piece>> }
  | { type: "warning"; message: string }
  | { type: "error"; message: string; paste?: boolean }
  | {
      type: "done";
      calls?: number;
      tokens?: number;
      seconds?: number;
      models?: Record<string, number>;
    };

async function failure(res: Response): Promise<Error> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (body.detail)
      detail =
        typeof body.detail === "string"
          ? body.detail
          : "That input wasn't accepted.";
  } catch {}
  return new Error(detail);
}

/** Starts a run and calls onEvent for every event as it streams in. */
export async function startRun(
  body: { url?: string; text?: string },
  onEvent: (e: RunEvent) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_URL}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await failure(res);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)) as RunEvent);
    }
  }
}

export type RescoreResult = {
  reactions: Record<string, Reaction[]>;
  score: Score | null;
  problems: string[];
};

export async function rescore(
  product: string,
  buyers: Buyer[],
  piece_id: PieceId,
  piece: Piece,
): Promise<RescoreResult> {
  const res = await fetch(`${API_URL}/api/rescore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product,
      buyers: buyers.map(({ model_label: _, ...b }) => b),
      piece_id,
      piece,
    }),
  });
  if (!res.ok) throw await failure(res);
  return res.json();
}
