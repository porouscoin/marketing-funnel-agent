"""Web search through Tavily, used to find a product's competitors."""

from .config import settings
from .providers import http


class SearchError(Exception):
    pass


async def search(query: str, max_results: int = 6) -> list[dict]:
    """Results as [{title, url, snippet}]."""
    if not settings.tavily_key:
        raise SearchError("Search isn't set up on this server.")
    try:
        resp = await http().post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": max_results, "search_depth": "basic"},
            headers={"Authorization": f"Bearer {settings.tavily_key}"},
            timeout=20,
        )
    except Exception as e:
        raise SearchError(f"Search failed ({type(e).__name__}).")
    if resp.status_code != 200:
        raise SearchError(f"Search failed (HTTP {resp.status_code}).")
    rows = resp.json().get("results") or []
    return [
        {"title": r.get("title", "")[:200], "url": r.get("url", ""), "snippet": (r.get("content") or "")[:400]}
        for r in rows
        if r.get("url", "").startswith("http")
    ]
