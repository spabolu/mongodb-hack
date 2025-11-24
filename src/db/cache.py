"""
Cache service for storing and retrieving verification results.

This module provides caching functionality to avoid re-verifying the same URLs.
Results are stored in MongoDB with a TTL (time-to-live) for automatic expiration.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse, urlunparse

from .mongodb import get_database

logger = logging.getLogger(__name__)

# MongoDB collection name for cache storage
COLLECTION_NAME = "verification_cache"
# Cache entries expire after 30 days
CACHE_TTL_DAYS = 30


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent caching.
    
    Same URL with different formats should map to the same cache key:
    - https://example.com/article and https://www.example.com/article/ should match
    - https://example.com/article?ref=reddit and https://example.com/article should match
    
    - Convert to lowercase
    - Remove trailing slashes
    - Remove query parameters and fragments
    - Remove www. prefix
    """
    if not url:
        return ""

    try:
        # Parse the URL into components
        parsed = urlparse(url.lower().strip())
        
        # Rebuild URL without query params, fragments, and www prefix
        # This ensures URLs like example.com/article?foo=bar and example.com/article match
        normalized = urlunparse(
            (
                parsed.scheme,
                parsed.netloc.replace("www.", ""),  # Remove www. prefix
                parsed.path.rstrip("/"),  # Remove trailing slash
                "",  # params
                "",  # query - removed for normalization
                "",  # fragment - removed for normalization
            )
        )
        return normalized
    except Exception as e:
        # If parsing fails, just return a basic normalized version
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        return url.lower().strip()


def generate_cache_key(url: str) -> str:
    """
    Generate SHA256 hash of normalized URL for use as cache key.
    
    Using a hash instead of the URL directly:
    - Makes the key fixed-length and URL-safe
    - Ensures consistent indexing in MongoDB
    - Prevents issues with special characters in URLs
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def get_cached_verification(url: str) -> Optional[dict]:
    """
    Retrieve cached verification result for a given URL.
    
    Args:
        url: The URL to look up in cache
        
    Returns:
        Cached verification result dict if found and not expired, None otherwise
        
    Note: Returns None on errors - cache failures shouldn't break verification
    """
    try:
        db = await get_database()
        collection = db[COLLECTION_NAME]

        # Generate cache key from normalized URL
        cache_key = generate_cache_key(url)

        # Look up the cached result by key
        doc = await collection.find_one({"cache_key": cache_key})

        if doc is None:
            logger.debug(f"Cache miss for URL: {url}")
            return None

        # Double-check expiration (MongoDB TTL index should auto-delete, but check anyway)
        expires_at = doc.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            logger.debug(f"Cache entry expired for URL: {url}")
            # Clean up expired entry manually
            await collection.delete_one({"_id": doc["_id"]})
            return None

        # Cache hit - return the stored result
        logger.info(f"Cache hit for URL: {url}")
        return doc.get("result")

    except Exception as e:
        # If cache lookup fails, just return None - don't break verification
        logger.warning(f"Error retrieving cache for URL '{url}': {e}")
        return None


async def store_verification(url: str, result: dict):
    """
    Store verification result in cache.
    
    Args:
        url: The URL that was verified
        result: The verification result dict to cache (contains is_correct, explanation, sources)
        
    Note: Uses upsert so storing the same URL again just updates the existing entry.
    Cache failures are logged but don't raise exceptions - verification still succeeds.
    """
    try:
        db = await get_database()
        collection = db[COLLECTION_NAME]

        # Generate cache key and normalize URL for storage
        cache_key = generate_cache_key(url)
        normalized_url = normalize_url(url)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=CACHE_TTL_DAYS)

        # Build the cache document
        document = {
            "cache_key": cache_key,  # Primary lookup key (indexed)
            "url": normalized_url,  # Human-readable URL for debugging
            "result": result,  # The actual verification result
            "created_at": now,  # When this was cached
            "expires_at": expires_at,  # When it expires (used by TTL index)
        }

        # Upsert: update if exists, insert if not
        # This handles the case where the same URL is verified multiple times
        await collection.update_one(
            {"cache_key": cache_key},
            {"$set": document},
            upsert=True,
        )

        logger.info(f"Cached verification result for URL: {url}")

    except Exception as e:
        # Log error but don't raise - cache is a performance optimization
        # If caching fails, verification should still work
        logger.error(f"Error storing cache for URL '{url}': {e}")

