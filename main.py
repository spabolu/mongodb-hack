"""
Welcome to mcp-agent! We believe MCP is all you need to build and deploy agents.
This is a canonical getting-started example that covers everything you need to know to get started.

We will cover:
  - Hello world agent: Setting up a basic Agent that uses the fetch and filesystem MCP servers to do cool stuff.
  - @app.tool and @app.async_tool decorators to expose your agents as long-running tools on an MCP server.
  - Advanced MCP features: Notifications, sampling, and elicitation

You can run this example locally using "uv run main.py", and also deploy it as an MCP server using "mcp-agent deploy".

Let's get started!
"""

from __future__ import annotations

import asyncio
from typing import Optional

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.agents.agent_spec import AgentSpec
from mcp_agent.core.context import Context as AppContext
from mcp_agent.workflows.factory import create_agent

# We are using the OpenAI augmented LLM for this example but you can swap with others (e.g. AnthropicAugmentedLLM)
from mcp_agent.workflows.llm.augmented_llm_google import GoogleAugmentedLLM
import re
import json
from datetime import datetime

# Create the MCPApp, the root of mcp-agent.
app = MCPApp(
    name="Reddit Community Notes",
    description="Reddit Community Notes is a tool that verifies the content of a Reddit post using Tavily.",
    # settings= <specify programmatically if needed; by default, configuration is read from mcp_agent.config.yaml/mcp_agent.secrets.yaml>
)

