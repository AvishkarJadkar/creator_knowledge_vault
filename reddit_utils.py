import logging
import random
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, List, Optional, Tuple
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

class RandomUserAgentSession(requests.Session):
    def request(self, *args, **kwargs):
        self.headers.update({"User-Agent": get_agent()})
        return super().request(*args, **kwargs)

class RedditScraper:
    def __init__(self, timeout: int = 10):
        self.session = RandomUserAgentSession()
        self.timeout = timeout

        retries = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def fetch_subreddit_posts(
        self, subreddit: str, limit: int = 10, category: str = "hot"
    ) -> List[Dict[str, Any]]:
        url = f"https://www.reddit.com/r/{subreddit}/{category}.json"
        params = {"limit": min(100, limit), "raw_json": 1}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
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
        url = f"https://www.reddit.com{permalink}.json"
        try:
            response = self.session.get(url, timeout=self.timeout)
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
