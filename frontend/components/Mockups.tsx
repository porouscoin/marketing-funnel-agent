"use client";

import { useRef, useState } from "react";

import type { Piece } from "@/lib/api";

export type Brand = { name: string; domain: string; image: string };
type Props = {
  piece: Piece;
  brand: Brand;
  editing: boolean;
  onField: (field: string, value: string, index?: number) => void;
};

/**
 * A span the visitor can type into while editing. The text is read back on every
 * keystroke so the character counters stay live. While editing, the span keeps
 * rendering the text it started with, so React never rewrites the DOM under the
 * caret; when editing ends it remounts with the new value.
 */
function Text({
  value,
  editing,
  onChange,
  className,
  multiline,
  label,
}: {
  value: string;
  editing: boolean;
  onChange: (v: string) => void;
  className?: string;
  multiline?: boolean;
  label: string;
}) {
  const start = useRef(value);
  if (!editing) start.current = value;
  return (
    <span
      key={editing ? "editing" : "view"}
      className={className}
      contentEditable={editing ? "plaintext-only" : false}
      suppressContentEditableWarning
      role={editing ? "textbox" : undefined}
      aria-label={editing ? label : undefined}
      aria-multiline={editing && multiline ? true : undefined}
      onInput={(e) =>
        onChange((e.currentTarget.textContent || "").replace(/ /g, " "))
      }
      onKeyDown={(e) => {
        if (e.key === "Enter" && !multiline) {
          e.preventDefault();
          e.currentTarget.blur();
        }
      }}
    >
      {editing ? start.current : value}
    </span>
  );
}

const s = (v: string | string[] | undefined) =>
  typeof v === "string" ? v : "";
const list = (v: string | string[] | undefined) => (Array.isArray(v) ? v : []);
const initial = (name: string) => (name.trim()[0] || "?").toUpperCase();

function Picture({ brand }: { brand: Brand }) {
  const [broken, setBroken] = useState(false);
  return (
    <div className="m-img">
      {brand.image && !broken ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={brand.image}
          alt=""
          onError={() => setBroken(true)}
          referrerPolicy="no-referrer"
        />
      ) : (
        <span>{brand.name}</span>
      )}
    </div>
  );
}

export function MetaAd({ piece, brand, editing, onField }: Props) {
  return (
    <div className="mock fb">
      <div className="m-head">
        <div className="m-logo">{initial(brand.name)}</div>
        <div>
          <div className="m-name">{brand.name}</div>
          <div className="m-sub">Sponsored</div>
        </div>
      </div>
      <div className="m-body">
        <Text
          label="Primary text"
          value={s(piece.primary)}
          editing={editing}
          onChange={(v) => onField("primary", v)}
          multiline
        />
      </div>
      <Picture brand={brand} />
      <div className="m-foot">
        <div style={{ minWidth: 0 }}>
          <div className="m-domain">{brand.domain || "yoursite.com"}</div>
          <div className="m-title">
            <Text
              label="Headline"
              value={s(piece.headline)}
              editing={editing}
              onChange={(v) => onField("headline", v)}
            />
          </div>
        </div>
        <div className="m-cta">{s(piece.cta)}</div>
      </div>
    </div>
  );
}

export function GoogleAd({ piece, brand, editing, onField }: Props) {
  const heads = list(piece.headlines);
  const descs = list(piece.descriptions);
  return (
    <div className="mock serp">
      <div className="spons">Sponsored</div>
      <div className="site">
        <div className="m-logo">{initial(brand.name)}</div>
        <div>
          <div>{brand.name}</div>
          <div className="url">https://{brand.domain || "yoursite.com"}</div>
        </div>
      </div>
      <div className="h">
        {heads.map((h, i) => (
          <span key={i}>
            {i > 0 && " | "}
            <Text
              label={`Headline ${i + 1}`}
              value={h}
              editing={editing}
              onChange={(v) => onField("headlines", v, i)}
            />
          </span>
        ))}
      </div>
      <div className="desc">
        {descs.map((d, i) => (
          <span key={i}>
            {i > 0 && " "}
            <Text
              label={`Description ${i + 1}`}
              value={d}
              editing={editing}
              onChange={(v) => onField("descriptions", v, i)}
            />
          </span>
        ))}
      </div>
    </div>
  );
}

export function LinkedInAd({ piece, brand, editing, onField }: Props) {
  return (
    <div className="mock li">
      <div className="m-head">
        <div className="m-logo">{initial(brand.name)}</div>
        <div>
          <div className="m-name">{brand.name}</div>
          <div className="m-sub">Promoted</div>
        </div>
      </div>
      <div className="m-body">
        <Text
          label="Intro text"
          value={s(piece.intro)}
          editing={editing}
          onChange={(v) => onField("intro", v)}
          multiline
        />
      </div>
      <Picture brand={brand} />
      <div className="m-foot">
        <div style={{ minWidth: 0 }}>
          <div className="m-title">
            <Text
              label="Headline"
              value={s(piece.headline)}
              editing={editing}
              onChange={(v) => onField("headline", v)}
            />
          </div>
          <div className="m-sub">{brand.domain || "yoursite.com"}</div>
        </div>
        <div className="m-cta">{s(piece.cta)}</div>
      </div>
    </div>
  );
}

export function Hero({
  piece,
  brand,
  editing,
  onField,
  phone,
}: Props & { phone: boolean }) {
  return (
    <div className={`mock site${phone ? " phone" : ""}`}>
      <div className="bar">
        <i />
        <i />
        <i />
        <span>{brand.domain || "yoursite.com"}</span>
      </div>
      <div className="stage">
        <div className="hl">
          <Text
            label="Headline"
            value={s(piece.headline)}
            editing={editing}
            onChange={(v) => onField("headline", v)}
          />
        </div>
        <div className="sl">
          <Text
            label="Subline"
            value={s(piece.subline)}
            editing={editing}
            onChange={(v) => onField("subline", v)}
            multiline
          />
        </div>
        <span className="cta">
          <Text
            label="Button"
            value={s(piece.cta)}
            editing={editing}
            onChange={(v) => onField("cta", v)}
          />
        </span>
        <div className="pf">
          <Text
            label="Proof line"
            value={s(piece.proof)}
            editing={editing}
            onChange={(v) => onField("proof", v)}
          />
        </div>
      </div>
    </div>
  );
}

export function Email({
  piece,
  brand,
  editing,
  onField,
  n,
}: Props & { n: number }) {
  return (
    <div className="mock inbox">
      <div className="row open">
        <span className="from">{brand.name}</span>
        <span>
          <span className="subj">{s(piece.subject)}</span>
          <span className="prev"> · {s(piece.preview)}</span>
        </span>
      </div>
      <div className="mail">
        <div className="subject">
          <Text
            label="Subject"
            value={s(piece.subject)}
            editing={editing}
            onChange={(v) => onField("subject", v)}
          />
        </div>
        <div className="meta">
          From {brand.name} · email {n} of 3 ·{" "}
          {editing ? (
            <>
              preview:{" "}
              <Text
                label="Preview text"
                value={s(piece.preview)}
                editing
                onChange={(v) => onField("preview", v)}
              />
            </>
          ) : (
            "to you"
          )}
        </div>
        <div className="body">
          <Text
            label="Body"
            value={s(piece.body)}
            editing={editing}
            onChange={(v) => onField("body", v)}
            multiline
          />
        </div>
      </div>
    </div>
  );
}