@app.tool()
async def verify_content_agent(
    url: str, title: str, subtext: str, app_ctx: Optional[AppContext] = None
) -> dict:
    """
    Verify content from Reddit posts using Tavily to find reputable sources
    and extract additional context.
    """
    logger = app_ctx.app.logger
    logger.info(f"Verifying content for URL: {url}")
    current_date = datetime.now().strftime("%Y-%m-%d")

    # List of reputable news sources for r/news and r/politics
    reputable_domains = [
        # === Pure Center / Gold Standard (least bias, highest accuracy) ===
        "reuters.com",           # #1 most neutral wire service
        "apnews.com",            # AP’s public site (prefer over ap.org)
        "associatedpress.com",   # Alternative AP domain
        "bbc.com",               # BBC News (global edition)
        "bbc.co.uk",             # BBC UK (same content)
        "axios.com",             # Center, concise, fact-driven
        "wsj.com",               # News section only — still Center in 2025
        
        # === Very high reliability + only mild Lean Left (still excellent for facts) ===
        "npr.org",               # Transparent, deep reporting
        "pbs.org",               # PBS NewsHour specifically
        "cbsnews.com",           # Network news — much improved
        "abcnews.go.com",        # Same as CBS
        "nbcnews.com",           # Same tier
        
        # === Strong investigative / non-partisan ===
        "propublica.org",        # Non-profit, Pulitzer-level investigations
        "politico.com",          # Straight reporting remains Center-ish in 2025
        
        # === High-quality business/global (minimal U.S. political spin) ===
        "bloomberg.com",         # Business focus reduces partisan noise
        "ft.com",                # Financial Times — very high standards
        "economist.com",         # Slight center-left global tilt but excellent fact-checking
    ]

    # Convert to string for prompt
    domains_str = ", ".join(reputable_domains)
    agent = Agent(
        name="content_verifier",
        instruction=(
            "You are a fact-checking assistant for r/news and r/politics subreddits. "
            "CRITICAL: Information changes rapidly - you MUST search multiple time ranges to find the most current information.\n"
            "Use Tavily MCP tools with domain filters to:\n"
            "1. ALWAYS perform MULTIPLE searches:\n"
            "   - First: time_range 'day' (past 24 hours - breaking news)\n"
            "   - Second: time_range 'week' (past 7 days - recent developments)\n"
            "   - Third: time_range 'month' (if needed for context)\n"
            "2. Search for reputable news sources using ONLY the following domains: "
            f"{domains_str}\n"
            "3. When calling tavily_search, ALWAYS use:\n"
            "   - include_domains parameter with the list above\n"
            "   - time_range parameter: Start with 'day', then 'week', then 'month' if needed\n"
            "   - max_results: 10 to get comprehensive results\n"
            "4. Compare results across time ranges - if 'day' results differ from 'week', recent sources are more accurate\n"
            "5. Extract detailed content from the provided URL if it's from a reputable source\n"
            "6. Check publication dates - prioritize sources from past 24-48 hours\n"
            "7. Compare the claims with reputable sources, paying attention to WHEN sources were published\n"
            "8. If information appears to have changed recently, note this explicitly\n"
            "9. Only use sources from the approved domain list\n"
            "10. If multiple sources exist, choose the MOST RECENT one (within past 24-48 hours if available)\n"
            "11. Generate a verified summary with:\n"
            "   - Verified title and key points\n"
            "   - Links to reputable sources (from approved domains only, prefer very recent)\n"
            "   - Any important context or corrections\n"
            "   - Fact-check status (verified/needs review/disputed)\n"
            "   - Explicit mention of source dates and recency"
        ),
        server_names=["tavily"],  # Use Tavily MCP server
        context=app_ctx,
    )

    async with agent:
        llm = await agent.attach_llm(GoogleAugmentedLLM)

        prompt = f"""
        Verify this Reddit post content and return a JSON response with this exact structure:

        Title: {title}
        URL: {url}
        Subtext: {subtext}

        CRITICAL INSTRUCTIONS - Search Strategy:

        Today's date: {current_date}
        When evaluating sources, prioritize sources from the past 24-48 hours relative to {current_date}.

        You MUST perform MULTIPLE searches to find the most recent information:
        
        1. FIRST SEARCH - Breaking News (Past 24 Hours):
           Call tavily_search with:
           - query: "{title}" or relevant keywords from the title
           - include_domains: [{domains_str}]
           - time_range: "day"
           - max_results: 10
           - Analyze: Are there sources from the past 24 hours? What do they say?
        
        2. SECOND SEARCH - Recent News (Past Week):
           Call tavily_search with:
           - query: Same as above
           - include_domains: [{domains_str}]
           - time_range: "week"
           - max_results: 10
           - Analyze: Compare with "day" results. Do they match? If not, recent sources are more accurate.
        
        3. THIRD SEARCH - Context (Past Month, if needed):
           If the first two searches don't provide enough context, call tavily_search with:
           - query: Same as above
           - include_domains: [{domains_str}]
           - time_range: "month"
           - max_results: 5
           - Analyze: Has information changed over time? What's the timeline?
        
        4. EXTRACT FROM URL:
           Call tavily_extract with the provided URL to see what it actually says
           - Check the publication date
           - Compare with search results
        
        5. COMPARISON & ANALYSIS:
           - Compare information from "day" vs "week" vs "month" searches
           - If "day" sources say something different than "week" sources, the "day" sources are more current
           - Look for evidence of recent changes (elections, appointments, breaking news)
           - Be aware: Political positions, job titles, and current events can change within hours or days
        
        6. SOURCE SELECTION:
           - ALWAYS prefer sources from "day" search (past 24 hours) if available
           - If no "day" sources, use "week" sources (past 7 days)
           - Only use "month" sources if nothing more recent exists
           - When selecting source_url, choose the MOST RECENT publication date available
        
        Return ONLY a valid JSON object with this exact structure:
        {{
        "is_correct": true/false,
        "explanation": "2-line explanation. MUST include: (1) What recent sources say (mention dates), (2) Whether information has changed recently, (3) Why the post is correct/incorrect based on MOST RECENT information available. Example format: 'Recent sources from [date] indicate that [fact]. This contradicts earlier reports from [date] that stated [old fact].'",
        "source_url": "MOST RECENT source URL from your searches (must be from past 24-48 hours if available, otherwise past week, from approved news domains only)",
        "source_description": "1 sentence. MUST include: (1) Exact publication date, (2) What the source discusses, (3) How it relates to the post. Format: 'This [source name] article published on [date] discusses [topic] and [how it relates to post].'"
        }}

        Do not include any text before or after the JSON.
        """

        result = await llm.generate_str(message=prompt)

        # Extract JSON from response (LLM might add extra text)
        json_match = re.search(r"\{.*\}", result, re.DOTALL)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                return parsed_result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "is_correct": None,
                    "explanation": result[:200],  # First 200 chars as fallback
                    "source_url": url,
                    "source_description": "Unable to parse structured response",
                }
        else:
            # Fallback if no JSON found
            return {
                "is_correct": None,
                "explanation": result[:200],
                "source_url": url,
                "source_description": "No structured response received",
            }

