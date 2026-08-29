"""Web search for chat: Brave Search API with a scraping fallback.

Brave is the primary provider (set ``BRAVE_SEARCH_API_KEY``). When the key is
missing or Brave fails, fall back to ``ddgs`` engine scraping, which is
unreliable from datacenter IPs such as Railway's but better than nothing.
Every result is normalized to ``{"title", "href", "body"}``.
"""

import os
import re

import requests

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
BRAVE_TIMEOUT = 10
# Brave rejects queries over 400 characters or 50 words.
QUERY_MAX_CHARS = 400
QUERY_MAX_WORDS = 50

# Markers left by the prompt rewrites in main.py that wrap the user's text
# with fetched page content or RAG context. Search must use the user's own
# words, not the wrapped prompt.
_WRAPPER_MARKERS = ("User message:", "User question:", "Original Query:")


def user_query_from_prompt(content) -> str:
    """Recover the user's own text from a prompt that may have been wrapped."""
    if not isinstance(content, str):
        return ""
    text = content
    for marker in _WRAPPER_MARKERS:
        index = text.rfind(marker)
        if index != -1:
            text = text[index + len(marker):]
    return text.strip()


def clean_search_query(query: str) -> str:
    """Collapse whitespace and cap the query to Brave's limits."""
    words = re.sub(r"\s+", " ", query or "").strip().split(" ")
    words = [word for word in words if word][:QUERY_MAX_WORDS]
    return " ".join(words)[:QUERY_MAX_CHARS].strip()


def parse_brave_results(payload: dict, max_results: int) -> list:
    results = []
    for item in (payload.get("web") or {}).get("results") or []:
        title = item.get("title") or ""
        body = item.get("description") or ""
        href = item.get("url") or ""
        if not (title or body):
            continue
        results.append({"title": title, "href": href, "body": body})
        if len(results) >= max_results:
            break
    return results


def brave_search(query: str, max_results: int, api_key: str) -> list:
    response = requests.get(
        BRAVE_ENDPOINT,
        params={"q": query, "count": min(max(max_results, 1), 20)},
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
        timeout=BRAVE_TIMEOUT,
    )
    response.raise_for_status()
    return parse_brave_results(response.json(), max_results)


def ddgs_search(query: str, max_results: int) -> list:
    from ddgs import DDGS

    last_err = None
    for backend in ("auto", "google, bing, brave, mojeek, yahoo, duckduckgo"):
        try:
            results = list(DDGS().text(query, max_results=max_results, backend=backend))
            if results:
                return [
                    {
                        "title": item.get("title", ""),
                        "href": item.get("href", ""),
                        "body": item.get("body", ""),
                    }
                    for item in results
                ]
        except Exception as e:  # noqa: BLE001 - engine errors vary widely
            last_err = e
            print(f"web_search ddgs backend='{backend}' failed: {type(e).__name__}: {e}")
    if last_err:
        print(f"web_search ddgs exhausted all backends: {type(last_err).__name__}: {last_err}")
    return []


def web_search(query: str, max_results: int = 5) -> list:
    """Search the web for ``query``. Returns [] if every provider fails."""
    cleaned = clean_search_query(user_query_from_prompt(query))
    if not cleaned:
        return []
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if api_key:
        try:
            results = brave_search(cleaned, max_results, api_key)
            if results:
                return results
            print("web_search brave returned no results; falling back to ddgs")
        except Exception as e:  # noqa: BLE001
            print(f"web_search brave failed: {type(e).__name__}: {e}; falling back to ddgs")
    else:
        print("web_search: BRAVE_SEARCH_API_KEY not set; using ddgs scraping fallback")
    return ddgs_search(cleaned, max_results)
