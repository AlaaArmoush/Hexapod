import os

from .base import ToolResult

_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_NEWS_KEYWORDS = (
    "news", "latest", "today", "current", "war", "politics",
    "iran", "russia", "ukraine", "china", "israel", "gaza",
    "trump", "biden", "election", "economy", "climate",
)


def _load_env() -> None:
    """Load .env from repo root if present (no external dependency needed)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _failure(error: str, spoken_text: str, query: str = "") -> ToolResult:
    return ToolResult(
        ok=False,
        action="search_web",
        spoken_text=spoken_text,
        data={"query": query, "results": []},
        display_face="search",
        error=error,
    )


def _newsapi_search(query: str, api_key: str) -> list[dict]:
    import requests
    resp = requests.get(
        _NEWSAPI_URL,
        params={
            "q": query,
            "apiKey": api_key,
            "pageSize": 3,
            "sortBy": "publishedAt",
            "language": "en",
        },
        timeout=8,
    )
    resp.raise_for_status()
    data = resp.json()
    articles = data.get("articles", [])
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "snippet": a.get("description") or a.get("title", ""),
            "source": a.get("source", {}).get("name", ""),
            "date": (a.get("publishedAt") or "")[:10],
        }
        for a in articles
        if a.get("title") and "[Removed]" not in a.get("title", "")
    ]


def _ddg_search(query: str, news: bool = False) -> list[dict]:
    from ddgs import DDGS
    with DDGS() as ddgs:
        if news:
            raw = list(ddgs.news(query, max_results=5, timelimit="w"))
            return [
                {
                    "title": h.get("title", ""),
                    "url": h.get("url", h.get("href", "")),
                    "snippet": h.get("body") or h.get("title", ""),
                    "source": h.get("source", ""),
                    "date": (h.get("date") or "")[:10],
                }
                for h in raw if h.get("title")
            ]
        raw = list(ddgs.text(query, max_results=5))
        return [
            {"title": h.get("title", ""), "url": h.get("href", ""),
             "snippet": h.get("body", ""), "source": "", "date": ""}
            for h in raw
            if len(h.get("body", "")) > 80
        ]


def search_web(query: str) -> ToolResult:
    query = (query or "").strip()
    if not query:
        return _failure("invalid_query", "I need a search query for that.", query)

    _load_env()
    api_key = os.environ.get("NEWS_API_KEY", "")
    is_news = any(kw in query.lower() for kw in _NEWS_KEYWORDS)

    hits: list[dict] = []
    try:
        if is_news and api_key:
            hits = _newsapi_search(query, api_key)
        if not hits:
            try:
                hits = _ddg_search(query, news=is_news)
            except Exception:
                hits = _ddg_search(query, news=False)
    except Exception:
        return _failure("network_error", "I could not reach web search right now.", query)

    if not hits:
        return ToolResult(
            ok=True,
            action="search_web",
            spoken_text="I couldn't find anything for that.",
            data={"query": query, "results": []},
            display_face="search",
        )

    headlines = " / ".join(h["title"] for h in hits[:3] if h.get("title"))
    spoken_text = headlines or hits[0]["snippet"] or hits[0]["title"]

    return ToolResult(
        ok=True,
        action="search_web",
        spoken_text=spoken_text,
        data={"query": query, "results": hits},
        display_face="search",
    )