# Hello world agent: an Agent using MCP servers + LLM
@app.tool()
async def finder_agent(request: str, app_ctx: Optional[AppContext] = None) -> str:
    """
    Run an Agent with access to MCP servers (fetch + filesystem) to handle the input request.

    Notes:
    - @app.tool:
      - runs the function as a long-running workflow tool when deployed as an MCP server
      - no-op when running this locally as a script
    - app_ctx:
      - MCPApp Context (configuration, logger, upstream session, etc.)
    """

    logger = app_ctx.app.logger
    # Logger requests are forwarded as notifications/message to the client over MCP.
    logger.info(f"finder_tool called with request: {request}")

    agent = Agent(
        name="finder",
        instruction=(
            "You are a helpful assistant. Use MCP servers to fetch and read files,"
            " then answer the request concisely."
        ),
        server_names=["fetch", "filesystem"],
        context=app_ctx,
    )

    async with agent:
        llm = await agent.attach_llm(GoogleAugmentedLLM)
        result = await llm.generate_str(message=request)
        return result


# Run a configured agent by name (defined in mcp_agent.config.yaml)
@app.async_tool(name="run_agent_async")
async def run_agent(
    agent_name: str = "web_helper",
    prompt: str = "Please summarize the first paragraph of https://modelcontextprotocol.io/docs/getting-started/intro",
    app_ctx: Optional[AppContext] = None,
) -> str:
    """
    Load an agent defined in mcp_agent.config.yaml by name and run it.

    Notes:
    - @app.async_tool:
      - async version of @app.tool -- returns a workflow ID back (can be used with workflows-get_status tool)
      - runs the function as a long-running workflow tool when deployed as an MCP server
      - no-op when running this locally as a script
    """

    logger = app_ctx.app.logger

    agent_definitions = (
        app.config.agents.definitions
        if app is not None
        and app.config is not None
        and app.config.agents is not None
        and app.config.agents.definitions is not None
        else []
    )

    agent_spec: AgentSpec | None = None
    for agent_def in agent_definitions:
        if agent_def.name == agent_name:
            agent_spec = agent_def
            break

    if agent_spec is None:
        logger.error("Agent not found", data={"name": agent_name})
        return f"agent '{agent_name}' not found"

    logger.info(
        "Agent found in spec",
        data={"name": agent_name, "instruction": agent_spec.instruction},
    )

    agent = create_agent(agent_spec, context=app_ctx)

    async with agent:
        llm = await agent.attach_llm(GoogleAugmentedLLM)
        return await llm.generate_str(message=prompt)


async def main():
    async with app.run() as agent_app:
        # Run the agent
        readme_summary = await finder_agent(
            request="Please summarize the README.md file in this directory.",
            app_ctx=agent_app.context,
        )
        print("README.md file summary:")
        print(readme_summary)

        webpage_summary = await run_agent(
            agent_name="web_helper",
            prompt="Please summarize the first few paragraphs of https://modelcontextprotocol.io/docs/getting-started/intro.",
            app_ctx=agent_app.context,
        )
        print("Webpage summary:")
        print(webpage_summary)

        # UNCOMMENT to run this MCPApp as an MCP server
        #########################################################
        # Create the MCP server that exposes both workflows and agent configurations,
        # optionally using custom FastMCP settings
        # from mcp_agent.server.app_server import create_mcp_server_for_app
        # mcp_server = create_mcp_server_for_app(agent_app)

        # # Run the server
        # await mcp_server.run_sse_async()


if __name__ == "__main__":
    asyncio.run(main())

# When you're ready to deploy this MCPApp as a remote SSE server, run:
# > uv run mcp-agent deploy "hello_world" --no-auth
#
# Congrats! You made it to the end of the getting-started example!
# There is a lot more that mcp-agent can do, and we hope you'll explore the rest of the documentation.
# Check out other examples in the mcp-agent repo:
# https://github.com/lastmile-ai/mcp-agent/tree/main/examples
# and read the docs (or ask an mcp-agent to do it for you):
# https://docs.mcp-agent.com/
#
# Happy mcp-agenting!
