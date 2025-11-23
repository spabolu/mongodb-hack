"""
Initialize MongoDB indexes for verification cache.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from db.mongodb import get_database

logger = logging.getLogger(__name__)


async def ensure_indexes():
    """
    Create necessary indexes for the verification_cache collection.
    - TTL index on expires_at (auto-delete after 30 days)
    - Unique index on cache_key for fast lookups
    """
    try:
        db = await get_database()
        collection = db["verification_cache"]

        # Create TTL index on expires_at field
        # Documents will be automatically deleted after expires_at time
        await collection.create_index(
            "expires_at",
            expireAfterSeconds=0,  # 0 means use expires_at value directly
            name="ttl_index_expires_at",
        )
        logger.info("Created TTL index on expires_at field")

        # Create unique index on cache_key for fast lookups
        await collection.create_index(
            "cache_key",
            unique=True,
            name="unique_index_cache_key",
        )
        logger.info("Created unique index on cache_key field")

        # Create index on created_at for potential analytics queries
        await collection.create_index(
            "created_at",
            name="index_created_at",
        )
        logger.info("Created index on created_at field")

    except Exception as e:
        logger.warning(f"Failed to create MongoDB indexes: {e}")
        # Don't raise - allow app to continue without indexes
        # Indexes can be created manually if needed

