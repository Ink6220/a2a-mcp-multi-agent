# A2A Agent Server Launcher

This script launches an individual agent server designed to operate within an Agent-to-Agent (A2A) Multi-Agent Control Plane (MCP) ecosystem. It initializes a specific agent based on a provided configuration ("agent card"), connects to an MCP server for discovery and communication, and serves the agent's capabilities over HTTP using a Starlette application.

## Features

*   **Dynamic Agent Loading**: Loads agent configurations from JSON "agent card" files.
*   **MCP Integration**: Connects to an A2A MCP server (via Server-Sent Events - SSE) for:
    *   Registering the agent.
    *   Discovering other agents in the network.
*   **Agent Selection**: Uses `A2AAgentSelector` to instantiate the correct agent implementation based on the agent card.
*   **Custom System Prompts**: Allows assignment of specific system prompts to known agent types (e.g., "Presale Agent", "PromoAdvisor Agent").
*   **Task Management**: Integrates with `MemoryManagement` for storing task-related data.
*   **A2A Protocol Compliance**: Uses `A2AStarletteApplication` and `DefaultRequestHandler` to handle A2A requests.
*   **Tool Filtering**: Supports allowlisting (`--include-tools`) and denylisting (`--exclude-tools`) for tools the agent can use/expose.
*   **Configurable**: CLI options for host, port, agent card path, MCP URL, and tool filters.
*   **Environment Variable Loading**: Loads settings from a `.env` file.
*   **Asynchronous Operations**: Leverages `asyncio` for efficient network I/O.

## Prerequisites

*   Python 3.13+ (with `asyncio` support)
*   Required Python packages (install via `pip` or your preferred package manager):
    *   `click`
    *   `httpx`
    *   `uvicorn`
    *   `python-dotenv`
    *   The `a2a` library (specifically `a2a.server.*`)
    *   The `a2a_mcp` library (specifically `a2a_mcp.common.*`)
*   A running A2A MCP server accessible at the specified `--mcp-url`.
*   Agent card JSON files (e.g., `presale_agent.json`).
*   (Optional) A `.env` file in the script's root directory for environment variables.

## Configuration

### 1. Agent Card (`--agent-card <path_to_json>`)

This is a **required** JSON file that defines the properties of the agent being launched. It should conform to the `CustomAgentCard` schema from `a2a_mcp.common.types`.

Example (conceptual structure of `presale_agent.json`):
```json
{
  "name": "Presale Agent",
  "description": "Handles presale inquiries and product information.",
  "version": "1.0.0",
  "defaultInputModes": ["text/plain"],
  "systemPrompt": "You are a helpful presale assistant..." // Can be overridden by the script
  // ... other CustomAgentCard fields
}
```
**Note**: The script currently has a `TODO` to improve how system prompts are loaded. For "Presale Agent" and "PromoAdvisor Agent", it hardcodes specific prompts (`PRESALE_PROMPT`, `PROMO_ADVISOR_PROMPT`) from `a2a_mcp.common.prompts`.

### 2. MCP URL (`--mcp-url <url>`)

The URL of the A2A MCP server's Server-Sent Events (SSE) endpoint.
Default: `http://localhost:8000/sse`

### 3. Tool Filtering
*   `--include-tools <tool_name>`: (Multiple allowed) Specifies a list of tool names that this agent is allowed to use or expose. If provided, only these tools will be considered.
    Default: `("save_log_customer",)`
*   `--exclude-tools <tool_name>`: (Multiple allowed) Specifies a list of tool names that this agent should *not* use or expose. This acts as a denylist.

### 4. Environment Variables (`.env`)
The script uses `python-dotenv` to load environment variables from a `.env` file. While this script itself doesn't explicitly depend on specific environment variables for its core launching logic, the underlying agent implementations or libraries it uses (like `a2a` or `a2a_mcp`) might.

## How It Works

