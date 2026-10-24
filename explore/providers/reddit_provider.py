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
        Uses OAuth when REDDIT_CLIENT_ID/SECRET are configured; otherwise the
        public JSON API is attempted (often blocked with a 403 on servers).
        """
        try:
            posts = self.scraper.search_posts(keyword, limit=limit)
        except Exception as e:
            logging.error(f"RedditProvider search error: {e}")
            return []

        results = []
        for p_data in posts:
            permalink = p_data.get("permalink")
            if not permalink:
                continue

            full_body = p_data.get("selftext", "") or ""
            comments = []
            try:
                comments = self.scraper.fetch_post_comments(permalink)
            except Exception as e:
                logging.warning(f"Failed deeper fetch for {permalink}: {e}")

            result = {
                "title": p_data.get("title", "Reddit post"),
                "url": f"https://www.reddit.com{permalink}",
                "source": f"r/{p_data.get('subreddit', 'reddit')}",
                "score": p_data.get("ups", 0),
                "created_utc": p_data.get("created_utc"),
                "thumbnail": self._get_best_thumbnail(p_data),
                # Truncate preview for UI display
                "summary": (full_body[:400] + "...") if len(full_body) > 400 else full_body,
                "comments": comments,
            }

            # Truncate content for AI synthesis (prevent context blow-out)
            safe_body = full_body[:1000]
            formatted_comments = self._format_comments(comments)[:1000]
            result["raw_text"] = f"Title: {result['title']}\nBody: {safe_body}\nComments:\n{formatted_comments}"

            results.append(result)
        return results

    def _fetch_comments_only(self, permalink: str) -> list[dict]:
        """Fetch top 3-5 top-level comments."""
        try:
            return self.scraper.fetch_post_comments(permalink)
        except Exception as e:
            logging.warning(f"Failed fetching comments for {permalink}: {e}")
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
