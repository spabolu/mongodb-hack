"""
FastAPI server that exposes the verify_content_agent as an HTTP endpoint.
This allows the browser extension to call the agent via REST API.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the MCP agent app and verification function
from .main import app as mcp_app, verify_content_agent
from mcp_agent.core.context import Context as AppContext

# MongoDB cache functions for storing/retrieving verification results
from .db.cache import get_cached_verification, store_verification
from .db.init_indexes import ensure_indexes
from .db.mongodb import close_mongodb_connection

# Global context shared across requests
# Set during app startup, used by verification endpoint
app_context: Optional[AppContext] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages app lifecycle: startup and shutdown.
    Runs when FastAPI starts, cleans up when it shuts down.
    """
    global app_context

    # Start the MCP agent and store its context for use in endpoints
    async with mcp_app.run() as agent_app:
        app_context = agent_app.context

        # Set up MongoDB indexes for efficient cache lookups
        # If this fails, we log a warning but continue (cache just won't work)
        try:
            await ensure_indexes()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"MongoDB index initialization failed: {e}. App will continue without cache."
            )

        yield  # Server runs here
        # Cleanup: close MongoDB connection when server shuts down
        await close_mongodb_connection()


# Create the FastAPI application
# The lifespan function handles startup/shutdown
fastapi_app = FastAPI(
    title="Reddit Content Verifier API",
    description="API for verifying Reddit post content using Tavily",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS so the browser extension can make requests
# Currently allows all origins - restrict this in production!
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your extension's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation

class VerifyRequest(BaseModel):
    """Request payload from the browser extension."""
    url: str  # URL of the post or linked article
    title: str  # Post title
    subtext: str  # Post body text (first 300 chars)
    postDate: str  # Post date/timestamp


class SourceItem(BaseModel):
    """A single source reference."""
    source_url: str
    source_description: str


class VerifyResponse(BaseModel):
    """Response sent back to the extension."""
    is_correct: bool | None  # True/false/None (unable to verify)
    explanation: str  # Human-readable explanation
    sources: list[SourceItem]  # List of source references
    # Legacy fields for backwards compatibility with older extension versions
    source_url: str | None = None
    source_description: str | None = None
    status: str = "success"


@fastapi_app.get("/")
async def root():
    """Simple health check - confirms the API is running."""
    return {"status": "ok", "message": "Reddit Content Verifier API is running"}


@fastapi_app.post("/verify", response_model=VerifyResponse)
async def verify_content(request: VerifyRequest):
    """
    Main verification endpoint - called by the browser extension.

    Flow:
    1. Check MongoDB cache for existing verification
    2. If cache miss, call the MCP agent to verify content
    3. Store result in cache (if valid)
    4. Normalize and return response
    """
    global app_context

    # Make sure the MCP agent is initialized before processing requests
    if app_context is None:
        raise HTTPException(
            status_code=503,
            detail="MCP agent app is not initialized yet. Please wait a moment and try again.",
        )

    try:
        # Try to get cached result first (much faster than re-verifying)
        cached_result = None
        try:
            cached_result = await get_cached_verification(request.url)
        except Exception as e:
            # Cache lookup failed, but we'll continue with verification
            logger = logging.getLogger(__name__)
            logger.warning(f"Cache lookup failed: {e}. Proceeding with verification.")

        if cached_result:
            # Found in cache - return immediately (no API calls needed)
            result = cached_result
        else:
            # Not in cache - call the MCP agent to verify the content
            result = await verify_content_agent(
                url=request.url,
                title=request.title,
                subtext=request.subtext,
                postDate=request.postDate,
                app_ctx=app_context,
            )

            # Store in cache for future requests (but don't block if it fails)
            # Only cache if we got a meaningful result
            if result.get("is_correct") is not None or result.get("explanation"):
                try:
                    await store_verification(request.url, result)
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Cache storage failed: {e}. Result still returned to user.")
            else:
                # Don't cache inconclusive results
                logger = logging.getLogger(__name__)
                logger.info(f"Verification inconclusive, skipping cache for URL: {request.url}")

        # Normalize sources from the result
        # The agent might return sources in different formats, so we normalize them
        raw_sources = result.get("sources") or []

        # Handle old format: if agent returned single source_url/source_description
        # Convert it to the new list format for backwards compatibility
        if not raw_sources and result.get("source_url"):
            raw_sources = [
                {
                    "source_url": result.get("source_url", ""),
                    "source_description": result.get("source_description", ""),
                }
            ]

        # Clean up sources: remove empty ones, ensure required fields exist
        normalized_sources: list[SourceItem] = []
        for source in raw_sources:
            url = (source or {}).get("source_url", "").strip()
            desc = (source or {}).get("source_description", "").strip()
            # Only include sources with valid URLs
            if url:
                normalized_sources.append(
                    SourceItem(source_url=url, source_description=desc)
                )

        # Extract first source for backwards compatibility fields
        # Older extension versions expect source_url/source_description at top level
        primary_source_url = normalized_sources[0].source_url if normalized_sources else ""
        primary_source_description = (
            normalized_sources[0].source_description if normalized_sources else ""
        )

        # Build and return the response
        return VerifyResponse(
            is_correct=result.get("is_correct"),
            explanation=result.get("explanation", ""),
            sources=normalized_sources,
            source_url=primary_source_url,  # For backwards compatibility
            source_description=primary_source_description,  # For backwards compatibility
            status="success",
        )

    except Exception as e:
        # Catch any errors and return a proper HTTP error response
        raise HTTPException(
            status_code=500, detail=f"Error verifying content: {str(e)}"
        )


def main():
    """
    Entry point for running the server.
    Can be called via console scripts or directly.
    """
    import uvicorn

    # Start the server on all interfaces, port 8000
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
