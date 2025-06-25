## Quick start on testing agent

## Overview 

-The testing framwork there are 3 agents which are guide, plan and recommend

-guide works as main agent that will keep asking user question until condition are fullfill then it will send to plan agent to finish

-recommend agent works as agent that will recommend/search for informaiton that user might want or need

##

```bash
# Start MCP server (default port 8000)
uv run a2a-mcp --run temp-mcp-server --transport sse
```

### Running Agents

```bash
# Start guide agent
uv run src/a2a_mcp/agents/ --agent-card agent_cards/guide_agent.json --port 10110 --include-tools NONE    

# Start plan agent (in another terminal)
 uv run src/a2a_mcp/agents/ --agent-card agent_cards/plan_agent.json --port 10102 --include-tools NONE  

 # Start recommend agent (in another terminal)
 uv run src/a2a_mcp/agents/ --agent-card agent_cards/recommend_agent.json --port 10103 --include-tools search_serpapi --include-tools search_flights_tool  
```

### Running the CLI
```bash
# Navigate to the CLI sample directory:
cd hosts\cli

#run cli
uv run . --agent http://localhost:10110    
```