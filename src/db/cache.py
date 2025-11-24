"""
Cache service for storing and retrieving verification results.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse, urlunparse

from .mongodb import get_database

logger = logging.getLogger(__name__)

COLLECTION_NAME = "verification_cache"
CACHE_TTL_DAYS = 30


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent caching.
    - Convert to lowercase
    - Remove trailing slashes
    - Remove query parameters and fragments
    - Remove www. prefix
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.lower().strip())
        # Remove query and fragment
        normalized = urlunparse(
            (
                parsed.scheme,
                parsed.netloc.replace("www.", ""),
                parsed.path.rstrip("/"),
                "",
                "",
                "",
            )
        )
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        return url.lower().strip()


def generate_cache_key(url: str) -> str:
    """
    Generate SHA256 hash of normalized URL for use as cache key.
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
    """
    try:
        db = await get_database()
        collection = db[COLLECTION_NAME]

        cache_key = generate_cache_key(url)

        # Find document by cache_key
        doc = await collection.find_one({"cache_key": cache_key})

        if doc is None:
            logger.debug(f"Cache miss for URL: {url}")
            return None

        # Check if expired (though TTL index should handle this)
        expires_at = doc.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            logger.debug(f"Cache entry expired for URL: {url}")
            # Delete expired entry
            await collection.delete_one({"_id": doc["_id"]})
            return None

        logger.info(f"Cache hit for URL: {url}")
        return doc.get("result")

    except Exception as e:
        logger.warning(f"Error retrieving cache for URL '{url}': {e}")
        # Graceful degradation - return None on error
        return None


async def store_verification(url: str, result: dict):
    """
    Store verification result in cache.
    
    Args:
        url: The URL that was verified
        result: The verification result dict to cache
    """
    try:
        db = await get_database()
        collection = db[COLLECTION_NAME]

        cache_key = generate_cache_key(url)
        normalized_url = normalize_url(url)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=CACHE_TTL_DAYS)

        document = {
            "cache_key": cache_key,
            "url": normalized_url,
            "result": result,
            "created_at": now,
            "expires_at": expires_at,
        }

        # Use upsert to handle duplicates
        await collection.update_one(
            {"cache_key": cache_key},
            {"$set": document},
            upsert=True,
        )

        logger.info(f"Cached verification result for URL: {url}")

    except Exception as e:
        logger.error(f"Error storing cache for URL '{url}': {e}")
        # Don't raise - cache storage failure shouldn't block verification

