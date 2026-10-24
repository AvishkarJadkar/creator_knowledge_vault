import logging
import os
import random
import threading
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, List, Optional
import re

# Mocking the agents.py functionality for self-containment
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
]

def get_agent():
    return random.choice(USER_AGENTS)


# ─────────────────────────────────────────────────────────────
# OAUTH (application-only)
# Reddit blocks unauthenticated JSON requests from most server IPs
# (HTTP 403), so production deployments should set REDDIT_CLIENT_ID
# and REDDIT_CLIENT_SECRET from https://www.reddit.com/prefs/apps
# ─────────────────────────────────────────────────────────────
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_oauth_lock = threading.Lock()
_oauth_cache = {"token": None, "expires_at": 0.0}


def get_oauth_token() -> Optional[str]:
    """Return a cached Reddit OAuth token, or None when not configured."""
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    with _oauth_lock:
        now = time.time()
        if _oauth_cache["token"] and now < _oauth_cache["expires_at"] - 60:
            return _oauth_cache["token"]

        try:
            resp = requests.post(
                REDDIT_TOKEN_URL,
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": get_agent()},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if not token:
                logging.error("Reddit OAuth: no access_token in response")
                return None
            _oauth_cache["token"] = token
            _oauth_cache["expires_at"] = now + int(data.get("expires_in", 3600))
            return token
        except Exception as e:
            logging.error(f"Reddit OAuth error: {e}")
            return None


class RandomUserAgentSession(requests.Session):
    def request(self, *args, **kwargs):
        self.headers.update({"User-Agent": get_agent()})
        return super().request(*args, **kwargs)


class RedditScraper:
    def __init__(self, timeout: int = 10):
        self.session = RandomUserAgentSession()
        self.timeout = timeout

        # Keep retries short: a blocked request should fail fast instead of
        # hanging an Explore request for a minute.
        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def get(self, path: str, params: Optional[Dict[str, Any]] = None):
        """GET a Reddit API path, using OAuth when credentials are configured.

        Falls back to the public JSON endpoints (which may be blocked with a
        403 on datacenter IPs — callers must handle that).
        """
        token = get_oauth_token()
        if token:
            return self.session.get(
                f"https://oauth.reddit.com{path}",
                params=params,
                headers={"Authorization": f"bearer {token}"},
                timeout=self.timeout,
            )

        # Public reddit.com endpoints need an explicit `.json` suffix —
        # otherwise they return an HTML page and response.json() fails.
        if not path.endswith(".json"):
            path = f"{path}.json"

        return self.session.get(
            f"https://www.reddit.com{path}",
            params=params,
            timeout=self.timeout,
        )

    def search_posts(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Reddit and return the raw post data dicts."""
        params = {
            "q": keyword,
            "sort": "relevance",
            "limit": limit,
            "type": "link",
            "raw_json": 1,
        }
        response = self.get("/search", params=params)
        response.raise_for_status()
        payload = response.json()
        children = payload.get("data", {}).get("children", [])
        return [child.get("data", {}) for child in children if child.get("kind") == "t3"]

    def fetch_post_comments(self, permalink: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch the top-level comments for a post."""
        response = self.get(f"{permalink}.json", params={"raw_json": 1, "limit": limit})
        response.raise_for_status()
        post_data = response.json()
        if not isinstance(post_data, list) or len(post_data) < 2:
            return []
        return self._extract_comments(post_data[1]["data"]["children"][:limit])

    def fetch_subreddit_posts(
        self, subreddit: str, limit: int = 10, category: str = "hot"
    ) -> List[Dict[str, Any]]:
        params = {"limit": min(100, limit), "raw_json": 1}
        
        try:
            response = self.get(f"/r/{subreddit}/{category}.json", params=params)
            response.raise_for_status()
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            results = []
            for post in posts:
                post_data = post["data"]
                results.append({
                    "title": post_data["title"],
                    "permalink": post_data["permalink"],
                    "url": f"https://www.reddit.com{post_data['permalink']}",
                    "created_utc": post_data["created_utc"],
                })
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logging.error(f"Error fetching Reddit posts for {subreddit}: {e}")
            return []

    def scrape_post_details(self, permalink: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.get(f"{permalink}.json", params={"raw_json": 1})
            response.raise_for_status()
            post_data = response.json()
            
            if not isinstance(post_data, list) or len(post_data) < 2:
                return None

            main_post = post_data[0]["data"]["children"][0]["data"]
            title = main_post["title"]
            body = main_post.get("selftext", "")

            # Flatten top 5 comments
            comments = self._extract_comments(post_data[1]["data"]["children"][:5])
            
            comment_text = "\n\nTop Comments:\n"
            for i, c in enumerate(comments):
                comment_text += f"{i+1}. {c['body']}\n"

            return {
                "title": title,
                "body": f"{body}{comment_text}" if body else comment_text.strip(),
                "created_utc": main_post.get("created_utc"),
            }
        except Exception as e:
            logging.error(f"Error scraping Reddit post {permalink}: {e}")
            return None

    def _extract_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        extracted = []
        for comment in comments:
            if isinstance(comment, dict) and comment.get("kind") == "t1":
                comment_data = comment.get("data", {})
                extracted.append({
                    "author": comment_data.get("author", ""),
                    "body": comment_data.get("body", ""),
                })
        return extracted

def get_subreddit_name(url: str) -> Optional[str]:
    """Extract 'python' from 'https://www.reddit.com/r/python'"""
    match = re.search(r'reddit\.com/r/([\w-]+)', url)
    if match:
        return match.group(1)
    return None
