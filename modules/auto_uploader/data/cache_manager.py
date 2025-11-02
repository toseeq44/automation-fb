"""Cache Manager - Caching system"""
import logging

class CacheManager:
    def __init__(self):
        logging.debug("CacheManager initialized")
        self.cache = {}

    def cache_set(self, key: str, value: any) -> None:
        """Set cache value."""
        self.cache[key] = value

    def cache_get(self, key: str) -> any:
        """Get cache value."""
        return self.cache.get(key)
