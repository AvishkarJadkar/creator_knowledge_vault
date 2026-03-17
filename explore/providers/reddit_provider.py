from . import BaseProvider, register_provider
from reddit_utils import RedditScraper
import html
import logging

@register_provider
class RedditProvider(BaseProvider):
    @property
    def name(self):
        return "reddit"

    @property
    def display_name(self):
        return "Reddit"

    @property
    def icon(self):
        return "hash" # Or a reddit emoji

    def __init__(self):
        self.scraper = RedditScraper()

    def search(self, keyword: str, limit: int = 5) -> list[dict]:
        """
        Search Reddit for keyword, fetching post details and top comments.
        """
        # Reddit Search API: https://www.reddit.com/search.json?q=KEYWORD&sort=relevance&limit=N
        url = "https://www.reddit.com/search.json"
        params = {"q": keyword, "sort": "relevance", "limit": limit}
        
        try:
            response = self.scraper.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            results = []
            for post in posts:
                p_data = post["data"]
                permalink = p_data["permalink"]
                
                # Consolidate: Fetch deeper details (body + comments) in ONE request
                # We use scrape_post_details but manually extract comments too
                details_url = f"https://www.reddit.com{permalink}.json"
                try:
                    resp = self.scraper.session.get(details_url, timeout=10)
                    resp.raise_for_status()
                    post_blob = resp.json()
                    
                    full_body = ""
                    comments = []
                    
                    if len(post_blob) > 0:
                        main_post = post_blob[0]["data"]["children"][0]["data"]
                        full_body = main_post.get("selftext", "")
                    
                    if len(post_blob) > 1:
                        comments_raw = post_blob[1]["data"]["children"][:5]
                        comments = self.scraper._extract_comments(comments_raw)
                except Exception as e:
                    logging.warning(f"Failed deeper fetch for {permalink}: {e}")
                    full_body = p_data.get("selftext", "")
                    comments = []

                result = {
                    "title": p_data["title"],
                    "url": f"https://www.reddit.com{permalink}",
                    "source": f"r/{p_data['subreddit']}",
                    "score": p_data.get("ups", 0),
                    "created_utc": p_data.get("created_utc"),
                    "thumbnail": self._get_best_thumbnail(p_data),
                    # Truncate preview for UI display
                    "summary": (full_body[:400] + "...") if len(full_body) > 400 else full_body,
                    "comments": comments
                }
                
                # Truncate content for AI synthesis (prevent context blow-out)
                safe_body = full_body[:1000]
                formatted_comments = self._format_comments(comments)[:1000]
                result["raw_text"] = f"Title: {result['title']}\nBody: {safe_body}\nComments:\n{formatted_comments}"
                
                results.append(result)
            return results
        except Exception as e:
            logging.error(f"RedditProvider search error: {e}")
            return []

    def _fetch_comments_only(self, permalink: str) -> list[dict]:
        """Fetch top 3-5 top-level comments."""
        url = f"https://www.reddit.com{permalink}.json"
        try:
            response = self.scraper.session.get(url, timeout=10)
            response.raise_for_status()
            post_data = response.json()
            if len(post_data) > 1:
                comments_raw = post_data[1]["data"]["children"][:5]
                return self.scraper._extract_comments(comments_raw)
        except:
            pass
        return []

    def _get_best_thumbnail(self, p_data: dict) -> str | None:
        """Try to get the best available image: preview > thumbnail."""
        # 1. Try Reddit's preview images (higher quality, more reliable)
        try:
            preview = p_data.get("preview", {})
            images = preview.get("images", [])
            if images:
                # Get the source (full-res) image URL
                source_url = images[0].get("source", {}).get("url", "")
                if source_url.startswith("http"):
                    # Reddit HTML-encodes preview URLs (&amp; instead of &)
                    return html.unescape(source_url)
                # Try resolutions (smaller previews) as fallback
                resolutions = images[0].get("resolutions", [])
                if resolutions:
                    res_url = resolutions[-1].get("url", "")
                    if res_url.startswith("http"):
                        return html.unescape(res_url)
        except (KeyError, IndexError, TypeError):
            pass

        # 2. Fall back to thumbnail
        thumb = p_data.get("thumbnail", "")
        if thumb.startswith("http"):
            return thumb

        return None

    def _format_comments(self, comments: list[dict]) -> str:
        return "\n".join([f"- {c['body']}" for c in comments])
