"""The seven pieces of copy, their fields and their length limits.

Limits are enforced here in code, never left to the model: a Google headline
over 30 characters is rejected by Google, so it can't be shown as if it would run.
Google's limits are hard ones. The Meta and LinkedIn limits are where the text
gets cut off in the feed, so going over them wastes the words that matter.
"""

import re
from typing import Any

PIECES: list[tuple[str, str]] = [
    ("meta", "Meta feed ad"),
    ("google", "Google search ad"),
    ("linkedin", "LinkedIn ad"),
    ("hero", "Landing page hero"),
    ("email1", "Email 1"),
    ("email2", "Email 2"),
    ("email3", "Email 3"),
]
PIECE_IDS = [p for p, _ in PIECES]
LABELS = dict(PIECES)

META_CTAS = ["Learn more", "Sign up", "Shop now", "Book now", "Get offer", "Get quote", "Contact us", "Subscribe", "Download"]
LINKEDIN_CTAS = ["Learn more", "Sign up", "Request demo", "Register", "Download", "Try now", "Subscribe", "Join"]

# piece kind -> field -> limit. A (limit, count) tuple means a list of that many strings.
LIMITS: dict[str, dict[str, Any]] = {
    "meta": {"primary": 125, "headline": 40},
    "google": {"headlines": (30, 3), "descriptions": (90, 2)},
    "linkedin": {"intro": 150, "headline": 70},
    "hero": {"headline": 70, "subline": 160, "cta": 24, "proof": 110},
    "email": {"subject": 60, "preview": 90, "body": 900},
}


def kind(piece_id: str) -> str:
    return "email" if piece_id.startswith("email") else piece_id


def spec_text() -> str:
    """The format rules, written out for the prompt."""
    return "\n".join(
        [
            f'- meta: {{"angle", "primary" (max 125 chars), "headline" (max 40), "cta" (one of: {", ".join(META_CTAS)})}}',
            '- google: {"angle", "headlines" (exactly 3, each max 30 chars), "descriptions" (exactly 2, each max 90)}',
            f'- linkedin: {{"angle", "intro" (max 150), "headline" (max 70), "cta" (one of: {", ".join(LINKEDIN_CTAS)})}}',
            '- hero: {"angle", "headline" (max 70), "subline" (max 160), "cta" (button text, max 24), "proof" (one line, max 110)}',
            '- email1, email2, email3: {"angle", "subject" (max 60), "preview" (max 90), "body" (max 900, plain text, short paragraphs)}',
        ]
    )


def _s(v: Any) -> str:
    return re.sub(r"[ \t]+", " ", str(v or "")).strip()


def _pick(value: Any, options: list[str]) -> str:
    v = _s(value).lower()
    for o in options:
        if o.lower() == v:
            return o
    return options[0]


def clean_piece(piece_id: str, raw: Any) -> dict:
    """Every expected field present, as a string (or list of strings), CTAs from the allowed list."""
    raw = raw if isinstance(raw, dict) else {}
    k = kind(piece_id)
    out: dict[str, Any] = {"angle": _s(raw.get("angle"))[:120]}
    for field, limit in LIMITS[k].items():
        if isinstance(limit, tuple):
            items = raw.get(field)
            items = [_s(x) for x in items] if isinstance(items, list) else []
            items = [x for x in items if x][: limit[1]]
            out[field] = items + [""] * (limit[1] - len(items))
        elif field == "body":
            out[field] = "\n\n".join(_s(p) for p in re.split(r"\n\s*\n", str(raw.get(field) or "")) if _s(p))
        else:
            out[field] = _s(raw.get(field))
    if k == "meta":
        out["cta"] = _pick(raw.get("cta"), META_CTAS)
    if k == "linkedin":
        out["cta"] = _pick(raw.get("cta"), LINKEDIN_CTAS)
    return out


def clean(drafts: Any) -> dict[str, dict]:
    drafts = drafts if isinstance(drafts, dict) else {}
    return {p: clean_piece(p, drafts.get(p)) for p in PIECE_IDS}


def problems(piece_id: str, piece: dict) -> list[str]:
    """What's wrong with a piece, as short sentences the model can fix."""
    out = []
    for field, limit in LIMITS[kind(piece_id)].items():
        if isinstance(limit, tuple):
            for i, item in enumerate(piece.get(field, [])):
                if not item:
                    out.append(f"{piece_id}.{field}[{i}] is empty")
                elif len(item) > limit[0]:
                    out.append(f'{piece_id}.{field}[{i}] is {len(item)} chars, max {limit[0]}: "{item}"')
        else:
            v = piece.get(field, "")
            if not v:
                out.append(f"{piece_id}.{field} is empty")
            elif len(v) > limit:
                out.append(f'{piece_id}.{field} is {len(v)} chars, max {limit}: "{v[:200]}"')
    return out


def trim(text: str, limit: int) -> str:
    """Cut at a sentence end if one is close enough, else at a word, so nothing ends mid-word."""
    if len(text) <= limit:
        return text
    sentence = max(text.rfind(". ", 0, limit), text.rfind("? ", 0, limit))
    if sentence >= limit * 0.5:
        return text[: sentence + 1]
    cut = text[: limit + 1].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut[:limit].rstrip(" ,;:-–—")


def fit(piece_id: str, piece: dict) -> dict:
    """The last resort after the model had a go: hard limits, enforced."""
    out = dict(piece)
    for field, limit in LIMITS[kind(piece_id)].items():
        if isinstance(limit, tuple):
            out[field] = [trim(x, limit[0]) for x in piece.get(field, [])]
        else:
            out[field] = trim(piece.get(field, ""), limit)
    return out


def as_text(piece_id: str, piece: dict) -> str:
    """How a buyer 'sees' a piece: the words in the order they'd meet them."""
    k = kind(piece_id)
    if k == "meta":
        return f"[{LABELS[piece_id]}]\n{piece['primary']}\nHeadline: {piece['headline']}\nButton: {piece['cta']}"
    if k == "google":
        return f"[{LABELS[piece_id]}]\n{' | '.join(piece['headlines'])}\n{' '.join(piece['descriptions'])}"
    if k == "linkedin":
        return f"[{LABELS[piece_id]}]\n{piece['intro']}\nHeadline: {piece['headline']}\nButton: {piece['cta']}"
    if k == "hero":
        return f"[{LABELS[piece_id]}]\n{piece['headline']}\n{piece['subline']}\nButton: {piece['cta']}\n{piece['proof']}"
    return f"[{LABELS[piece_id]}]\nSubject: {piece['subject']}\nPreview: {piece['preview']}\n\n{piece['body']}"
