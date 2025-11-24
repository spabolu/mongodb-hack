# Reddit Community Notes – AI-powered Truth Checker

This project improves Reddit with an AI-powered "Truth Checker" that runs directly in the browser. It is inspired by X/Twitter's Community Notes feature and the rise of misinformation on forums like Reddit.

It consists of three main pieces:

1. **Frontend Chrome Extension** (`reddit-extension/`): injects a panel into eligible Reddit posts (r/news, r/politics, r/TheOnion) and calls the backend to display the verification results.
2. **Backend FastAPI Server** (`src/app.py`, `src/main.py`): wraps LastMile's `mcp-agent` app, exposes a `/verify` endpoint, and orchestrates Tavily searches plus LLM reasoning.
3. **AI + MCP Tooling**: Tavily MCP server for search, LastMile's `mcp-agent` for workflow management, and OpenAI/Gemini LLM backends via augmented LLMs.

## 🌐 Live Services

- **MCP Agent**: [https://1eb4wbtqipdcbkqwm8ve7wtnmo9mk0wk.deployments.mcp-agent.com/](https://1eb4wbtqipdcbkqwm8ve7wtnmo9mk0wk.deployments.mcp-agent.com/)
- **FastAPI Backend**: [https://cef5c5f9c1f3.ngrok-free.app/](https://cef5c5f9c1f3.ngrok-free.app/)

## Example Screenshot
<table>
  <tr>
    <td>
      <img src="./SCR-20251123-mifh.png" alt="Real news post" width="100%">
    </td>
    <td>
      <img src="./SCR-20251123-mhmi.png" alt="Fake/satire news post" width="100%">
    </td>
  </tr>
</table>


---
#
## Tech stack
- Tavily MCP (search/extract/crawl tools)
- LastMile's MCP-Agent
- MongoDB (`pymongo`) driver
- OpenAI/Gemini LLMs
- Chrome Extension `ManifestV3` (JavaScript)
- FastAPI (Python 3)
- Fetch/Web tooling for REST calls and packaging
- `uv` for dependency/env management

---

## Frontend (Chrome Extension)

* Lives in `reddit-extension/`.
* Injects Twitter's "Community Notes"-style card into each Reddit post that matches the supported subreddits.
* Sends a POST request to `/verify` endpoint with the post URL, title, subtext, and detected timestamp.
* Renders the structured response (verdict + sources) returned by the backend.

### Running the extension

1. Build/prepare the backend first (see next section).
2. In Chrome, open `chrome://extensions`, enable **Developer Mode**, then **Load unpacked**.
3. Select the `reddit-extension/` folder.
4. Visit Reddit and verify posts to see the injected panel.

##### Example URLs to try:
1. Reddit [r/news](https://www.reddit.com/r/news/comments/1p33pck/france_will_investigate_musks_grok_chatbot_after/)

2. Reddit [r/TheOnion](https://www.reddit.com/r/TheOnion/comments/1ok7fzi/china_agrees_to_purchase_11_us_soybeans/)

3. Reddit [r/news](https://www.reddit.com/r/news/comments/1olrogq/80_of_nycarea_air_traffic_controllers_absent_amid/)

---

## Backend (FastAPI + MCP Agent)

* The core MCP agent logic lives in `src/main.py` (adapted LastMile's `mcp-agent` example).
* `src/app.py` wraps the MCP app with FastAPI and exposes `/verify` endpoint.
* Uses Tavily MCP server to fetch reputable sources and OpenAI/Gemini LLMs (via `OpenAIAugmentedLLM`).
* MongoDB caching layer (`src/db/`) for storing verification results to reduce API costs. Uses hashing to store unique id of the Reddit post URL.

### Project Structure

```
.
├── src/
│   ├── app.py              # FastAPI server with /verify endpoint
│   ├── main.py             # MCP agent with verify_content_agent tool
│   └── db/
│       ├── cache.py         # MongoDB cache for verification results
│       ├── mongodb.py       # MongoDB connection management
│       └── init_indexes.py  # Database index initialization
├── reddit-extension/        # Chrome extension frontend
│   ├── content.js          # Extension content script
│   └── manifest.json       # Extension manifest
├── mcp_agent.config.yaml   # MCP agent configuration
├── mcp_agent.secrets.yaml  # API keys (references .env)
└── pyproject.toml          # Python dependencies
```

### Prerequisites

* Python 3.11+
* [uv](https://github.com/astral-sh/uv) for managing the virtual environment.
* Tavily API key and LLM provider API keys (OpenAI/Gemini) — stored in secrets files / `.env`.
* MongoDB (Atlas or local) — optional but recommended for caching verification results.
* Highly recommend using OpenAI `gpt-5-mini-2025-08-07` model for efficiency and/or `gpt-5.1-2025-11-13` model for best accuracy.

### Installation & Running

```bash
# Install dependencies
uv sync

# Start the FastAPI server
uv run uvicorn src.app:fastapi_app --reload --host 0.0.0.0 --port 8000

# Or use the console script entry point
uv run app
```

The server listens on `http://0.0.0.0:8000`. The browser extension should point there for verification requests.

**Note**: The extension is currently configured to use the deployed backend at `https://cef5c5f9c1f3.ngrok-free.app/verify`. To use a local server, update the URL in `reddit-extension/content.js`.

---

## AI Libraries / Services

| Component | Purpose |
|-----------|---------|
| **Tavily MCP server** | Performs date-bounded searches on reputable domains using `topic="news"` to filter for news sources, returning structured search results with publication dates. |
| **LastMile's `mcp-agent`** | Provides the MCP workflow framework, agent lifecycle, logging, and server connections. |
| **OpenAI / Gemini LLMs** | Reason over Tavily results, enforce JSON schema, and summarize verification. `OpenAIAugmentedLLM` is currently configured with the `gpt-5-mini-2025-08-07` model. |

The workflow enforces:
* Date filters aligned with the Reddit post timestamp.
* Use the `topic="news"` parameter in Tavily searches to prioritize recent news sources with publication dates (thanks to Yash for suggesting this feature).
* Reputable domain whitelists.
* Satire/fake-source detection (don't treat original satire articles as "proof").
* Returning multiple independent sources with descriptions.

---

## Configuration & Secrets

### `.env`

Create a `.env` in the repo root. Structure as follows:

```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
TAVILY_API_KEY=tvly-...
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/reddit_verifier?retryWrites=true&w=majority
```

`uv` automatically reads `.env` files when running commands. The FastAPI server and MCP config reference these environment variables.

### MongoDB Setup

MongoDB is used to cache verification results, reducing API costs and improving response times for repeated post verifications.

#### MongoDB Atlas

1. Create a free account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a new cluster (free tier M0 is sufficient)
3. Create a database user and set a password
4. Add your IP address to the network access list (or use `0.0.0.0/0` for development)
5. Click "Connect" → "Connect your application" → Copy the connection string
6. Replace `<password>` with your database user password and `<dbname>` with `reddit_verifier`
7. Add the connection string to your `.env` file as `MONGODB_URI`

Example connection string format:
```
mongodb+srv://username:password@cluster.mongodb.net/reddit_verifier?retryWrites=true&w=majority
```

#### Cache Behavior

- **Cache Key**: SHA256 hash of normalized URL (handles URL variations)
- **TTL**: 30 days (results auto-expire)
- **Graceful Degradation**: If MongoDB is unavailable, verification still works (just without caching)
- **Indexes**: Automatically created on first startup (TTL index on `expires_at`, unique index on `cache_key`)

The cache significantly reduces API costs when the same Reddit posts are verified multiple times.

### `mcp_agent.config.yaml`

* Core MCP agent configuration (logger, MCP servers, agent definitions, default models).
* Update the `openai.default_model` or add other provider defaults if needed.
* Tavily server uses `python -m mcp_server_tavily` and expects `TAVILY_API_KEY` in the environment.

### `mcp_agent.secrets.yaml`

* Stores provider API keys and MCP server env overrides.
* Structure as follows:

```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
google:
  api_key: "${GOOGLE_API_KEY}"

mcp:
  servers:
    tavily:
      env:
        TAVILY_API_KEY: "${TAVILY_API_KEY}"
```

> Never commit real keys. Reference environment variables via `${VAR_NAME}` and keep the `.env` local.

---

## Development Workflow

1. Update dependencies or code.
2. Run `uv run python src/main.py` (or the specific test script) to ensure the agent still returns valid JSON with at least two sources.
3. Start the FastAPI server (`uv run uvicorn src.app:fastapi_app --reload`).
4. Load the Chrome extension and verify posts.
5. Check the terminal logs for "LLM Raw Response" and "Parsed JSON" to debug any schema issues.

With this setup, you can quickly iterate on the Chrome UI, backend logic, or the MCP/LLM instructions to improve verification quality.

## API Endpoints

### `GET /`
Health check endpoint. Returns `{"status": "ok", "message": "Reddit Content Verifier API is running"}`.

### `POST /verify`
Main verification endpoint. Accepts a JSON body with:
- `url`: The URL of the Reddit post or linked article
- `title`: Post title
- `subtext`: Post body text (first 300 characters)
- `postDate`: Post timestamp (ISO format or relative time)

Returns a JSON response with:
- `is_correct`: `true`, `false`, or `null` (unable to verify)
- `explanation`: Human-readable explanation
- `sources`: Array of source objects with `source_url` and `source_description`
- `status`: Always `"success"`

The endpoint checks MongoDB cache first, and only calls the MCP agent if no cached result exists.
