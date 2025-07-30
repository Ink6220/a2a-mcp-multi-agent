# Migration to Unified LiteLLM Agent System

This document summarizes the major refactoring of the A2A MCP framework to use a unified agent system powered by LiteLLM.

## Overview

The framework has been migrated from having separate agent implementations for different providers (`A2ANovaAgent`, `A2AOpenaiAgent`) to a unified system where all providers are handled through LiteLLM integration modules.

**UPDATE:** The framework has also been enhanced with sophisticated MCP tool server management capabilities, allowing for configuration-driven tool server loading and per-agent MCP server specification.

## Key Changes

### 1. New Integration Modules

Created provider-specific integration modules that handle LiteLLM configuration:

- **`aws_integration.py`** - AWS Bedrock models (Nova, Claude on Bedrock, etc.)
- **`openai_integration.py`** - OpenAI models (GPT-4, GPT-3.5, etc.)
- **`anthropic_integration.py`** - Anthropic models (Claude 3 series)
- **`google_integration.py`** - Google models (Gemini series)

Each integration module:
- Validates required environment variables
- Converts model names to LiteLLM format
- Provides setup validation and error messages

### 2. Refactored A2AAgentSelector

The `A2AAgentSelector` now:
- Automatically detects provider from agent card
- Loads appropriate integration module
- Validates environment setup
- Creates unified agent with LiteLLM model string
- Provides clear error messages for missing credentials

### 3. Unified Agent Implementation

- **Removed**: `A2ANovaAgent` (no longer needed)
- **Modified**: `A2AOpenaiAgent` is now provider-agnostic through LiteLLM
- **Enhanced**: `BaseAgent` now accepts a separate `litellm_model` parameter to preserve original model names
- **Result**: Single agent implementation works with all providers while maintaining model traceability

### 4. Model Name Preservation

The system now preserves both the original model name and the LiteLLM-formatted model string:

- **`model_name`**: Original model name from agent card (e.g., "amazon.nova-lite-v1:0")
- **`litellm_model`**: LiteLLM-formatted string for API calls (e.g., "bedrock/amazon.nova-lite-v1:0")

This approach ensures:
- Original model information is preserved for logging and tracking
- LiteLLM gets the correctly formatted model string for API calls
- No data loss during provider abstraction

### 5. Updated Agent Cards

Agent cards now specify providers like:
```json
{
  "provider": {
    "organization": "aws"
  },
  "modelName": "amazon.nova-lite-v1:0"
}
```

The selector automatically converts this to the appropriate LiteLLM format.

## Benefits

1. **Simplified Architecture**: One agent implementation instead of multiple
2. **Easy Provider Switching**: Change provider by modifying agent card only
3. **Extensible**: Add new providers by creating integration modules
4. **Better Error Handling**: Clear validation and setup messages
5. **Consistent Interface**: Same API regardless of underlying provider

## Migration Path

### For Existing Agent Cards
- No changes needed to existing OpenAI agent cards
- AWS agent cards should use `"organization": "aws"` in provider
- Model names are automatically converted to LiteLLM format

### For Developers
- Use `A2AAgentSelector` instead of directly instantiating agent classes
- Agent selection is now automatic based on provider configuration
- All agents use the same interface regardless of provider

## New Files Created

- `src/a2a_mcp/common/base_agent/aws_integration.py`
- `src/a2a_mcp/common/base_agent/openai_integration.py`
- `src/a2a_mcp/common/base_agent/anthropic_integration.py`
- `src/a2a_mcp/common/base_agent/google_integration.py`
- `agent_cards/test_aws_agent.json` (example AWS agent card)
- `demo_unified_agents.py` (demonstration script)

## Files Modified

- `src/a2a_mcp/common/base_agent/a2a_agent_selector.py` (major refactor)
- `src/a2a_mcp/common/base_agent/a2a_openai_agent.py` (minor updates)
- `src/a2a_mcp/common/base_agent/README.md` (added documentation)
- `unit_tests/test_invoke_protocol_compliance/sample_test.py` (updated for new system)

## Files Removed

- `src/a2a_mcp/common/base_agent/a2a_nova_agent.py` (replaced by unified system)

## Testing

The migration includes comprehensive testing focused on OpenAI and AWS providers:

