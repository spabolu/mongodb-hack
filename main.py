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
from urllib.parse import urlparse

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.agents.agent_spec import AgentSpec
from mcp_agent.core.context import Context as AppContext
from mcp_agent.workflows.factory import create_agent

# We are using the OpenAI augmented LLM for this example but you can swap with others (e.g. AnthropicAugmentedLLM)
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
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
    url: str,
    title: str,
    subtext: str,
    postDate: str,
    app_ctx: Optional[AppContext] = None,
) -> dict:
    """
    Verify content from Reddit posts using Tavily to find reputable sources
    and extract additional context.
    """
    logger = app_ctx.app.logger
    logger.info(f"Verifying content for URL: {url}")
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Parse post date and calculate date range for source search
    post_date_str = None
    start_date = None
    end_date = None

    if postDate and postDate != "No date found":
        try:
            # Parse ISO format: "2025-11-03T12:24:47.083Z"
            post_datetime = datetime.fromisoformat(postDate.replace("Z", "+00:00"))
            post_date_str = post_datetime.strftime("%Y-%m-%d")

            # Calculate date range: a few days before and 1-2 days after
            from datetime import timedelta

            start_date = (post_datetime - timedelta(days=3)).strftime(
                "%Y-%m-%d"
            )  # 3 days before
            end_date = (post_datetime + timedelta(days=2)).strftime(
                "%Y-%m-%d"
            )  # 2 days after

            logger.info(
                f"Post date: {post_date_str}, Search range: {start_date} to {end_date}"
            )
        except Exception as e:
            logger.warning(f"Failed to parse post date '{postDate}': {e}")
            # Fallback: use relative time if it's in format like "19d ago"
            if "ago" in postDate.lower():
                # Could parse relative time here if needed
                pass

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

    satire_domains = [
        "theonion.com",
        "babylonbee.com",
        "clickhole.com",
        "thebeaverton.com",
        "waterfordwhispersnews.com",
        "newsbiscuit.com",
    ]

    # Convert to string for prompt
    domains_str = ", ".join(reputable_domains)
    satire_domains_str = ", ".join(satire_domains)
    post_domain = (
        urlparse(url).netloc.replace("www.", "").lower()
        if url not in (None, "")
        else "unknown"
    )
    is_known_satire = post_domain in satire_domains
    agent = Agent(
        name="content_verifier",
        instruction=(
            "You are a fact-checking assistant for r/news, r/politics, and r/TheOnion subreddits. "
            "CRITICAL: Information changes rapidly - you MUST search for sources around the time the post was made.\n"
            f"{f'This post was made on {post_date_str}. Search for sources published between {start_date} and {end_date} to verify claims made around that time.' if post_date_str and start_date and end_date else 'Search for recent sources to verify this post.'}\n"
            "Use Tavily MCP tools with domain filters to:\n"
            "1. ALWAYS perform searches with date filters:\n"
            f"   - start_date: '{start_date}' (if available)\n"
            if start_date
            else f"   - end_date: '{end_date}' (if available)\n"
            if end_date
            else ""
            "   - This ensures you find sources published around the time the post was made\n"
            "2. Search for reputable news sources"
            "3. When calling tavily_search, ALWAYS use:\n"
            "   - include_domains parameter with the list above\n"
            f"   - start_date: '{start_date}' (sources after this date)\n"
            if start_date
            else f"   - end_date: '{end_date}' (sources before this date)\n"
            if end_date
            else ""
            "   - max_results: 10 to get comprehensive results\n"
            "4. Extract detailed content from the provided URL if it's from a reputable source\n"
            "   - CRITICAL: When extracting publication dates, use metadata/structured data, NOT dates mentioned in article content\n"
            "   - The publication date is when the article was published, which may be different from dates mentioned in the content\n"
            "5. Check publication dates - prioritize sources from the date range around the post date\n"
            "6. Compare the claims with reputable sources, paying attention to WHEN sources were published relative to the post date\n"
            "7. If information appears to have changed recently, note this explicitly\n"
            "8. Only use sources from the approved domain list\n"
            "9. If multiple sources exist, choose sources closest to the post date\n"
            "10. Generate a verified summary with:\n"
            "   - Verified title and key points\n"
            "   - Links to reputable sources (from approved domains only, prefer sources from around the post date)\n"
            "   - Any important context or corrections\n"
            "   - Fact-check status (verified/needs review/disputed)\n"
            "   - Explicit mention of source dates and how they relate to the post date"
        ),
        server_names=["tavily"],  # Use Tavily MCP server
        context=app_ctx,
    )

    async with agent:
        try:
            # Since we configured the default model for OpenAI in config.yaml, we don't need to pass it here
            # But if we wanted to override it, we would need to check how OpenAIAugmentedLLM accepts arguments
            # The error suggests attach_llm doesn't accept kwargs for the LLM constructor directly in this version
            # or it expects them differently.
            # However, since we set it in config, let's try without the argument first,
            # or instantiate the LLM class directly if needed.
            # For now, let's rely on the config.
            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            prompt = f"""
            Verify this Reddit post content and return a JSON response with this exact structure:

            Title: {title}
            URL: {url}
            Subtext: {subtext}
            {"Post Date: " + post_date_str + f" (search for sources between {start_date} and {end_date})" if post_date_str and start_date and end_date else ""}

            CRITICAL INSTRUCTIONS - Search Strategy:

            Today's date: {current_date}
            {"The post was made on " + post_date_str + ". Look for sources published between " + start_date + " and " + end_date + " to verify claims made around that time." if post_date_str and start_date and end_date else "Search for recent sources to verify this post."}

            You MUST perform searches with date filters to find sources from around the post date:
            
            1. PRIMARY SEARCH - Sources Around Post Date:
               Call tavily_search with:
               - query: "{title}" or relevant keywords from the title
               {'- start_date: "' + start_date + '" (sources published after this date)' if start_date else ""}
               {'- end_date: "' + end_date + '" (sources published before this date)' if end_date else ""}
               - max_results: 10
               - exclude_domains: ["reddit.com"] 
               - Analyze: Are there sources from around the post date? What do they say?
            
            2. FALLBACK SEARCH - Recent Sources (if primary search yields few results):
               Call tavily_search with:
               - query: Same as above
               - time_range: "week"
               - max_results: 10
               - DO NOT use include_domains - search across all domains
               - exclude_domains: ["reddit.com"]
               - Analyze: Compare with date-filtered results. Are they consistent?
            
            SATIRE / FAKE SOURCE CHECK:
            - Known satire domains: [{satire_domains_str}]
            - This Reddit post references domain: "{post_domain}".
            - If the post domain is a known satire/fake outlet ({'YES' if is_known_satire else 'NO'}) or the content itself reads like satire, explicitly call this out in the explanation.
            - Prioritize reputable fact-checkers or straight news outlets (AP, Reuters, AFP Fact Check, Snopes, etc.) that confirm whether the claim started as satire/misinformation.
            - NEVER treat the satire article itself as validation — it is only context. Use independent news/fact-checking sources that explain the truth.
            
            3. EXTRACT FROM URL:
               Call tavily_extract with the provided URL to see what it actually says. 
               This URL is the Reddit post content provided for context. 
               Use this to understand the claims being made, BUT do not use it as a verification source itself.
               - CRITICAL: When checking publication date, look for:
                 * Metadata fields like "publishedDate", "datePublished", "publishDate"
                 * URL structure that might indicate date (e.g., /2025/11/22/)
                 * Article metadata, not dates mentioned in the article content
               - DO NOT confuse dates mentioned IN the article content (like "July 7, 2021") with the publication date
               - If the article mentions historical dates, those are NOT the publication date
               - The publication date is when the article was published, not when events in the article occurred
               - Compare the ACTUAL publication date with the post date ({post_date_str if post_date_str else "N/A"})
               - If the URL appears to be from around the post date ({start_date} to {end_date}), verify carefully
               - Compare with search results
            
            4. COMPARISON & ANALYSIS:
               - Compare information from date-filtered sources vs recent sources
               - If sources from around the post date say something different than recent sources, note this
               - Look for evidence that supports or contradicts the post based on sources from that time period
               - Example: If a post claims "Zohran Mamdani made a 1am stop at a bar ahead of the mayoral election on November 3rd", look for sources from November 2-5 that mention this event
            
            5. SOURCE SELECTION:
               - ALWAYS prefer sources from the date range around the post date ({start_date} to {end_date}) if available
               - If no sources in that range, use recent sources but note the time gap
               - When selecting source_url, choose sources closest to the post date
               - Verify that the source publication date makes sense for the claim being made
               - CRITICAL: Do NOT use the original Reddit post URL as the source_url for validation. Use an independent news source found via search.
               - If the underlying claim stems from a satire/fake outlet ({'YES' if is_known_satire else 'NO'}), cite reputable sources that clearly state it is satire/fake or otherwise debunk/clarify the claim.
            
            Return ONLY a valid JSON object with this exact structure (NO EXTRA TEXT):
            {{
            "is_correct": true/false,
            "explanation": "2-line explanation...",
            "sources": [
                {{
                    "source_url": "First URL from Tavily search - MUST be a real URL, not a placeholder. Prefer well-known reputable news sources. MUST NOT be the same as the Reddit post URL: {url}",
                    "source_description": "1 sentence for source 1. MUST include: (1) Exact publication date, (2) What the source discusses, (3) How it relates to the post. Format: 'This [source name] article published on [exact date] discusses [topic] and [supports/contradicts] the post's claim.'"
                }},
                {{
                    "source_url": "Second DIFFERENT URL from Tavily search - MUST be distinct from the first source. Prefer well-known reputable news sources. MUST NOT be the same as the Reddit post URL: {url}",
                    "source_description": "1 sentence for source 2. MUST include: (1) Exact publication date, (2) What the source discusses, (3) How it relates to the post. Format: 'This [source name] article published on [exact date] discusses [topic] and [supports/contradicts] the post's claim.'"
                }}
            ]
            }}

            IMPORTANT: Provide EXACTLY 2 sources in the sources array. Ensure both sources are distinct and NEITHER is the original Reddit post URL.
            If you cannot find 2 independent sources, provide 1, but do NOT hallucinate or use the Reddit link as a source.
            """

            result = await llm.generate_str(message=prompt)
            logger.info(f"LLM Raw Response: {result}")

            # Extract JSON from response (LLM might add extra text or markdown code blocks)
            # First, try to strip markdown code blocks
            cleaned_result = result.strip()
            if cleaned_result.startswith('```'):
                # Remove markdown code fences
                lines = cleaned_result.split('\n')
                # Remove first line if it's a code fence
                if lines[0].startswith('```'):
                    lines = lines[1:]
                # Remove last line if it's a code fence
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                cleaned_result = '\n'.join(lines).strip()
            
            # Find the first '{' and the last '}'
            start_idx = cleaned_result.find('{')
            end_idx = cleaned_result.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = cleaned_result[start_idx : end_idx + 1]
                try:
                    parsed_result = json.loads(json_str)
                    logger.info(f"Parsed JSON: {json.dumps(parsed_result, indent=2)}")

                    # Normalize sources array: ensure unique, non-empty, and not the Reddit URL
                    normalized_sources: list[dict[str, str]] = []
                    seen_urls: set[str] = set()
                    reddit_domain = (
                        urlparse(url).netloc.replace("www.", "").lower() if url else ""
                    )

                    for source in parsed_result.get("sources") or []:
                        source_url = (source or {}).get("source_url", "").strip()
                        if not source_url:
                            continue

                        source_domain = (
                            urlparse(source_url).netloc.replace("www.", "").lower()
                        )
                        if source_domain == reddit_domain:
                            continue
                        if source_url in seen_urls:
                            continue

                        normalized_sources.append(
                            {
                                "source_url": source_url,
                                "source_description": (source or {}).get(
                                    "source_description", ""
                                ).strip(),
                            }
                        )
                        seen_urls.add(source_url)

                    if (
                        not normalized_sources
                        and parsed_result.get("source_url")
                        and parsed_result.get("source_url") not in seen_urls
                    ):
                        fallback_url = parsed_result.get("source_url", "")
                        fallback_domain = (
                            urlparse(fallback_url)
                            .netloc.replace("www.", "")
                            .lower()
                        )
                        if fallback_domain and fallback_domain != reddit_domain:
                            normalized_sources.append(
                                {
                                    "source_url": fallback_url,
                                    "source_description": parsed_result.get(
                                        "source_description", ""
                                    ).strip(),
                                }
                            )
                            seen_urls.add(fallback_url)

                    # Keep at most 3 sources for readability
                    parsed_result["sources"] = normalized_sources[:3]

                    return parsed_result
                except json.JSONDecodeError as e:
                    logger.error(f"JSON Decode Error: {e}. Content: {json_str}")
                    # Fallback if JSON parsing fails
                    return {
                        "is_correct": None,
                        "explanation": result[:200],
                        "sources": [],
                    }
            else:
                logger.error("No JSON found in response")
                # Fallback if no JSON found
                return {
                    "is_correct": None,
                    "explanation": result[:200],
                    "sources": [],
                }
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            raise e

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
        llm = await agent.attach_llm(OpenAIAugmentedLLM)
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
        llm = await agent.attach_llm(OpenAIAugmentedLLM)
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
