"""
FastAPI server that exposes the verify_content_agent as an HTTP endpoint.
This allows the browser extension to call the agent via REST API.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import your mcp-agent app and tools
from main import app as mcp_app, verify_content_agent
from mcp_agent.core.context import Context as AppContext

# Global variable to hold the app context
app_context: Optional[AppContext] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the mcp-agent app."""
    global app_context

    # Start the mcp-agent app and get context
    async with mcp_app.run() as agent_app:
        app_context = agent_app.context
        yield  # Keep running
        # Cleanup happens here when server shuts down


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


class VerifyResponse(BaseModel):
    is_correct: bool | None
    explanation: str
    source_url: str
    source_description: str
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
        # Call your verify_content_agent tool
        result = await verify_content_agent(
            url=request.url,
            title=request.title,
            subtext=request.subtext,
            app_ctx=app_context,
        )
        
        # result is now a dict, not a string
        return VerifyResponse(
            is_correct=result.get("is_correct"),
            explanation=result.get("explanation", ""),
            source_url=result.get("source_url", ""),
            source_description=result.get("source_description", ""),
            status="success"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error verifying content: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
