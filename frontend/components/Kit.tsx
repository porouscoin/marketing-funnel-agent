"use client";

import { useState } from "react";

import {
  PIECES,
  rescore,
  type Buyer,
  type Piece,
  type PieceId,
  type Reaction,
  type RescoreResult,
  type Score,
} from "@/lib/api";
import { reactionOf, type RunState } from "@/lib/run";
import {
  Email,
  GoogleAd,
  Hero,
  LinkedInAd,
  MetaAd,
  type Brand,
} from "./Mockups";

// Mirrors backend/app/formats.py. [limit] or [limit, count] for lists.
const LIMITS: Record<string, Record<string, number | [number, number]>> = {
  meta: { primary: 125, headline: 40 },
  google: { headlines: [30, 3], descriptions: [90, 2] },
  linkedin: { intro: 150, headline: 70 },
  hero: { headline: 70, subline: 160, cta: 24, proof: 110 },
  email: { subject: 60, preview: 90, body: 900 },
};
const kindOf = (id: PieceId) => (id.startsWith("email") ? "email" : id);

type Edit = {
  piece: Piece;
  base: "draft" | "rewrite";
  result?: RescoreResult;
  scored?: Piece;
  busy?: boolean;
  error?: string;
};

export const tone = (v: number, bar: number) =>
  v >= bar + 1.5 ? "good" : v >= bar ? "mid" : "bad";

function Limits({ id, piece }: { id: PieceId; piece: Piece }) {
  const rows: { label: string; n: number; max: number }[] = [];
  for (const [field, lim] of Object.entries(LIMITS[kindOf(id)])) {
    const v = piece[field];
    if (Array.isArray(lim))
      (Array.isArray(v) ? v : []).forEach((x, i) =>
        rows.push({
          label: `${field.replace(/s$/, "")} ${i + 1}`,
          n: x.length,
          max: lim[0],
        }),
      );
    else
      rows.push({
        label: field,
        n: typeof v === "string" ? v.length : 0,
        max: lim,
      });
  }
  return (
    <div className="limits">
      {rows.map((r) => (
        <span key={r.label} className={r.n > r.max ? "over" : ""}>
          {r.label} {r.n}/{r.max}
        </span>
      ))}
    </div>
  );
}

