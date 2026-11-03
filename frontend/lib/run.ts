import type {
  Brief,
  Buyer,
  Market,
  PageInfo,
  Piece,
  PieceId,
  Reaction,
  RunEvent,
  Score,
  Step,
} from "./api";

export type RunState = {
  steps: Step[];
  page: PageInfo | null;
  brief: Brief | null;
  market: Market | null;
  panel: Buyer[] | null;
  drafts: Record<PieceId, Piece> | null;
  // round -> buyer id -> reactions. Round 1 = first drafts, 2 = rewrites.
  reactions: Record<number, Record<string, Reaction[]>>;
  buyerErrors: Record<string, string>;
  scores: Record<number, Partial<Record<PieceId, Score>>>;
  rewrites: Partial<Record<PieceId, Piece>>;
  warning: string | null;
  error: string | null;
  pasteHint: boolean;
  done: {
    calls?: number;
    seconds?: number;
    models?: Record<string, number>;
  } | null;
  events: RunEvent[]; // kept so a finished run can be replayed or shared
};

export const emptyRun = (): RunState => ({
  steps: [],
  page: null,
  brief: null,
  market: null,
  panel: null,
  drafts: null,
  reactions: {},
  buyerErrors: {},
  scores: {},
  rewrites: {},
  warning: null,
  error: null,
  pasteHint: false,
  done: null,
  events: [],
});

export function reduce(s: RunState, e: RunEvent): RunState {
  const next = { ...s, events: [...s.events, e] };
  switch (e.type) {
    case "step": {
      const { type: _, ...step } = e;
      const i = s.steps.findIndex((x) => x.id === step.id);
      next.steps =
        i < 0
          ? [...s.steps, step]
          : s.steps.map((x, j) => (j === i ? step : x));
      return next;
    }
    case "page":
      return { ...next, page: e.value };
    case "brief":
      return { ...next, brief: e.value };
    case "market":
      return { ...next, market: e.value };
    case "panel":
      return { ...next, panel: e.value };
    case "drafts":
      return { ...next, drafts: e.value };
    case "reaction":
      return {
        ...next,
        reactions: {
          ...s.reactions,
          [e.round]: { ...(s.reactions[e.round] || {}), [e.buyer]: e.value },
        },
        buyerErrors: e.error
          ? { ...s.buyerErrors, [e.buyer]: e.error }
          : s.buyerErrors,
      };
    case "scores":
      return { ...next, scores: { ...s.scores, [e.round]: e.value } };
    case "rewrites":
      return { ...next, rewrites: e.value };
    case "warning":
      return { ...next, warning: e.message };
    case "error":
      return { ...next, error: e.message, pasteHint: !!e.paste };
    case "done":
      return {
        ...next,
        done: { calls: e.calls, seconds: e.seconds, models: e.models },
      };
  }
  return next;
}

/** One buyer's reaction to one piece in a round. */
export const reactionOf = (
  s: RunState,
  round: number,
  buyer: string,
  piece: PieceId,
) => (s.reactions[round]?.[buyer] || []).find((r) => r.piece === piece);
