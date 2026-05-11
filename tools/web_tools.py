from typing import Any, Dict, List

from .base import ToolResult


DDG_INSTANT_ANSWER_URL = "https://api.duckduckgo.com/"


def _failure(error: str, spoken_text: str, query: str = "") -> ToolResult:
    return ToolResult(
        ok=False,
        action="search_web",
        spoken_text=spoken_text,
        data={"query": query, "results": []},
        display_face="search",
        error=error,
    )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_results(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    results = []

    abstract = _clean_text(payload.get("AbstractText"))
    abstract_url = _clean_text(payload.get("AbstractURL"))
    heading = _clean_text(payload.get("Heading")) or "DuckDuckGo result"
    if abstract:
        results.append({"title": heading, "url": abstract_url, "snippet": abstract})

    for topic in payload.get("RelatedTopics", []):
        if len(results) >= 5:
            break

        if isinstance(topic, dict) and "Topics" in topic:
            nested_topics = topic.get("Topics") or []
        else:
            nested_topics = [topic]

        for item in nested_topics:
            if len(results) >= 5:
                break
            if not isinstance(item, dict):
                continue

            text = _clean_text(item.get("Text"))
            first_url = _clean_text(item.get("FirstURL"))
            if not text:
                continue

            title = text.split(" - ", 1)[0][:80]
            results.append({"title": title, "url": first_url, "snippet": text})

    return results[:5]


def search_web(query: str) -> ToolResult:
    query = _clean_text(query)
    if not query:
        return _failure("invalid_query", "I need a search query for that.", query)

    try:
        import requests
    except ImportError:
        return _failure("network_unavailable", "Web search is not available because requests is not installed.", query)

    try:
        response = requests.get(
            DDG_INSTANT_ANSWER_URL,
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException:
        return _failure("network_unavailable", "I could not reach web search right now.", query)

    try:
        payload = response.json()
    except ValueError:
        return _failure("parse_error", "I could not understand the search response.", query)

    if not isinstance(payload, dict):
        return _failure("parse_error", "I could not understand the search response.", query)

    results = _extract_results(payload)
    if not results:
        return ToolResult(
            ok=True,
            action="search_web",
            spoken_text="I couldn't find anything for that.",
            data={"query": query, "results": []},
            display_face="search",
        )

    top = results[0]
    spoken_text = top["snippet"] or top["title"]
    return ToolResult(
        ok=True,
        action="search_web",
        spoken_text=spoken_text,
        data={"query": query, "results": results},
        display_face="search",
    )
