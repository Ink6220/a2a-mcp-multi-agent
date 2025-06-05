# A2A MCP Boilerplate

**A boilerplate project for building Agent-to-Agent (A2A) applications using Model Context Protocol (MCP).**

## Overview

This boilerplate provides a foundation for creating multi-agent systems where:
- Agents discover each other through MCP
- Agents communicate using the A2A protocol
- MCP serves as a registry for agent cards and tools

## Quick Start

### Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### Running the MCP Server

```bash
# Start MCP server (default port 10100)
uv run a2a-mcp --run mcp-server --transport sse
```

### Running Agents

```bash
# Start orchestrator agent
uv run src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101

# Start planner agent (in another terminal)
uv run src/a2a_mcp/agents/ --agent-card agent_cards/planner_agent.json --port 10102
```

## Project Structure

```
.
├── src/a2a_mcp/           # Main source code
│   ├── agents/            # Agent implementations
│   ├── mcp/              # MCP server and client
│   └── common/           # Shared utilities
├── agent_cards/          # Agent configuration files
└── pyproject.toml        # Project dependencies
```

## Configuration

- Modify `agent_cards/*.json` to configure your agents
- Update `pyproject.toml` to add/remove dependencies
- Customize agents in `src/a2a_mcp/agents/`

## Development

This boilerplate includes:
- MCP server for agent discovery
- A2A protocol implementation
- Base agent classes
- Configuration management
- Common utilities

## Next Steps

1. Define your agent cards in `agent_cards/`
2. Implement your agent logic in `src/a2a_mcp/agents/`
3. Add custom tools and resources to the MCP server
4. Test agent interactions

For more details on A2A and MCP protocols, refer to the official documentation.
