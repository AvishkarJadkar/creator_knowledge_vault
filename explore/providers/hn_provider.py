"""Hacker News provider.

Reddit now blocks unauthenticated requests from most server IPs, which used to
leave Explore with no results at all. Hacker News' public Algolia API needs no
credentials, so it doubles as a reliable fallback source.
"""

import html
import logging
import re
from urllib.parse import urlparse

import requests

from . import BaseProvider, register_provider

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={}"

_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(value: str) -> str:
    """Strip the HTML that HN returns in story/comment text."""
    if not value:
        return ""
    return html.unescape(_TAG_RE.sub(" ", value)).strip()


def _safe_url(value, fallback):
    """Only allow http(s) links; HN submissions can point anywhere."""
    try:
        parsed = urlparse(value or "")
    except (ValueError, AttributeError):
        return fallback
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return value
    return fallback


@register_provider
class HackerNewsProvider(BaseProvider):
    @property
    def name(self):
        return "hackernews"

    @property
    def display_name(self):
        return "Hacker News"

    @property
    def icon(self):
        return "newspaper"

    def search(self, keyword: str, limit: int = 5) -> list[dict]:
        try:
            response = requests.get(
                HN_SEARCH_URL,
                params={"query": keyword, "tags": "story", "hitsPerPage": limit},
                timeout=10,
            )
            response.raise_for_status()
            hits = response.json().get("hits", [])
        except Exception as e:
            logging.error(f"HackerNewsProvider search error: {e}")
            return []

        results = []
        for hit in hits:
            title = hit.get("title") or hit.get("story_title") or "Hacker News story"
            object_id = hit.get("objectID", "")
            url = _safe_url(hit.get("url"), HN_ITEM_URL.format(object_id))
            body = _plain_text(hit.get("story_text") or "")
            points = hit.get("points") or 0
            num_comments = hit.get("num_comments") or 0

            if body:
                summary = body[:400] + "..." if len(body) > 400 else body
            else:
                summary = f"{num_comments} comments · {points} points on Hacker News"

            results.append({
                "title": title,
                "url": url,
                "source": "Hacker News",
                "score": points,
                "created_utc": hit.get("created_at_i"),
                "thumbnail": None,
                "summary": summary,
                "comments": [],
                "raw_text": f"Title: {title}\nBody: {body[:1000]}",
            })

        return results
