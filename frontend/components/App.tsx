"use client";

import { useEffect, useReducer, useRef, useState } from "react";

import { API_URL, startRun, type RunEvent } from "@/lib/api";
import { emptyRun, reduce, type RunState } from "@/lib/run";
import Kit from "./Kit";
import Market from "./Market";

const REPO = "https://github.com/porouscoin/marketing-funnel-agent";

type Action = { type: "reset" } | { type: "event"; e: RunEvent };
const runReducer = (s: RunState, a: Action): RunState =>
  a.type === "reset" ? emptyRun() : reduce(s, a.e);

function Steps({ run }: { run: RunState }) {
  return (
    <ol className="steps" aria-live="polite">
      {run.steps.map((s) => (
        <li key={s.id} className={s.status}>
          <span className="dot" aria-hidden />
          <span>
            {s.label}
            {s.detail && <span className="detail">{s.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Stats({ done }: { done: NonNullable<RunState["done"]> }) {
  const models = Object.entries(done.models || {});
  return (
    <div className="stats">
      {done.calls ?? 0} model calls
      {done.seconds ? ` in ${Math.round(done.seconds)} s` : ""}
      {models.length > 0 && (
        <div>{models.map(([m, n]) => `${m} ×${n}`).join(", ")}</div>
      )}
    </div>
  );
}

function Brief({ run }: { run: RunState }) {
  const b = run.brief!;
  const p = run.page;
  return (
    <>
      {p && (p.title || p.image) && (
        <div className="page-card">
          {p.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={p.image}
              alt=""
              referrerPolicy="no-referrer"
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          )}
          <div>
            <div className="t">{p.title}</div>
            {p.url && (
              <a
                className="d"
                href={p.url}
                target="_blank"
                rel="noreferrer noopener"
              >
                {p.domain} ↗
              </a>
            )}
          </div>
        </div>
      )}
      <dl className="kv">
        <dt>What it is</dt>
        <dd>{b.one_liner || b.category}</dd>
        <dt>Who it&apos;s for</dt>
        <dd>{b.audience}</dd>
        <dt>The offer</dt>
        <dd>{b.offer}</dd>
        <dt>Proof on the page</dt>
        <dd>
          {b.proof.length ? (
            <ul>
              {b.proof.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          ) : (
            "None found"
          )}
        </dd>
        <dt>Voice</dt>
        <dd>{b.tone}</dd>
      </dl>
    </>
  );
}

function Panel({ run }: { run: RunState }) {
  return (
    <div className="buyers">
      {run.panel!.map((b) => (
        <div className="buyer" key={b.id}>
          <div className="who">
            <span className="av" aria-hidden>
              {b.name[0]}
            </span>
            <div>
              <div className="name">{b.name}</div>
              <div className="role">{b.role}</div>
            </div>
          </div>
          <dl>
            <dt>Cares about</dt>
            <dd>{b.cares}</dd>
            <dt>Uses today</dt>
            <dd>{b.uses_today}</dd>
            <dt>Main doubt</dt>
            <dd>{b.doubt}</dd>
          </dl>
          {b.model_label && (
            <div className="model">thinks with {b.model_label}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [run, dispatch] = useReducer(runReducer, emptyRun());
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [paste, setPaste] = useState(false);
  const [formError, setFormError] = useState("");
  const [source, setSource] = useState("");
  const [bar, setBar] = useState(6);
  const [replay, setReplay] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then((r) => r.json())
      .then((c) => typeof c.bar === "number" && setBar(c.bar))
      .catch(() => {});
  }, []);

  const begin = async (
    body: { url?: string; text?: string },
    label: string,
  ) => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setFormError("");
    setBusy(true);
    try {
      let started = false;
      await startRun(
        body,
        (e) => {
          if (!started) {
            started = true;
            dispatch({ type: "reset" });
            setSource(label);
            setReplay(false);
            setActive(true);
            window.scrollTo({ top: 0 });
          }
          dispatch({ type: "event", e });
        },
        ctrl.signal,
      );
    } catch (err) {
      if (!ctrl.signal.aborted)
        setFormError(
          err instanceof Error ? err.message : "Something went wrong.",
        );
    } finally {
      if (abort.current === ctrl) setBusy(false);
    }
  };

  const example = async () => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setFormError("");
    const events: RunEvent[] = await fetch("/example.json").then((r) =>
      r.json(),
    );
    dispatch({ type: "reset" });
    const page = events.find((e) => e.type === "page");
    setSource(
      page && page.type === "page" ? page.value.domain || "Example" : "Example",
    );
    setReplay(true);
    setActive(true);
    setBusy(true);
    window.scrollTo({ top: 0 });
    // Replays a saved run at a watchable pace.
    for (const e of events) {
      if (ctrl.signal.aborted) return;
      dispatch({ type: "event", e });
      const wait =
        e.type === "step"
          ? e.status === "running"
            ? 700
            : 120
          : e.type === "reaction"
            ? 220
            : 60;
      await new Promise((r) => setTimeout(r, wait));
    }
    setBusy(false);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (paste) {
      if (text.trim().length < 200)
        return setFormError(
          "Paste a bit more of the page: at least a few paragraphs.",
        );
      begin({ text }, "Pasted page text");
    } else {
      if (!url.trim())
        return setFormError("Paste a product page address first.");
      begin(
        { url: url.trim() },
        url
          .trim()
          .replace(/^https?:\/\//, "")
          .replace(/\/$/, ""),
      );
    }
  };

  const reset = () => {
    abort.current?.abort();
    setBusy(false);
    setActive(false);
    dispatch({ type: "reset" });
  };

  const brand = {
    name: run.brief?.product || "Your brand",
    domain: run.page?.domain || "",
    image: run.page?.image || "",
  };

  return (
    <>
      <div className="wrap">
        <header className="top">
          <button
            className="brand"
            onClick={reset}
            aria-label="Marketing funnel agent, start over"
          >
            <i aria-hidden>
              <svg width="12" height="12" viewBox="0 0 12 12">
                <path d="M1 2h10L7 7v3.5L5 11V7z" fill="var(--accent-ink)" />
              </svg>
            </i>
            Funnel agent
          </button>
          <nav>
            <a
              className="hide-sm"
              href={REPO}
              target="_blank"
              rel="noreferrer noopener"
            >
              Code on GitHub
            </a>
          </nav>
        </header>

        {!active && (
          <>
            <section className="hero">
              <h1>
                Your launch kit, tested on five buyers before you ship it.
              </h1>
              <p className="lede">
                Paste a product page. The agent finds the competitors and the
                angle none of them own, writes the ads, the landing hero and an
                email sequence, then shows every piece to a panel of synthetic
                buyers and rewrites what they reject.
              </p>
              <form onSubmit={submit}>
                {!paste ? (
                  <div className="ask">
                    <input
                      type="text"
                      inputMode="url"
                      placeholder="yourproduct.com"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      aria-label="Product page address"
                      autoComplete="url"
                    />
                    <button className="btn" disabled={busy}>
                      {busy ? "Starting…" : "Run the agent"}
                    </button>
                  </div>
                ) : (
                  <div className="paste">
                    <textarea
                      placeholder="Paste the text of the product page: headline, features, pricing, proof."
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      aria-label="Product page text"
                    />
                    <div className="row">
                      <button className="btn" disabled={busy}>
                        {busy ? "Starting…" : "Run the agent"}
                      </button>
                    </div>
                  </div>
                )}
              </form>
              {formError && <div className="form-error">{formError}</div>}
              <div className="links">
                <button
                  className="linkish"
                  onClick={() => (setPaste(!paste), setFormError(""))}
                >
                  {paste ? "Use a URL instead" : "Paste the page text instead"}
                </button>
                <button className="linkish" onClick={example}>
                  See an example run
                </button>
              </div>
            </section>
            <section className="how" aria-label="How it works">
              <ol>
                <li>
                  <b>Reads the page</b>
                </li>
                <li>Finds 3 competitors</li>
                <li>Builds 5 buyers</li>
                <li>Writes 7 pieces</li>
                <li>Buyers react</li>
                <li>Rewrites the weak ones</li>
              </ol>
            </section>
          </>
        )}

        {active && (
          <div className="run">
            <aside>
              <div className="run-head">
                <div className="k">{busy ? "Working on" : "Run for"}</div>
                <h2>{source}</h2>
              </div>
              <Steps run={run} />
              {run.done && <Stats done={run.done} />}
              <div className="aside-actions">
                <button className="btn ghost small" onClick={reset}>
                  New run
                </button>
              </div>
            </aside>
            <main>
              {run.error && (
                <div className="notice bad">
                  {run.error}
                  {run.pasteHint && (
                    <div style={{ marginTop: 8 }}>
                      <button
                        className="linkish"
                        onClick={() => {
                          reset();
                          setPaste(true);
                        }}
                      >
                        Paste the page text instead
                      </button>
                    </div>
                  )}
                </div>
              )}
              {replay && (
                <div className="notice">
                  A saved run on {source}&apos;s public home page, replayed. All
                  the copy and the buyers are the agent&apos;s; nothing here
                  comes from {source} itself.
                </div>
              )}
              {run.warning && <div className="notice">{run.warning}</div>}

              {run.brief && (
                <section className="sec">
                  <header>
                    <h3>The brief</h3>
                    <p>
                      What the agent took from the page. Everything after this
                      is built on it.
                    </p>
                  </header>
                  <Brief run={run} />
                </section>
              )}

              {run.market && (
                <section className="sec">
                  <header>
                    <h3>The market</h3>
                    <p>
                      Competitors found by web search, read from their own home
                      pages.
                    </p>
                  </header>
                  <Market
                    m={run.market}
                    product={run.brief?.product || "You"}
                  />
                </section>
              )}

              {run.panel && (
                <section className="sec">
                  <header>
                    <h3>The panel</h3>
                    <p>
                      Five synthetic buyers built from the page. They are
                      simulations for spotting weak copy, not a forecast of real
                      click rates.
                    </p>
                  </header>
                  <Panel run={run} />
                </section>
              )}

              {run.drafts && (
                <section className="sec">
                  <header>
                    <h3>The kit</h3>
                    <p>
                      Every piece as it would appear, with each buyer&apos;s
                      reaction. Pieces scoring under {bar} were rewritten to
                      answer the objections, then scored again.
                      {run.done
                        ? " Edit any piece and the panel will read it again."
                        : ""}
                    </p>
                  </header>
                  <Kit run={run} brand={brand} bar={bar} />
                </section>
              )}
            </main>
          </div>
        )}
      </div>
      <footer className="footer">
        <div className="wrap">
          Built by{" "}
          <a
            href="https://ziyadhisham.com"
            target="_blank"
            rel="noreferrer noopener"
          >
            Ziyad Hisham
          </a>
          . The buyers are AI simulations; use them to find weak copy, not to
          predict results.
        </div>
      </footer>
    </>
  );
}
