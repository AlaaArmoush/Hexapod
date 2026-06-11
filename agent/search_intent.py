from __future__ import annotations

_SEARCH_TRIGGERS = (
    "search for",
    "find the",
    "find my",
    "find a",
    "look for",
    "where is",
    "where's the",
    "locate",
)


def match_search_intent(text: str) -> str | None:
    """Return the target label if text is a search request, else None."""
    t = text.lower().strip()
    for trigger in _SEARCH_TRIGGERS:
        if trigger in t:
            target = t[t.index(trigger) + len(trigger):].strip().rstrip(".")
            if target:
                return target
    return None
