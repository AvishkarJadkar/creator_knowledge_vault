from .routes import explore_bp
from .providers.reddit_provider import RedditProvider # This triggers registration
from .providers.hn_provider import HackerNewsProvider # Fallback source, no auth required