### Updated Test Suite (`sample_test.py`)
- **Focused Testing**: Now specifically tests OpenAI and AWS agents
- **Dual Provider Support**: Tests both providers when environment variables are available
- **Model Preservation Verification**: Shows both original and LiteLLM model names
- **Flexible Agent Creation**: `create_test_agent()` can prefer specific providers
- **Comprehensive Coverage**: Includes both simple functionality tests and full compliance/behavior tests

### New Comparison Test (`test_openai_vs_aws.py`)
- **Side-by-Side Testing**: Compares OpenAI and AWS agents with identical queries
- **Environment Detection**: Automatically detects available providers
- **Detailed Output**: Shows model information and response details for both providers
- **Multiple Query Testing**: Tests agents with various types of queries

### Test Features
- **Automatic Fallback**: Tests run with whatever providers are available
- **Clear Output**: Shows original model names vs LiteLLM-formatted strings
- **Error Handling**: Graceful handling when providers are unavailable
- **Comprehensive Reporting**: Detailed success/failure reporting for each provider

## Environment Variables

The system now validates the following environment variables:

- **OpenAI**: `OPENAI_API_KEY`
- **AWS**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`
- **Anthropic**: `ANTHROPIC_API_KEY`
- **Google**: `GOOGLE_API_KEY`

## Usage Example

```python
from src.a2a_mcp.common.base_agent.a2a_agent_selector import A2AAgentSelector

# Create agent card with desired provider
agent_card = CustomAgentCard(
    provider=AgentProvider(organization="aws"),
    modelName="amazon.nova-lite-v1:0",  # Original model name preserved
    # ... other properties
)

# Agent selector automatically handles provider setup
selector = A2AAgentSelector(agent_card, card_discovery, mcp_server)
agent = selector.get_agent()

# Agent now has both model names available:
print(f"Original model: {agent.model_name}")          # "amazon.nova-lite-v1:0"
print(f"LiteLLM model: {agent.litellm_model}")        # "bedrock/amazon.nova-lite-v1:0"

# Same interface regardless of provider
result = await agent.invoke(query, context_id, task_id, context)
```

This migration makes the framework more maintainable, extensible, and user-friendly while preserving all existing functionality. 

## Recent Enhancements (MCP Server Management)

### 1. Sophisticated MCP Tool Server Management

Added a new `MCPToolServerManager` class that provides:

- **Configuration-driven server loading** from `mcp_config.json`
- **Per-agent MCP server specification** via `mcp_servers` field in agent cards
- **Proper resource management** using AsyncExitStack
- **Graceful error handling** for missing or failed servers

### 2. Enhanced Agent Cards

Agent cards now support an additional `mcp_servers` field:
```json
{
  "name": "Airbnb Agent",
  "provider": {
    "organization": "openai"
  },
  "modelName": "gpt-4.1-mini",
  "mcp_servers": ["airbnb"]
}
```

This allows each agent to specify which MCP tool servers it needs.

### 3. Cleaned MCP Server Implementation

- **Removed hardcoded tools** from `src/a2a_mcp/mcp/server.py`
- **Simplified server** to focus only on agent card discovery
- **External tool servers** now managed through configuration

### 4. Configuration-Based MCP Servers

Added `src/a2a_mcp/common/base_mcp/mcp_config.json` with server definitions:
```json
{
  "mcpServers": {
    "airbnb": {
      "command": "npx",
      "args": ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
    },
    "wikipedia": {
      "command": "wikipedia-mcp",
      "args": ["--transport", "stdio", "--language", "en"]
    }
  }
}
```

### 5. Enhanced Agent Launcher

The agent launcher (`src/a2a_mcp/agents/__main__.py`) now:
- Uses `AsyncExitStack` for proper resource management
- Loads tool servers based on agent card specifications
- Combines discovery server with tool servers
- Provides better logging and error handling

## Combined Benefits

The system now provides:

1. **Unified LiteLLM Agent System**: Single agent implementation for all providers
2. **Sophisticated MCP Management**: Configuration-driven tool server loading
3. **Per-Agent Tool Specification**: Each agent can specify its required tools
4. **Clean Architecture**: Separation between agent discovery and tool provision
5. **Proper Resource Management**: AsyncExitStack ensures clean shutdown
6. **Backward Compatibility**: Existing agent cards continue to work 