1.  **CLI Parsing**: The `main()` function uses `click` to parse command-line arguments.
2.  **Initialization (`init_agent_server`)**:
    *   Loads the specified `CustomAgentCard` from the JSON file.
    *   Establishes an asynchronous connection to the MCP server using `FilteredMCPServerSse`. This connection is kept alive to receive updates and maintain presence.
    *   Uses `A2ACardDiscovery` to discover other available agents through the connected MCP.
    *   Initializes `MemoryManagement` for task state.
    *   Calls `get_agent()` to instantiate the agent:
        *   If the agent name matches "Presale Agent" or "PromoAdvisor Agent", it assigns a predefined system prompt. (See `TODO` in code).
        *   Uses `A2AAgentSelector` to select and return the appropriate agent instance based on the `agent_card`.
    *   Wraps the agent in a `BaseAgentExecutor`.
    *   Sets up a `DefaultRequestHandler` (from `a2a.server`) to process incoming A2A requests, using the agent executor and task store.
    *   Creates an `A2AStarletteApplication` (from `a2a.server`) with the agent card and request handler.
3.  **Server Launch**:
    *   The `run_uvicorn` function is called in a separate daemon thread to start the Uvicorn ASGI server, which serves the Starlette application. This allows the main thread to continue.
4.  **MCP Connection Maintenance**: The main `asyncio` event loop in `init_agent_server` runs a `while True: await asyncio.sleep(1)` loop. This keeps the script alive and, crucially, maintains the asynchronous context for the `FilteredMCPServerSse` connection to the MCP.
5.  **Shutdown**: On `KeyboardInterrupt` (Ctrl+C), the script initiates a graceful shutdown, and the `async with FilteredMCPServerSse(...)` context manager handles closing the MCP connection.

## Usage

To run the agent server, execute the script from your terminal.

**General Syntax:**
```bash
python your_script_name.py --agent-card <path_to_agent_card.json> [OPTIONS]
```
(Replace `your_script_name.py` with the actual name of this Python file.)

Or, if using a runner like `uv`:
```bash
uv run path/to/your_script_name.py --agent-card <path_to_agent_card.json> [OPTIONS]
```

**CLI Options:**

*   `--host TEXT`: The host address to bind the server to. (Default: `localhost`)
*   `--port INTEGER`: The port number for the server. (Default: `10000`)
*   `--agent-card TEXT`: **Required.** Path to the agent card JSON file.
*   `--mcp-url TEXT`: URL of the MCP server's SSE endpoint. (Default: `http://localhost:8000/sse`)
*   `--include-tools TEXT`: Tool name to include (allowlist). Can be specified multiple times. (Default: `save_log_customer`)
*   `--exclude-tools TEXT`: Tool name to exclude (denylist). Can be specified multiple times.

**Example Command (from the script comments):**
This example assumes the script is located within a `src/a2a_mcp/agents/` directory structure and is being run with `uv`.

```bash
uv run src/a2a_mcp/agents/your_script_name.py \
    --port 10000 \
    --agent-card agent_cards/presale_agent.json \
    --mcp-url http://localhost:8000/sse \
    --include-tools save_log_customer \
    --include-tools check_car_brand \
    --include-tools data_car_insurance_2 \
    --include-tools data_other_insurance
```
This command would:
*   Start an agent server on port `10000`.
*   Load the agent definition from `agent_cards/presale_agent.json`.
*   Connect to an MCP server at `http://localhost:8000/sse`.
*   Specifically include the tools: `save_log_customer`, `check_car_brand`, `data_car_insurance_2`, and `data_other_insurance`.

## Error Handling

The script includes basic error handling for:
*   Missing agent card file.
*   Invalid JSON in the agent card file.
*   Other general exceptions during server startup.
Errors are logged to the console, and the script will exit with a non-zero status code upon failure.

## TODOs & Notes

*   **System Prompt Loading**: The `get_agent` function has a `TODO` comment:
    > `TODO: add systemprompt instruction into agent_card based on agent name, due to load agent card from .json -> cannot directly passing prompt and connot write multiple line of string into systemPrompt.`
    This indicates a plan to improve how system prompts are defined and loaded, potentially directly from the agent card JSON or a more flexible mechanism rather than hardcoding.
*   **Threaded Uvicorn**: The Uvicorn server runs in a separate thread. This is a common pattern for running ASGI servers within scripts that also need to manage other long-running tasks (like the MCP connection).
