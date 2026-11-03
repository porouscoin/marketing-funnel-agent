"""The agent loop: read the page, map the market, build a panel, draft, test, rewrite.

run_agent() is an async generator of events. The API streams each one to the
browser as it happens, so the visitor watches every step: "step" events drive
the step log, the others carry the results each part of the page is drawn from.
"""

import asyncio
import statistics
import time
from typing import Any, AsyncIterator

from . import prompts
from .config import ModelSpec, model_registry, settings
from .formats import LABELS, PIECE_IDS, as_text, clean, clean_piece, fit, kind, problems
from .page import Page, PageError, backed_by, domain_of, extract, fetch_html, from_text, normalize_url, read_page
from .providers import ProviderError, Usage, ask_json
from .search import SearchError, search

REG = model_registry()


def models(order: tuple[str, ...]) -> list[ModelSpec]:
    return [REG[m] for m in order if m in REG]


def mock_only() -> bool:
    return all(s.provider == "mock" for s in REG.values())


def step(id: str, status: str, label: str, detail: str | None = None) -> dict:
    return {"type": "step", "id": id, "status": status, "label": label, "detail": detail}


def _s(v: Any, limit: int = 300) -> str:
    return " ".join(str(v or "").split())[:limit]


def _clamp(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


# ---------- 1. the brief ----------


def clean_brief(raw: dict, page: Page) -> dict:
    proof = raw.get("proof") if isinstance(raw.get("proof"), list) else []
    queries = raw.get("queries") if isinstance(raw.get("queries"), list) else []
    brief = {
        "product": _s(raw.get("product"), 80) or page.site_name or page.title[:60] or "This product",
        "one_liner": _s(raw.get("one_liner"), 160),
        "category": _s(raw.get("category"), 60) or "software",
        "audience": _s(raw.get("audience"), 160),
        "offer": _s(raw.get("offer"), 200),
        "proof": [_s(p, 200) for p in proof if _s(p)][:4],
        "tone": _s(raw.get("tone"), 60),
        "queries": [_s(q, 120) for q in queries if _s(q)][:2],
    }
    if not brief["queries"]:
        brief["queries"] = [f"{brief['category']} alternatives", f"best {brief['category']}"]
    return brief


# ---------- 2. the market ----------


async def _competitor_page(url: str) -> Page | None:
    try:
        html, final = await fetch_html(url, timeout=8.0)
    except PageError:
        return None
    page = extract(html, final)
    return page if (page.title or page.description or page.headings) else None


def _mock_competitors(brief: dict) -> list[tuple[dict, Page]]:
    out = []
    for i, name in enumerate(["Northwind", "Brightlane", "Clearpath"]):
        url = f"https://{name.lower()}.example.com"
        page = Page(url=url, domain=domain_of(url), title=f"{name}: the {brief['category']} for growing teams")
        out.append(({"name": name, "url": url}, page))
    return out


def _competitor_brief(page: Page) -> str:
    return "\n".join(
        x
        for x in [
            f"Title: {page.title}",
            f"Description: {page.description}" if page.description else "",
            "Headings: " + " | ".join(page.headings[:8]) if page.headings else "",
            page.text[:1200],
        ]
        if x
    )


def clean_market(raw: dict, found: list[tuple[dict, Page]], page: Page) -> dict:
    rows = raw.get("competitors") if isinstance(raw.get("competitors"), list) else []
    pos = raw.get("positions") if isinstance(raw.get("positions"), dict) else {}
    cpos = pos.get("competitors") if isinstance(pos.get("competitors"), list) else []
    competitors = []
    for i, (pick, cpage) in enumerate(found):
        row = rows[i] if i < len(rows) and isinstance(rows[i], dict) else {}
        p = cpos[i] if i < len(cpos) and isinstance(cpos[i], dict) else {}
        competitors.append(
            {
                "name": _s(row.get("name"), 60) or pick["name"],
                "url": cpage.url,
                "claim": _s(row.get("claim"), 140) or cpage.title,
                "target": _s(row.get("target"), 100) or "not stated",
                "price": _s(row.get("price"), 80) or "not shown",
                "x": _clamp(p.get("x"), 0, 1, 0.5),
                "y": _clamp(p.get("y"), 0, 1, 0.5),
            }
        )
    axes = raw.get("axes") if isinstance(raw.get("axes"), dict) else {}

    def axis(k: str, lo: str, hi: str) -> dict:
        a = axes.get(k) if isinstance(axes.get(k), dict) else {}
        return {"low": _s(a.get("low"), 30) or lo, "high": _s(a.get("high"), 30) or hi}

    me = pos.get("product") if isinstance(pos.get("product"), dict) else {}
    gap = raw.get("gap") if isinstance(raw.get("gap"), dict) else {}
    evidence = _s(gap.get("evidence"), 300)
    return {
        "competitors": competitors,
        "axes": {"x": axis("x", "simple", "powerful"), "y": axis("y", "solo", "team")},
        "product": {"x": _clamp(me.get("x"), 0, 1, 0.5), "y": _clamp(me.get("y"), 0, 1, 0.5)},
        "gap": {
            "angle": _s(gap.get("angle"), 240),
            "why": _s(gap.get("why"), 240),
            "evidence": evidence,
            # The agent must not claim a position the product's own page doesn't back up.
            "verified": backed_by(evidence, page),
        },
    }


async def market_steps(page: Page, brief: dict, usage: Usage) -> AsyncIterator[dict]:
    writer = models(settings.writer_models)
    found: list[tuple[dict, Page]] = []
    sources: list[dict] = []
    if mock_only() and not settings.tavily_key:
        found = _mock_competitors(brief)
        yield step("search", "done", "Searched for competitors", "Mock data: search isn't set up locally")
    else:
        yield step("search", "running", "Searching for competitors", " · ".join(brief["queries"]))
        results: list[dict] = []
        try:
            for batch in await asyncio.gather(*(search(q) for q in brief["queries"])):
                results.extend(batch)
        except SearchError as e:
            yield step("search", "skipped", "Competitor search skipped", str(e))
            return
        seen = set()
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                sources.append(r)
        listing = "\n".join(f"- {r['title']} ({r['url']}): {r['snippet'][:200]}" for r in sources[:12])
        picked, _ = await ask_json(
            "pick",
            writer,
            prompts.PICK,
            f"Product: {brief['product']}, {brief['one_liner']} ({brief['category']})\n"
            f"Product site: {page.domain or 'unknown'}\n\nSearch results:\n{listing}",
            usage,
            max_tokens=500,
            temperature=0.2,
        )
        candidates = []
        for c in picked.get("competitors") or []:
            if not isinstance(c, dict):
                continue
            try:
                url = normalize_url(_s(c.get("url"), 200))
            except PageError:
                continue
            d = domain_of(url)
            if d and d != page.domain and d not in {domain_of(x["url"]) for x in candidates}:
                candidates.append({"name": _s(c.get("name"), 60), "url": url})
        yield step("search", "done", "Searched for competitors", f"{len(sources)} results, {len(candidates)} candidates")
        if not candidates:
            yield step("market", "skipped", "No clear competitors found", "The drafts will lean on the page alone")
            return
        yield step("visit", "running", "Reading competitor pages", ", ".join(c["name"] for c in candidates[:4]))
        pages = await asyncio.gather(*(_competitor_page(c["url"]) for c in candidates[:4]))
        found = [(c, p) for c, p in zip(candidates, pages) if p][:3]
        yield step("visit", "done", "Read competitor pages", f"{len(found)} of {len(candidates[:4])} pages readable")
        if not found:
            yield step("market", "skipped", "Competitor pages couldn't be read", "The drafts will lean on the page alone")
            return

    yield step("market", "running", "Mapping positions and finding the gap")
    listing = "\n\n".join(f"## Competitor {i + 1}: {c['name']} ({p.url})\n{_competitor_brief(p)}" for i, (c, p) in enumerate(found))
    raw, _ = await ask_json(
        "market",
        writer,
        prompts.MARKET,
        f"# PRODUCT\n{prompts.dump(brief)}\n\nProduct page:\n{page.for_prompt(3500)}\n\n# COMPETITORS\n{listing}",
        usage,
        max_tokens=1400,
        temperature=0.4,
    )
    market = clean_market(raw, found, page)
    market["sources"] = [{"title": r["title"], "url": r["url"]} for r in sources[:8]]
    yield {"type": "market", "value": market}
    detail = market["gap"]["angle"] or "No clear gap"
    if not market["gap"]["verified"]:
        detail += " (quote not found on the page)"
    yield step("market", "done", "Found the gap", detail)


# ---------- 3. the panel ----------


def clean_panel(raw: dict) -> list[dict]:
    rows = raw.get("buyers") if isinstance(raw.get("buyers"), list) else []
    specs = models(settings.buyer_models)
    buyers = []
    for i, b in enumerate([r for r in rows if isinstance(r, dict)][:5]):
        name = _s(b.get("name"), 30) or f"Buyer {i + 1}"
        spec = specs[i % len(specs)] if specs else None
        buyers.append(
            {
                "id": f"b{i + 1}",
                "name": name,
                "role": _s(b.get("role"), 100),
                "cares": _s(b.get("cares"), 140),
                "uses_today": _s(b.get("uses_today"), 100) or "nothing in particular",
                "doubt": _s(b.get("doubt"), 160),
                "style": _s(b.get("style"), 100) or "skims",
                "model": spec.id if spec else "",
                "model_label": spec.label if spec else "",
            }
        )
    return buyers


# ---------- 4. drafts ----------


def _context(brief: dict, market: dict | None, page: Page, buyers: list[dict] | None = None) -> str:
    """What the writer sees: the brief, the page itself (for facts), the gap and the panel."""
    gap = market["gap"] if market else None
    out = f"# PRODUCT BRIEF\n{prompts.dump(brief)}\n\n# THE PRODUCT PAGE (the only source of facts)\n{page.for_prompt(4500)}\n\n"
    if gap and gap["angle"]:
        out += f"# THE GAP (the angle no competitor owns)\n{prompts.dump(gap)}\n\n"
    else:
        out += "# THE GAP\nNo competitor research is available. Pick angles from what is distinctive on the page.\n\n"
    if buyers:
        out += "# THE PANEL\n" + "\n".join(f"- {b['name']}, {b['role']}. Cares about {b['cares']}. Doubt: {b['doubt']}" for b in buyers)
    return out


async def enforce(pieces: dict[str, dict], usage: Usage) -> tuple[dict[str, dict], int]:
    """Length and format rules: one fix-up call for whatever breaks them, then a hard trim."""
    broken = {p: pieces[p] for p in pieces if problems(p, pieces[p])}
    fixed = 0
    if broken:
        issues = [x for p in broken for x in problems(p, broken[p])]
        try:
            raw_fix, _ = await ask_json(
                "shorten",
                models(settings.writer_models),
                prompts.SHORTEN,
                "Problems:\n" + "\n".join(f"- {x}" for x in issues) + f"\n\nPieces:\n{prompts.dump(broken)}",
                usage,
                max_tokens=1500,
                temperature=0.3,
            )
            for p in broken:
                if isinstance(raw_fix.get(p), dict):
                    candidate = clean_piece(p, {**pieces[p], **raw_fix[p]})
                    candidate.update({k: v for k, v in pieces[p].items() if k == "addresses"})
                    if len(problems(p, candidate)) < len(problems(p, pieces[p])):
                        pieces = {**pieces, p: candidate}
                        fixed += 1
        except ProviderError:
            pass
    # Whatever the model couldn't fix, code enforces.
    return {p: {**fit(p, v), **({"addresses": v["addresses"]} if "addresses" in v else {})} for p, v in pieces.items()}, fixed


async def write_drafts(brief: dict, market: dict | None, page: Page, buyers: list[dict], usage: Usage) -> tuple[dict, int]:
    raw, _ = await ask_json(
        "drafts", models(settings.writer_models), prompts.DRAFTS, _context(brief, market, page, buyers), usage, max_tokens=3500, temperature=0.8
    )
    return await enforce(clean(raw), usage)


# ---------- 5. the panel reacts ----------


def clean_reactions(raw: dict, pieces: list[str]) -> list[dict]:
    rows = raw.get("reactions") if isinstance(raw.get("reactions"), list) else []
    by_piece = {}
    for r in rows:
        if isinstance(r, dict) and r.get("piece") in pieces and r["piece"] not in by_piece:
            by_piece[r["piece"]] = r
    out = []
    for p in pieces:
        r = by_piece.get(p)
        if not r:
            continue
        click = r.get("click")
        if isinstance(click, str):
            click = click.strip().lower() in ("true", "yes")
        out.append(
            {
                "piece": p,
                "click": bool(click),
                "score": int(round(_clamp(r.get("score"), 1, 10, 5))),
                "objection": _s(r.get("objection"), 240),
                "reason": _s(r.get("reason"), 120),
            }
        )
    return out


async def react(buyer: dict, brief: dict, pieces: dict[str, dict], usage: Usage) -> list[dict]:
    specs = models(settings.buyer_models)
    # The buyer's own model first; the others are fallbacks when it's rate limited.
    specs.sort(key=lambda s: s.id != buyer.get("model"))
    out: list[dict] = []
    todo = dict(pieces)
    # Models sometimes stop after a few pieces; ask once more for the ones they skipped.
    for _ in range(2):
        shown = "\n\n".join(f"Piece id: {p}\n{as_text(p, piece)}" for p, piece in todo.items())
        raw, _ = await ask_json(
            "buyer", specs, prompts.buyer_system(buyer, brief["product"]), shown, usage, max_tokens=2000, temperature=0.7
        )
        out += clean_reactions(raw, list(todo))
        done = {r["piece"] for r in out}
        todo = {p: v for p, v in pieces.items() if p not in done}
        if not todo:
            break
    return sorted(out, key=lambda r: list(pieces).index(r["piece"]))


async def panel_round(round: int, buyers: list[dict], brief: dict, pieces: dict[str, dict], usage: Usage) -> AsyncIterator[dict]:
    async def one(b: dict):
        try:
            return b, await react(b, brief, pieces, usage), None
        except ProviderError as e:
            print(f"buyer {b['id']} failed: {e}")
            return b, [], "Couldn't answer this time (model busy)"

    for next_done in asyncio.as_completed([one(b) for b in buyers]):
        b, reactions, error = await next_done
        yield {"type": "reaction", "round": round, "buyer": b["id"], "value": reactions, "error": error}


def score(reactions: dict[str, list[dict]], pieces: list[str]) -> dict[str, dict]:
    out = {}
    for p in pieces:
        rows = [r for rs in reactions.values() for r in rs if r["piece"] == p]
        if rows:
            scores = [r["score"] for r in rows]
            out[p] = {
                "avg": round(sum(scores) / len(scores), 1),
                "clicks": sum(r["click"] for r in rows),
                "n": len(rows),
                "spread": round(statistics.pstdev(scores), 2),
            }
    return out


# ---------- 6. rewrites ----------


async def rewrite(
    low: list[str], brief: dict, market: dict | None, page: Page, drafts: dict, reactions: dict, buyers: list[dict], usage: Usage
) -> dict:
    who = {b["id"]: b for b in buyers}
    parts = []
    for p in low:
        rows = sorted(
            ((who[bid], r) for bid, rs in reactions.items() for r in rs if r["piece"] == p), key=lambda x: x[1]["score"]
        )
        said = [
            f"- {b['name']} ({b['role']}): {r['score']}/10, {'would click' if r['click'] else 'no click'}. \"{r['objection']}\""
            for b, r in rows
        ]
        parts.append(f"## {p} ({LABELS[p]})\nCurrent version:\n{prompts.dump(drafts[p])}\nWhat the panel said, lowest score first:\n" + "\n".join(said))
    raw, _ = await ask_json(
        "rewrite",
        models(settings.writer_models),
        prompts.REWRITE,
        _context(brief, market, page) + "\n\n# PIECES TO FIX\n\n" + "\n\n".join(parts),
        usage,
        max_tokens=3500,
        temperature=0.7,
    )
    rows = raw.get("rewrites") if isinstance(raw.get("rewrites"), dict) else {}
    out = {}
    for p in low:
        if isinstance(rows.get(p), dict):
            piece = clean_piece(p, {**drafts[p], **rows[p]})
            piece["addresses"] = _s(rows[p].get("addresses"), 160)
            out[p] = piece
    fixed, _ = await enforce(out, usage)
    return fixed


# ---------- the whole run ----------


async def run_agent(url: str | None, text: str | None) -> AsyncIterator[dict]:
    usage = Usage()
    started = time.monotonic()
    async for e in _steps(url, text, usage):
        yield e
    yield {
        "type": "done",
        "calls": usage.calls,
        "tokens": usage.tokens,
        "seconds": round(time.monotonic() - started, 1),
        "models": usage.models,
    }


async def _steps(url: str | None, text: str | None, usage: Usage) -> AsyncIterator[dict]:
    writer = models(settings.writer_models)
    if not writer:
        yield {"type": "error", "message": "No model is configured on the server."}
        return

    try:
        # 1. Read the page.
        yield step("read", "running", "Reading the page", url or "Pasted text")
        try:
            page = from_text(text) if text else await read_page(url or "")
        except PageError as e:
            yield step("read", "error", "Couldn't read the page", str(e))
            yield {"type": "error", "message": str(e), "paste": True}
            return
        yield {
            "type": "page",
            "value": {"url": page.url, "domain": page.domain, "title": page.title, "description": page.description, "image": page.image},
        }
        yield step("read", "done", "Read the page", f"{len(page.text):,} characters, {len(page.headings)} headings")

        yield step("brief", "running", "Working out the audience, offer and proof")
        raw, spec = await ask_json("brief", writer, prompts.BRIEF, page.for_prompt(), usage, max_tokens=900, temperature=0.3)
        brief = clean_brief(raw, page)
        yield {"type": "brief", "value": brief}
        yield step("brief", "done", "Worked out the brief", f"{brief['product']}: {brief['category']}")

        # 2. The market.
        market = None
        async for e in market_steps(page, brief, usage):
            if e["type"] == "market":
                market = e["value"]
            yield e

        # 3. The panel.
        yield step("panel", "running", "Building the buyer panel")
        raw, _ = await ask_json(
            "panel",
            writer,
            prompts.PANEL,
            f"# PRODUCT BRIEF\n{prompts.dump(brief)}\n\nCompetitors: "
            + (", ".join(c["name"] for c in market["competitors"]) if market else "unknown"),
            usage,
            max_tokens=1200,
            temperature=0.9,
        )
        buyers = clean_panel(raw)
        if len(buyers) < 3:
            raise ProviderError("the panel came back too small")
        yield {"type": "panel", "value": buyers}
        yield step("panel", "done", "Built the buyer panel", ", ".join(b["name"] for b in buyers))

        # 4. Drafts.
        yield step("drafts", "running", "Writing 3 ads, a landing hero and 3 emails")
        drafts, fixed = await write_drafts(brief, market, page, buyers, usage)
        yield {"type": "drafts", "value": drafts}
        yield step("drafts", "done", "Wrote the drafts", f"Length limits checked in code{f', {fixed} fixed' if fixed else ''}")

        # 5. Round 1.
        yield step("react", "running", "Showing every piece to the panel")
        reactions: dict[str, list[dict]] = {}
        async for e in panel_round(1, buyers, brief, drafts, usage):
            reactions[e["buyer"]] = e["value"]
            yield e
        scores = score(reactions, PIECE_IDS)
        yield {"type": "scores", "round": 1, "value": scores}
        if not scores:
            raise ProviderError("no buyer could answer")
        low = [p for p in PIECE_IDS if p in scores and scores[p]["avg"] < settings.bar]
        spreads = [s["spread"] for s in scores.values()]
        if spreads and statistics.mean(spreads) < 0.6:
            yield {"type": "warning", "message": "The buyers agreed on almost everything, so treat these scores with suspicion."}
        yield step(
            "react",
            "done",
            "The panel reacted",
            f"{len(low)} of {len(scores)} pieces below {settings.bar:g}" if low else "Every piece cleared the bar",
        )

        # 6. Rewrite what fell below the bar, then test it again.
        if low:
            yield step("rewrite", "running", f"Rewriting {len(low)} pieces to answer the objections", ", ".join(LABELS[p] for p in low))
            rewrites = await rewrite(low, brief, market, page, drafts, reactions, buyers, usage)
            yield {"type": "rewrites", "value": rewrites}
            yield step("rewrite", "done", "Rewrote the weak pieces", ", ".join(LABELS[p] for p in rewrites))
            if rewrites:
                yield step("rescore", "running", "Scoring the rewrites again")
                again: dict[str, list[dict]] = {}
                async for e in panel_round(2, buyers, brief, rewrites, usage):
                    again[e["buyer"]] = e["value"]
                    yield e
                after = score(again, list(rewrites))
                yield {"type": "scores", "round": 2, "value": after}
                better = sum(1 for p in after if after[p]["avg"] > scores[p]["avg"])
                yield step("rescore", "done", "Scored the rewrites", f"{better} of {len(after)} improved")
    except ProviderError as e:
        print(f"run failed: {e}")
        yield {"type": "error", "message": "The models are busy or out of free quota right now. Try again in a few minutes."}


async def rescore(brief: dict, buyers: list[dict], piece_id: str, piece: dict) -> dict:
    """The panel's reaction to one edited piece."""
    usage = Usage()
    clean_ = clean_piece(piece_id, piece)
    reactions: dict[str, list[dict]] = {}
    async for e in panel_round(3, buyers, brief, {piece_id: clean_}, usage):
        reactions[e["buyer"]] = e["value"]
    return {"reactions": reactions, "score": score(reactions, [piece_id]).get(piece_id), "problems": problems(piece_id, clean_)}


__all__ = ["run_agent", "rescore", "kind"]
