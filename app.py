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

# Import your mcp-agent app and tools
from main import app as mcp_app, verify_content_agent
from mcp_agent.core.context import Context as AppContext

# Import MongoDB cache functions
from db.cache import get_cached_verification, store_verification
from db.init_indexes import ensure_indexes
from db.mongodb import close_mongodb_connection

# Global variable to hold the app context
app_context: Optional[AppContext] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the mcp-agent app."""
    global app_context

    # Start the mcp-agent app and get context
    async with mcp_app.run() as agent_app:
        app_context = agent_app.context

        # Initialize MongoDB indexes
        try:
            await ensure_indexes()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"MongoDB index initialization failed: {e}. App will continue without cache."
            )

        yield  # Keep running
        # Cleanup happens here when server shuts down
        await close_mongodb_connection()


# Create FastAPI app
fastapi_app = FastAPI(
    title="Reddit Content Verifier API",
    description="API for verifying Reddit post content using Tavily",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow requests from browser extension
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your extension's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class VerifyRequest(BaseModel):
    url: str
    title: str
    subtext: str
    postDate: str  # Add this field


class SourceItem(BaseModel):
    source_url: str
    source_description: str


class VerifyResponse(BaseModel):
    is_correct: bool | None
    explanation: str
    sources: list[SourceItem]
    # Backwards compatibility fields for older extension versions
    source_url: str | None = None
    source_description: str | None = None
    status: str = "success"


@fastapi_app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Reddit Content Verifier API is running"}


@fastapi_app.post("/verify", response_model=VerifyResponse)
async def verify_content(request: VerifyRequest):
    """
    Verify Reddit post content using Tavily and return fact-checked summary.

    This endpoint receives title, URL, and subtext from the browser extension,
    calls the verify_content_agent, and returns the verified content.
    """
    global app_context

    if app_context is None:
        raise HTTPException(
            status_code=503,
            detail="MCP agent app is not initialized yet. Please wait a moment and try again.",
        )

    try:
        # Check cache first
        cached_result = None
        try:
            cached_result = await get_cached_verification(request.url)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Cache lookup failed: {e}. Proceeding with verification.")

        if cached_result:
            # Cache hit - return cached result
            result = cached_result
        else:
            # Cache miss - perform verification
            result = await verify_content_agent(
                url=request.url,
                title=request.title,
                subtext=request.subtext,
                postDate=request.postDate,
                app_ctx=app_context,
            )

            # Store result in cache (non-blocking) if valid verification
            if result.get("is_correct") is not None or result.get("explanation"):
                try:
                    await store_verification(request.url, result)
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Cache storage failed: {e}. Result still returned to user.")
            else:
                logger = logging.getLogger(__name__)
                logger.info(f"Verification inconclusive, skipping cache for URL: {request.url}")

        raw_sources = result.get("sources") or []

        # Backwards compatibility: if old keys exist, convert them
        if not raw_sources and result.get("source_url"):
            raw_sources = [
                {
                    "source_url": result.get("source_url", ""),
                    "source_description": result.get("source_description", ""),
                }
            ]

        # Ensure all sources have required fields and are not empty strings
        normalized_sources: list[SourceItem] = []
        for source in raw_sources:
            url = (source or {}).get("source_url", "").strip()
            desc = (source or {}).get("source_description", "").strip()
            if url:
                normalized_sources.append(
                    SourceItem(source_url=url, source_description=desc)
                )

        primary_source_url = normalized_sources[0].source_url if normalized_sources else ""
        primary_source_description = (
            normalized_sources[0].source_description if normalized_sources else ""
        )

        return VerifyResponse(
            is_correct=result.get("is_correct"),
            explanation=result.get("explanation", ""),
            sources=normalized_sources,
            source_url=primary_source_url,
            source_description=primary_source_description,
            status="success",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error verifying content: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