function Verdict({
  score,
  was,
  reactions,
  buyers,
  bar,
  errors,
}: {
  score: Score | null | undefined;
  was?: { label: string; score: Score | undefined };
  reactions: (Reaction | undefined)[];
  buyers: Buyer[];
  bar: number;
  errors: Record<string, string>;
}) {
  if (!score)
    return (
      <div className="verdict">
        <div className="waiting">The panel hasn't seen this yet.</div>
      </div>
    );
  return (
    <div className="verdict">
      <div className="score">
        <span className={`num ${tone(score.avg, bar)}`}>
          {score.avg.toFixed(1)}
        </span>
        <span className="of">/ 10</span>
        {was?.score && (
          <span className="was">
            {was.label} was {was.score.avg.toFixed(1)}
          </span>
        )}
      </div>
      <div className="sub">
        {score.clicks} of {score.n} would click
        {score.avg < bar ? ` · below the bar of ${bar}` : ""}
      </div>
      <ul className="reacts">
        {buyers.map((b, i) => {
          const r = reactions[i];
          return (
            <li key={b.id}>
              <span className="av sm" aria-hidden>
                {b.name[0]}
              </span>
              <span>
                <span className="n">{b.name}</span>
                <span className="q">
                  {r ? `“${r.objection}”` : errors[b.id] || "No answer"}
                </span>
              </span>
              {r && (
                <span
                  className={`s${r.click ? " click" : ""}`}
                  title={r.reason}
                >
                  {r.score}
                  <small>{r.click ? "clicks" : "scrolls"}</small>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function PieceRow({
  id,
  label,
  run,
  brand,
  bar,
}: {
  id: PieceId;
  label: string;
  run: RunState;
  brand: Brand;
  bar: number;
}) {
  const rewrite = run.rewrites[id];
  const [version, setVersion] = useState<"draft" | "rewrite" | null>(null);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState(false);
  const draft = run.drafts?.[id];
  if (!draft) return null;
  const shown: "draft" | "rewrite" =
    version ??
    ((run.scores[2]?.[id]?.avg ?? -1) >= (run.scores[1]?.[id]?.avg ?? 0)
      ? "rewrite"
      : "draft");
  const base = shown === "rewrite" && rewrite ? rewrite : draft;
  const piece = edit?.piece ?? base;
  const buyers = run.panel || [];
  const round = shown === "rewrite" ? 2 : 1;

  let score: Score | null | undefined = run.scores[round]?.[id];
  let reactions = buyers.map((b) => reactionOf(run, round, b.id, id));
  let was: { label: string; score: Score | undefined } | undefined =
    shown === "rewrite"
      ? { label: "first draft", score: run.scores[1]?.[id] }
      : undefined;
  if (edit?.result) {
    score = edit.result.score;
    reactions = buyers.map((b) =>
      (edit.result!.reactions[b.id] || []).find((r) => r.piece === id),
    );
    was = {
      label: edit.base === "rewrite" ? "rewrite" : "first draft",
      score: run.scores[edit.base === "rewrite" ? 2 : 1]?.[id],
    };
  } else if (edit) {
    score = null;
  }

  const onField = (field: string, value: string, index?: number) => {
    setEdit((e) => {
      const cur = e ?? { piece: base, base: shown };
      const next = { ...cur.piece } as Piece;
      if (index !== undefined) {
        const arr = [...((next[field] as string[]) || [])];
        arr[index] = value;
        next[field] = arr;
      } else next[field] = value;
      return { ...cur, piece: next };
    });
  };

  const send = async () => {
    if (!edit || !run.brief) return;
    setEditing(false);
    setEdit({ ...edit, busy: true, error: undefined });
    try {
      const result = await rescore(run.brief.product, buyers, id, edit.piece);
      setEdit({ ...edit, busy: false, result, scored: edit.piece });
    } catch (err) {
      setEdit({
        ...edit,
        busy: false,
        error: err instanceof Error ? err.message : "Couldn't re-score.",
      });
    }
  };

  const props = { piece, brand, editing, onField };
  const n = Number(id.replace("email", "")) || 1;
  const finished = !!run.done;

  return (
    <article className="piece">
      <div>
        <div className="piece-head">
          <div>
            <h4>{label}</h4>
            {piece.angle && <div className="angle">Angle: {piece.angle}</div>}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {id === "hero" && (
              <div className="seg" role="group" aria-label="Screen size">
                <button
                  className={!phone ? "on" : ""}
                  onClick={() => setPhone(false)}
                >
                  Desktop
                </button>
                <button
                  className={phone ? "on" : ""}
                  onClick={() => setPhone(true)}
                >
                  Phone
                </button>
              </div>
            )}
            {rewrite && !edit && (
              <div className="seg" role="group" aria-label="Version">
                <button
                  className={shown === "draft" ? "on" : ""}
                  onClick={() => setVersion("draft")}
                >
                  First draft
                </button>
                <button
                  className={shown === "rewrite" ? "on" : ""}
                  onClick={() => setVersion("rewrite")}
                >
                  Rewrite
                </button>
              </div>
            )}
          </div>
        </div>
        {id === "meta" && <MetaAd {...props} />}
        {id === "google" && <GoogleAd {...props} />}
        {id === "linkedin" && <LinkedInAd {...props} />}
        {id === "hero" && <Hero {...props} phone={phone} />}
        {kindOf(id) === "email" && <Email {...props} n={n} />}
        {shown === "rewrite" && !edit && rewrite?.addresses && (
          <div className="addresses">
            <b>What the rewrite answers:</b> {rewrite.addresses}
          </div>
        )}
        {editing && <Limits id={id} piece={piece} />}
        {finished && (
          <div className="edit-bar">
            {!editing && !edit?.busy && (
              <button
                className="btn ghost small"
                onClick={() => setEditing(true)}
              >
                Edit
              </button>
            )}
            {editing && (
              <button className="btn small" onClick={send} disabled={!edit}>
                Re-score with the panel
              </button>
            )}
            {editing && (
              <button
                className="btn ghost small"
                onClick={() => {
                  setEditing(false);
                  setEdit((e) =>
                    e?.result && e.scored ? { ...e, piece: e.scored } : null,
                  );
                }}
              >
                Cancel
              </button>
            )}
            {edit && !editing && !edit.busy && (
              <button className="btn ghost small" onClick={() => setEdit(null)}>
                Back to the agent&apos;s version
              </button>
            )}
            {editing && <span>Click any text in the mockup to change it.</span>}
            {edit?.busy && <span>The panel is reading your version…</span>}
            {edit?.error && (
              <span style={{ color: "var(--bad)" }}>{edit.error}</span>
            )}
          </div>
        )}
      </div>
      <Verdict
        score={score}
        was={was}
        reactions={reactions}
        buyers={buyers}
        bar={bar}
        errors={run.buyerErrors}
      />
    </article>
  );
}

export default function Kit({
  run,
  brand,
  bar,
}: {
  run: RunState;
  brand: Brand;
  bar: number;
}) {
  return (
    <div>
      {PIECES.map((p) => (
        <PieceRow
          key={p.id}
          id={p.id}
          label={p.label}
          run={run}
          brand={brand}
          bar={bar}
        />
      ))}
    </div>
  );
}
