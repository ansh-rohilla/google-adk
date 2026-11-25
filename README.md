# Google ADK Playground

A hands-on collection of agents, tool integrations, MCP servers, and session-management demos built with the **Google Agent Development Kit (ADK)**.

---

## Repository Structure

```text
google-adk/
├── ansh_bot/                  # Basic LiteLLM (OpenAI GPT-4o) agent with generation config
├── google_agent/              # Gemini agent with built-in Google Search
├── tavily_search_agent/       # Third-party Tavily Search wrapped via LangchainTool
├── world_clock_agent/         # Custom Python function tool using zoneinfo
├── code_exec_agent/           # Agent using ADK's BuiltInCodeExecutor
├── combined_tool_agent/       # Built-in search + Tavily + custom function + code execution
├── structured_output_agent/   # Pydantic schema extraction (output_schema & output_key)
├── mcp_agent/                 # Filesystem MCP (stdio) + GitHub MCP (Streamable HTTP)
├── coding_agent/              # Coding agent with filesystem, custom safe-shell & GitHub MCPs
│   ├── servers/shell_server.py
│   └── workspace/
├── session_runner_demo/       # Runner + InMemorySessionService CLI demo
│   ├── run_agent.py
│   └── session_agent/
└── runner_chatbot_demo/       # Persistent Streamlit chatbot with SQLite DatabaseSessionService
    ├── app.py
    ├── chat_service.py
    └── chatbot_agent/
```

---

## Projects Overview

### 1. Core Agents & Tools

| Directory | Model | Highlights |
| :--- | :--- | :--- |
| [`ansh_bot/`](ansh_bot/agent.py) | `openai/gpt-4o` (via `LiteLlm`) | Multi-provider LLM usage and `GenerateContentConfig` (`max_output_tokens`, `temperature`, `top_p`). |
| [`google_agent/`](google_agent/agent.py) | `gemini-3.5-flash` | Uses ADK's built-in `google_search` tool for live web search. |
| [`tavily_search_agent/`](tavily_search_agent/agent.py) | `gemini-3.5-flash` | Wraps LangChain's `TavilySearch` (`langchain-tavily`) using ADK's `LangchainTool`. |
| [`world_clock_agent/`](world_clock_agent/agent.py) | `gemini-3.5-flash` | Custom function tool (`get_current_time`) converting IANA timezones via `zoneinfo`. |
| [`code_exec_agent/`](code_exec_agent/agent.py) | `gemini-3.5-flash` | Enables server-side Python execution with `BuiltInCodeExecutor`. |
| [`combined_tool_agent/`](combined_tool_agent/agent.py) | `gemini-3.5-flash` | Combines `google_search`, `TavilySearch`, `get_current_time`, and `BuiltInCodeExecutor` in one agent. |

### 2. Structured Outputs

- **[`structured_output_agent/`](structured_output_agent/agent.py)**: Defines a Pydantic `Enquiry` model (`name`, `email`, `interested_in`, `budget_inr`) and configures `output_schema=Enquiry` and `output_key="enquiry"` to extract structured student enquiry data without guessing missing fields.

### 3. MCP (Model Context Protocol) Integrations

- **[`mcp_agent/`](mcp_agent/agent.py)** (`github_publisher`):
  - Connects to `@modelcontextprotocol/server-filesystem` over stdio, scoped to [`mcp_agent/files/`](mcp_agent/files/).
  - Connects to GitHub's remote MCP server (`https://api.githubcopilot.com/mcp/`) via `StreamableHTTPConnectionParams` using `GITHUB_TOKEN`.

- **[`coding_agent/`](coding_agent/agent.py)**:
  - **Filesystem MCP**: Scoped to `WORKSPACE_DIR` (defaults to `coding_agent/workspace/`) for listing, reading, creating, and editing files.
  - **Safe Shell MCP** ([`coding_agent/servers/shell_server.py`](coding_agent/servers/shell_server.py)): Custom stdio MCP server that runs commands with `shell=False` and strict allowlisting:
    - Allowed programs: `python`, `pytest`, `pip`, `git` (blocks `git push/remote/config/reset/clean/rebase`, `pip uninstall/download`, pipes, redirects, and chaining).
    - Background FastAPI/Uvicorn lifecycle tools (`start_server`, `stop_server`, `server_logs`, `check_url`) serving on `http://127.0.0.1:8001` (leaving port `8000` free for `adk web`).
    - Approval policy (`shell_needs_confirmation`): auto-approves `pytest`, `python -m pytest`, `git status`, `git diff`, and `git log`; prompts for other commands and server starts.
  - **GitHub MCP (optional)**: Enabled when `GITHUB_PAT` is set—splits tools into auto-approved read tools and confirmation-gated write tools (`create_repository`, `create_branch`, `push_files`, `create_pull_request`, `add_issue_comment`).

### 4. ADK Internals: Runners & Sessions

- **[`session_runner_demo/`](session_runner_demo/run_agent.py)**: Demonstrates creating sessions and running turns programmatically with `Runner` and `InMemorySessionService`, illustrating context retention within a session and isolation across separate sessions.
- **[`runner_chatbot_demo/`](runner_chatbot_demo/app.py)**: A multi-chat Streamlit app backed by [`chat_service.py`](runner_chatbot_demo/chat_service.py) using `Runner` + `DatabaseSessionService` (`sqlite+aiosqlite:///./sessions.db`) to persist conversations, auto-generate chat titles from the first message, and switch between past chats.

---

## Prerequisites

- **Python 3.12+**
- **Node.js & `npx`** (required for `@modelcontextprotocol/server-filesystem` in `mcp_agent` and `coding_agent`)

Key Python dependencies used across the modules:

```bash
pip install google-adk python-dotenv litellm langchain-tavily pydantic mcp streamlit aiosqlite fastapi uvicorn
```

---

## Configuration

Each agent directory loads its own `.env` file (automatically handled by `adk web` / `adk run`, or via `load_dotenv(...)` in standalone scripts). Set the keys needed for the agent you want to run:

| Variable | Used By | Purpose |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Gemini-based agents | Google Gemini API authentication |
| `GOOGLE_GENAI_USE_ENTERPRISE` | All agents | Set `FALSE` for Google AI Studio or configure for enterprise/Vertex |
| `OPENAI_API_KEY` | `ansh_bot` | OpenAI access via `LiteLlm` |
| `TAVILY_API_KEY` | `tavily_search_agent`, `combined_tool_agent` | Tavily web search API |
| `GITHUB_TOKEN` | `mcp_agent` | GitHub MCP server bearer token |
| `GITHUB_PAT` | `coding_agent` (optional) | Enables GitHub read/write MCP tools |
| `WORKSPACE_DIR` | `coding_agent` (optional) | Custom workspace path (defaults to `coding_agent/workspace`) |

---

## Running the Projects

Activate your virtual environment first:

```bash
source .venv/bin/activate
```

### Run ADK Agents (Web UI or CLI)

From the repository root, launch the ADK web interface and pick any agent from the dropdown:

```bash
adk web
```

Or run a specific agent directly in the terminal:

```bash
adk run google_agent
```

### Run the Session Runner Demo

```bash
cd session_runner_demo
python run_agent.py
```

### Run the Persistent Streamlit Chatbot

```bash
cd runner_chatbot_demo
streamlit run app.py
```

### Test the Safe-Shell MCP Server Directly

```bash
python coding_agent/servers/shell_server.py --root /absolute/path/to/coding_agent/workspace
```
