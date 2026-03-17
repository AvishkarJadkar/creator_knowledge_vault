from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    @property
    @abstractmethod
    def icon(self) -> str:
        """Emoji or Lucide icon name."""
        pass

    @abstractmethod
    def search(self, keyword: str, limit: int = 5) -> list[dict]:
        """Returns list of result dicts: {title, url, summary, score, source, raw_text}"""
        pass

PROVIDERS = {}

def register_provider(provider_cls):
    provider = provider_cls()
    PROVIDERS[provider.name] = provider
    return provider_cls
