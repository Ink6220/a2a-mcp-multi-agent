#!/usr/bin/env python3
"""
Sample Test Runner for all A2A Agent Types
Tests both A2A protocol compliance and LLM behavior for all valid agents in base_agent

Usage:
    python sample_test.py
"""

import asyncio
import sys
import os
from typing import Dict, Any, List, Tuple
from uuid import uuid4

# Extend path to nested test subfolders
base_dir = os.path.dirname(__file__)
sys.path.append(os.path.join(base_dir, 'test_invoke_return_type'))
sys.path.append(os.path.join(base_dir, 'test_llm_invoke_behaviour'))

# Add project root for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.a2a_mcp.common.base_agent.a2a_openai_agent import A2AOpenaiAgent
from src.a2a_mcp.common.base_agent.a2a_openai_agent_native import A2AOpenaiAgentNative
from src.a2a_mcp.common.base_agent.a2a_nova_agent import A2ANovaAgent
from src.a2a_mcp.common.types import CustomAgentCard
from src.a2a_mcp.common.card_discovery import A2ACardDiscovery
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report  # type: ignore
from test_llm_behavior import LLMBehaviorTester, print_behavior_report  # type: ignore
from a2a.types import AgentProvider, AgentCapabilities, AgentSkill

# --- Agent Type Registry ---
AGENT_TYPES = [
    {
        "name": "A2AOpenaiAgent",
        "class": A2AOpenaiAgent,
        "env_check": lambda: bool(os.getenv("OPENAI_API_KEY")),
        "model_name": "gpt-4.1-mini",
        "provider": {"organization": "openai", "url": "None"},
    },
    {
        "name": "A2AOpenaiAgentNative",
        "class": A2AOpenaiAgentNative,
        "env_check": lambda: bool(os.getenv("OPENAI_API_KEY")),
        "model_name": "gpt-4.1-mini",
        "provider": {"organization": "openai", "url": "None"},
    },
    {
        "name": "A2ANovaAgent",
        "class": A2ANovaAgent,
        "env_check": lambda: all([
            os.getenv("AWS_CLIENT_TYPE"),
            os.getenv("AWS_REGION_NAME"),
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
        ]),
        "model_name": "anthropic.claude-3-sonnet-20240229-v1:0",
        "provider": {"organization": "aws", "url": "None"},
    },
]

# --- Agent Card Factory ---
def create_agent_card(agent_type: dict) -> CustomAgentCard:
    """Create a CustomAgentCard for the given agent type."""
    return CustomAgentCard(
        name=f"Test {agent_type['name']}",
        description=f"Test agent for protocol compliance ({agent_type['name']})",
        url="http://localhost:10101/",
        provider=AgentProvider(
            organization=agent_type["provider"]["organization"],
            url=agent_type["provider"]["url"]
        ),
        version="1.0.0",
        documentationUrl=None,
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=True,
            stateTransitionHistory=False
        ),
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        skills=[
            AgentSkill(
                id="tester",
                name="Protocol Tester",
                description="Tests A2A protocol compliance",
                tags=["test", "protocol"],
                examples=["Test the protocol compliance"],
                inputModes=None,
                outputModes=None
            )
        ],
        modelName=agent_type["model_name"],
        systemPrompt="""You are a test agent that validates A2A protocol compliance.

## DISCOVERY
Available agents:
- test-agent-1: A simple test agent for basic tasks
- test-agent-2: A more complex test agent for advanced tasks

## ACTION SPACE
## ACTION SPACE
[1] call_next_agent
  Description: Delegate tasks to one or more agents that are available in DISCOVERY. Tasks can be delegated in parallel.
  Parameters:
    - agent_names (list[str]): List of agent names to delegate tasks to.
    - next_agent_instructions (list[str]): List of instructions for each agent, must match length of agent_names.
    - artifacts (str): Optional structured JSON data to be passed as artifacts; must be JSON-serializable.

  Example (Single Agent):
  {
    "action": "call_next_agent",
    "status": "input_required",
    "message": "I will delegate this task to the Sales Agent",
    "agent_names": ["Sales Agent"],
    "next_agent_instructions": ["Please handle the customer inquiry about pricing"],
    "artifacts": null
  }

  Example (Multiple Agents):
  {
    "action": "call_next_agent",
    "status": "input_required",
    "message": "I will delegate tasks to both the Sales and Support agents",
    "agent_names": ["Sales Agent", "Support Agent"],
    "next_agent_instructions": [
      "Calculate the pricing for this customer",
      "Check if there are any technical limitations"
    ],
    "artifacts": null
  }

[2] answer
  Description: Answer the question with current knowledge or using tools (if available).
  Parameters:
    - message (str): Final answer to the question

[3] status
  Description: This status is used to indicate the completeness of the task, takes in a string, if task is delegated to another agent, status should be input_required
  Parameters:
    status: Literal[\"input_required\", \"completed\", \"failed\"]

Your task is to respond to queries in a way that tests different aspects of the A2A protocol:
1. Basic answers with completed status
2. Delegation to other agents
3. Input required scenarios
4. Error handling

Make sure your responses follow the XML schema:
<o>
    <action>answer|call_next_agent</action>
    <status>input_required|completed|error|hang_up</status>
    <custom_status></custom_status>
    <agent_name></agent_name>
    <message>Your message here</message>
    <next_agent_instruction></next_agent_instruction>
    <next_agent_schema></next_agent_schema>
</o>""",
        nextAgent=["http://localhost:10002/", "http://localhost:10001/"]
    )

