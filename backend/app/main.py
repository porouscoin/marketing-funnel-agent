"""HTTP API: start a run (streamed), re-score an edited piece."""

import json
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent import REG, rescore, run_agent
from .config import settings
from .formats import PIECE_IDS

app = FastAPI(title="Marketing funnel agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_origin_regex=settings.frontend_origin_regex or None,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

HOUR, DAY = 3600, 86400

# In-memory limits. Each server instance keeps its own, which is enough to stop
# one visitor from draining the free model quotas; the providers' own caps are the backstop.
_hits: dict[str, deque] = defaultdict(deque)


def ip_of(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def allow(key: str, limit: int, window: int) -> bool:
    now = time.time()
    q = _hits[key]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/config")
async def config():
    return {
        "models": [s.label for s in REG.values()],
        "search": bool(settings.tavily_key),
        "bar": settings.bar,
        "runs_per_day": settings.runs_per_day,
    }


class RunIn(BaseModel):
    url: str | None = Field(default=None, max_length=500)
    text: str | None = Field(default=None, max_length=20000)


@app.post("/api/run")
async def run(body: RunIn, request: Request):
    url = (body.url or "").strip()
    text = (body.text or "").strip()[: settings.max_text_chars]
    if not url and len(text) < 200:
        raise HTTPException(400, "Paste a product page URL, or at least a few paragraphs of its text.")
    if not allow("run:" + ip_of(request), settings.runs_per_day, DAY):
        raise HTTPException(429, f"That's {settings.runs_per_day} runs today, the limit for one visitor. Come back tomorrow.")
    if not allow("run:all", settings.runs_per_day_global, DAY):
        raise HTTPException(429, "The agent has done all its runs for today. It's resting until tomorrow.")

    async def stream():
        try:
            async for event in run_agent(url or None, text or None):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:  # never leave the browser hanging
            print(f"run crashed: {e!r}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something broke on our side. Try again.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


class Buyer(BaseModel):
    id: str = Field(max_length=8)
    name: str = Field(max_length=40)
    role: str = Field(max_length=120)
    cares: str = Field(max_length=160)
    uses_today: str = Field(max_length=120)
    doubt: str = Field(max_length=180)
    style: str = Field(max_length=120)
    model: str = Field(default="", max_length=40)


class RescoreIn(BaseModel):
    product: str = Field(max_length=80)
    buyers: list[Buyer] = Field(max_length=5, min_length=1)
    piece_id: str
    piece: dict


@app.post("/api/rescore")
async def rescore_piece(body: RescoreIn, request: Request):
    if body.piece_id not in PIECE_IDS:
        raise HTTPException(400, "Unknown piece.")
    if len(json.dumps(body.piece)) > 4000:
        raise HTTPException(400, "That piece is too long.")
    if not allow("rescore:" + ip_of(request), settings.rescores_per_hour, HOUR):
        raise HTTPException(429, "That's a lot of re-scores. Give the panel a few minutes.")
    return await rescore({"product": body.product}, [b.model_dump() for b in body.buyers], body.piece_id, body.piece)
