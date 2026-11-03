import type { Market as MarketData } from "@/lib/api";

const S = 360; // drawing size
const P = { l: 18, r: 18, t: 18, b: 44 }; // room for axis labels at the bottom

/** Two axes the agent picked for this category, every product placed on them, the emptiest quarter shaded. */
function Map({ m, product }: { m: MarketData; product: string }) {
  const w = S - P.l - P.r;
  const h = S - P.t - P.b;
  const X = (v: number) => P.l + v * w;
  const Y = (v: number) => P.t + (1 - v) * h;
  const quarters = [
    { x: 0, y: 1 },
    { x: 1, y: 1 },
    { x: 0, y: 0 },
    { x: 1, y: 0 },
  ].map((q) => ({
    ...q,
    n: m.competitors.filter(
      (c) => (c.x >= 0.5 ? 1 : 0) === q.x && (c.y >= 0.5 ? 1 : 0) === q.y,
    ).length,
    mine:
      (m.product.x >= 0.5 ? 1 : 0) === q.x &&
      (m.product.y >= 0.5 ? 1 : 0) === q.y,
  }));
  const fewest = Math.min(...quarters.map((q) => q.n));
  const open = quarters
    .filter((q) => q.n === fewest)
    .sort((a, b) => Number(b.mine) - Number(a.mine))[0];
  const label = (x: number) =>
    x > 0.68
      ? { anchor: "end" as const, dx: -12 }
      : { anchor: "start" as const, dx: 12 };
  const dots = [
    ...m.competitors.map((c) => ({ name: c.name, x: c.x, y: c.y, me: false })),
    { name: product, x: m.product.x, y: m.product.y, me: true },
  ];
  return (
    <svg
      className="map"
      viewBox={`0 0 ${S} ${S}`}
      role="img"
      aria-label={`Positioning map: ${m.axes.x.low} to ${m.axes.x.high}, ${m.axes.y.low} to ${m.axes.y.high}`}
    >
      {fewest === 0 && (
        <g>
          <rect
            x={X(open.x * 0.5)}
            y={Y(open.y * 0.5 + 0.5)}
            width={w / 2}
            height={h / 2}
            fill="var(--accent)"
            opacity="0.07"
          />
          <text
            x={X(open.x * 0.5 + 0.25)}
            y={Y(open.y * 0.5 + 0.5) + 22}
            textAnchor="middle"
            fontSize="12"
            fill="var(--accent)"
            opacity="0.85"
          >
            open space
          </text>
        </g>
      )}
      <rect
        x={P.l}
        y={P.t}
        width={w}
        height={h}
        fill="none"
        stroke="var(--line-2)"
      />
      <line
        x1={X(0.5)}
        x2={X(0.5)}
        y1={P.t}
        y2={P.t + h}
        stroke="var(--line)"
      />
      <line
        x1={P.l}
        x2={P.l + w}
        y1={Y(0.5)}
        y2={Y(0.5)}
        stroke="var(--line)"
      />
      <text x={P.l} y={S - 22} fontSize="12.5" fill="var(--text-3)">
        ← {m.axes.x.low}
      </text>
      <text
        x={P.l + w}
        y={S - 22}
        fontSize="12.5"
        fill="var(--text-3)"
        textAnchor="end"
      >
        {m.axes.x.high} →
      </text>
      <text x={P.l + 8} y={P.t + 16} fontSize="12.5" fill="var(--text-3)">
        ↑ {m.axes.y.high}
      </text>
      <text x={P.l + 8} y={P.t + h - 8} fontSize="12.5" fill="var(--text-3)">
        ↓ {m.axes.y.low}
      </text>
      {dots.map((d) => {
        const l = label(d.x);
        return (
          <g key={d.name + d.me}>
            <circle
              cx={X(d.x)}
              cy={Y(d.y)}
              r={d.me ? 8 : 6}
              fill={d.me ? "var(--accent)" : "var(--text-3)"}
              stroke="var(--bg)"
              strokeWidth="2"
            />
            <text
              x={X(d.x) + l.dx}
              y={Y(d.y) + 4.5}
              textAnchor={l.anchor}
              fontSize={d.me ? 14 : 13}
              fontWeight={d.me ? 600 : 400}
              fill={d.me ? "var(--text)" : "var(--text-2)"}
              stroke="var(--bg)"
              strokeWidth="4"
              paintOrder="stroke"
            >
              {d.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Market({
  m,
  product,
}: {
  m: MarketData;
  product: string;
}) {
  return (
    <>
      <div className="market">
        <Map m={m} product={product} />
        {m.gap.angle && (
          <div className="gap">
            <div className="k">The gap</div>
            <p className="angle">{m.gap.angle}</p>
            {m.gap.why && <p className="why">{m.gap.why}</p>}
            {m.gap.evidence && <blockquote>“{m.gap.evidence}”</blockquote>}
            <div className={`check${m.gap.verified ? "" : " no"}`}>
              {m.gap.verified
                ? "This quote was checked against the product page."
                : "This quote wasn't found word for word on the page, so treat the angle with care."}
            </div>
          </div>
        )}
      </div>
      <table className="comp">
        <thead>
          <tr>
            <th>Competitor</th>
            <th>What they lead with</th>
            <th>Who for</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {m.competitors.map((c) => (
            <tr key={c.url}>
              <td data-label="Competitor">
                <span>
                  {c.name}
                  <a href={c.url} target="_blank" rel="noreferrer noopener">
                    {c.url
                      .replace(/^https?:\/\/(www\.)?/, "")
                      .replace(/\/$/, "")}{" "}
                    ↗
                  </a>
                </span>
              </td>
              <td data-label="Leads with">{c.claim}</td>
              <td data-label="Who for">{c.target}</td>
              <td data-label="Price">{c.price}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