def create_test_agent():
    """Return a standard OpenAI agent instance with a mock agent card for testing."""
    agent_type = {
        "name": "A2AOpenaiAgent",
        "class": A2AOpenaiAgent,
        "model_name": "gpt-4.1-mini",
        "provider": {"organization": "openai", "url": "None"},
    }
    agent_card = create_agent_card(agent_type)
    card_discovery = A2ACardDiscovery(agent_card=agent_card)
    return A2AOpenaiAgent(agent_card=agent_card, card_discovery=card_discovery)

# --- Environment Check Helper ---
def get_available_agent_types() -> List[dict]:
    """Return a list of agent types with required env vars present."""
    available = []
    for agent_type in AGENT_TYPES:
        if agent_type["env_check"]():
            available.append(agent_type)
        else:
            print(f"⚠️  Skipping {agent_type['name']} (missing required environment variables)")
    return available

async def test_agent(agent_type: dict) -> Tuple[str, bool]:
    """Test a single agent type. Returns (agent_name, passed)."""
    print(f"\n🧪 Testing {agent_type['name']}")
    print("="*50)
    # Create agent card and discovery
    agent_card = create_agent_card(agent_type)
    card_discovery = A2ACardDiscovery(agent_card=agent_card)
    # Instantiate agent
    agent = agent_type["class"](agent_card=agent_card, card_discovery=card_discovery)
    # Run compliance test
    print("\n📋 Running A2A Protocol Compliance Test...")
    compliance_results = await A2AComplianceTester.test_agent_invoke_compliance(agent)
    print_compliance_report(compliance_results)
    # Run behavior test
    print("\n🤖 Running LLM Behavior Test...")
    behavior_results = await LLMBehaviorTester.test_llm_behavior(agent)
    print_behavior_report(behavior_results)
    passed = (
        compliance_results.get('status') == 'PASSED' and 
        behavior_results.get('status') == 'PASSED'
    )
    return (agent_type['name'], passed)

async def main():
    available_agents = get_available_agent_types()
    if not available_agents:
        print("❌ No valid agent types found with required environment variables. Exiting.")
        return
    results = []
    for agent_type in available_agents:
        try:
            agent_name, passed = await test_agent(agent_type)
            results.append((agent_name, passed))
        except Exception as e:
            print(f"❌ Exception while testing {agent_type['name']}: {e}")
            results.append((agent_type['name'], False))
    # Print summary
    print("\n=== Test Summary ===")
    for agent_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{agent_name}: {status}")
    all_passed = all(passed for _, passed in results)
    if all_passed:
        print("\n🎉 All available agent types PASSED!")
    else:
        print("\n⚠️  Some agent types FAILED. See above for details.")

if __name__ == "__main__":
    asyncio.run(main()) 