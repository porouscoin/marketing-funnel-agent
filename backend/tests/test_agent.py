from fastapi.testclient import TestClient

from app.agent import rescore, run_agent
from app.formats import PIECE_IDS
from app.main import app

TEXT = "Inboxly: cold email for founders\n" + "Warm up your domain and send at safe limits so cold email reaches the inbox. " * 5


async def collect():
    return [e async for e in run_agent(None, TEXT)]


async def test_full_run_with_mock_model():
    events = await collect()
    types = [e["type"] for e in events]
    assert types[-1] == "done" and "error" not in types
    for t in ("page", "brief", "market", "panel", "drafts", "reaction", "scores", "rewrites"):
        assert t in types, t
    drafts = next(e for e in events if e["type"] == "drafts")["value"]
    assert set(drafts) == set(PIECE_IDS)
    assert all(len(h) <= 30 for h in drafts["google"]["headlines"])
    panel = next(e for e in events if e["type"] == "panel")["value"]
    assert len(panel) == 5
    round1 = [e for e in events if e["type"] == "reaction" and e["round"] == 1]
    assert len(round1) == 5 and all(len(e["value"]) == 7 for e in round1)
    market = next(e for e in events if e["type"] == "market")["value"]
    assert market["gap"]["verified"]  # the mock quotes the page
    # Every step that started also finished.
    steps = [e for e in events if e["type"] == "step"]
    running = {e["id"] for e in steps if e["status"] == "running"}
    ended = {e["id"] for e in steps if e["status"] != "running"}
    assert running <= ended


async def test_rescore_one_piece():
    events = await collect()
    panel = next(e for e in events if e["type"] == "panel")["value"]
    out = await rescore({"product": "Inboxly"}, panel, "hero", {"headline": "x" * 80, "subline": "s", "cta": "Go", "proof": "p"})
    assert out["score"]["n"] == 5
    assert any("max 70" in p for p in out["problems"])


def test_api_streams_and_limits():
    c = TestClient(app)
    assert c.post("/api/run", json={"text": "too short"}).status_code == 400
    r = c.post("/api/run", json={"text": TEXT})
    assert r.status_code == 200 and '"type": "done"' in r.text
