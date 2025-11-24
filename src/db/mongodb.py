"""
MongoDB connection manager for async operations using Motor.
"""

from __future__ import annotations

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Global client instance
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


def get_mongodb_uri() -> str:
    """
    Get MongoDB connection URI from environment variable.
    Falls back to local MongoDB if MONGODB_URI is not set.
    """
    uri = os.getenv("MONGODB_URI")
    if not uri:
        # Fallback to the hardcoded URI if env var is missing
        uri = "mongodb+srv://saketh:mdVe8sQu8QtciKPG@cluster0.twxcezi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    return uri


async def connect_to_mongodb() -> AsyncIOMotorClient:
    """
    Create and return MongoDB client connection.
    Uses connection pooling for better performance.
    """
    global _client

    if _client is None:
        uri = get_mongodb_uri()
        _client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            maxPoolSize=10,  # Connection pool size
        )

        # Test connection
        try:
            await _client.admin.command("ping")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")

    return _client


async def get_database() -> AsyncIOMotorDatabase:
    """
    Get database instance. Creates connection if needed.
    """
    global _database

    if _database is None:
        client = await connect_to_mongodb()
        # Extract database name from URI or use default
        uri = get_mongodb_uri()
        # Check if URI contains database name after the host but before query params
        try:
            from pymongo.uri_parser import parse_uri
            parsed = parse_uri(uri)
            db_name = parsed.get("database")
        except Exception:
            db_name = None
            
        if not db_name:
            db_name = "reddit_verifier"
            
        _database = client[db_name]

    return _database


async def close_mongodb_connection():
    """
    Close MongoDB connection. Called on app shutdown.
    """
    global _client, _database

    if _client:
        _client.close()
        _client = None
        _database = None

