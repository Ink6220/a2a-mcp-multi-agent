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

### Env.sample
```bash
OPENAI_API_KEY=
```
```bash
AWS_CLIENT_TYPE=
AWS_REGION_NAME=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

### Running the MCP Server

```bash
# Start MCP server (default port 8000)
uv run a2a-mcp --run mcp-server --transport sse
```

### Running Agents

```bash
# Start orchestrator agent
uv run src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101

# Start presale agent (in another terminal)
uv run src/a2a_mcp/agents/ --agent-card agent_cards/presale_agent.json --port 10001
```

### Running the CLI
```bash
# Navigate to the CLI sample directory:
cd hosts\cli

# for example --agent http://localhost:10000. More command line options are documented in the source code.
uv run . --agent [url-of-your-a2a-server]
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

### Agent configuration and Switching
Currently support 2 provider (Openai and Amazon Nova invoke capability). You can change model and configuration (e.g model_name, skill, description) via agent_card.json.
Here is an example choosing Openai agent (gpt-4.1-mini) as a Presale Agent role
[read more about agent_card](https://a2aproject.github.io/A2A/specification/#55-agentcard-object-structure)

**Navigate to agent_cards/** 
1. Create a new JSON file named using the following convention: `<agent_name>_agent.json`
    - Create your `agent_cards/presale_agent.json`
    - The <agent_name> should be lowercase, use underscores (_) to separate words, and reflect the primary function or role of the agent.
2. Update **organization='openai'** and **modelName="gpt-4.1-mini"**
3. Update **name='Presale Agent'**, this agent name (descriptive name related to this agent capability and skill)
4. Update **url**, url and port to be deployed
5. Update **systemPrompt=""**, which can be update later inside **agent_class/\_\_main\_\_.py**
6. Update **description="your-agent-description"**, this will help other agent understand this agent role and when to call this agent
7. Update **skills**, helps to briefly explain agent's tool as skill that this agent can do.
8. Update **nextAgent**, define the list of agents this agent can communicate with using the nextAgent field. Provide the URLs of those agents:
```json
{
    "name": "Presale Agent",
    "description": "Initiate contact, qualify customer availability. Only call this agent to ask for availability only, otherwise call other agent. Input format: {{user_question}}",
    "url": "http://localhost:10001/",
    "provider": {
        "organization": "openai",
        "url":"None"
    },
    "version": "1.0.0",
    "documentationUrl": null,
    "capabilities": {
        "streaming": "True",
        "pushNotifications": "True",
        "stateTransitionHistory": "False"
    },
    "authentication": {
        "credentials": null,
        "schemes": [
            "public"
        ]
    },
    "defaultInputModes": [
        "text",
        "text/plain"
    ],
    "defaultOutputModes": [
        "text",
        "text/plain"
    ],
    "skills": [
        {
            "id": "greet_and_introduce",
            "name": "Greet and introduce the promotion",
            "description": "Helps Initiate contact to customer and qualify customer availability.",
            "tags": [
                "Greeting",
                "Asking customer availability"
            ],
            "examples": [
                "สวัสดี"
            ],
            "inputModes": null,
            "outputModes": null
        }
    ],
    "modelName":"gpt-4.1-mini",
    "systemPrompt": "",
    "nextAgent": ["http://localhost:10002/"]
}
```


### Customize your MCP Server
Navigate to **src/a2a_mcp/mcp/server.py**
```python
from mcp.server.fastmcp import FastMCP

def serve(host, port, transport):  # noqa: PLR0915
    """Initializes and runs the Agent Cards MCP server.

    Args:
        host: The hostname or IP address to bind the server to.
        port: The port number to bind the server to.
        transport: The transport mechanism for the MCP server (e.g., 'stdio', 'sse').
    """
    logger.info('Starting Agent Cards MCP Server')
    mcp = FastMCP('agent-cards', host=host, port=port)

    @mcp.tool()
    def your_tool_name(first_param: str, second_param: str) -> str:
        """This tool is for ...
    
        Args:
            first_param: description
            second_param: description
            
        """
    
        # customize your logic
        return "tool-result"
```


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
