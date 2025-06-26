#!/usr/bin/env python3
"""
Sample Test Runner for A2AOpenaiAgent
Tests both A2A protocol compliance and LLM behavior

Usage:
    python sample_test.py
"""

import asyncio
import sys
import os
from typing import Dict, Any, List
from uuid import uuid4

# Extend path to nested test subfolders
base_dir = os.path.dirname(__file__)
sys.path.append(os.path.join(base_dir, 'test_invoke_return_type'))
sys.path.append(os.path.join(base_dir, 'test_llm_invoke_behaviour'))

# Add project root for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.a2a_mcp.common.base_agent.a2a_openai_agent import A2AOpenaiAgent
from src.a2a_mcp.common.types import CustomAgentCard
from src.a2a_mcp.common.card_discovery import A2ACardDiscovery
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report  # type: ignore
from test_llm_behavior import LLMBehaviorTester, print_behavior_report  # type: ignore
from a2a.types import AgentProvider, AgentCapabilities, AgentSkill

def create_test_agent() -> A2AOpenaiAgent:
    """Create a test instance of A2AOpenaiAgent"""
    
    # Create agent card similar to orchestrator_agent.json
    agent_card = CustomAgentCard(
        name="Test Agent",
        description="Test agent for protocol compliance",
        url="http://localhost:10101/",
        provider=AgentProvider(
            organization="openai",
            url="None"
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
        modelName="gpt-4.1-mini",
        systemPrompt="""You are a test agent that validates A2A protocol compliance.

## DISCOVERY
Available agents:
- test-agent-1: A simple test agent for basic tasks
- test-agent-2: A more complex test agent for advanced tasks

## ACTION SPACE
[1] call_next_agent
  Description: Delegate the task to appropriate agent that are available in DISCOVERY.
  Parameters:
    - agent_name (str): Name of the agent responsible for the current response.
    - message (str): Message to another agent.

[2] answer
  Description: Answer the question with current knowledge or using tools (if available).
  Parameters:
    - message (str): Final answer to the question

[3] status
  Description: This status is used to indicate the completeness of the task, takes in a string, if task is delegated to another agent, status should be input_required
  Parameters:
    status: Literal["input_required", "completed", "failed"]

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

    # Create card discovery with agent card
    card_discovery = A2ACardDiscovery(agent_card=agent_card)

    # Create agent instance
    return A2AOpenaiAgent(agent_card=agent_card, card_discovery=card_discovery)

def setup_environment():
    """Set up environment variables for testing"""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key and try again:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)

async def main():
    """Main test function"""
    print("🧪 Testing A2AOpenaiAgent")
    print("="*50)
    
    # Set up environment
    setup_environment()
    
    # Create test agent
    agent = create_test_agent()
    
    # Run compliance test
    print("\n📋 Running A2A Protocol Compliance Test...")
    compliance_results = await A2AComplianceTester.test_agent_invoke_compliance(agent)
    print_compliance_report(compliance_results)
    
    # Run behavior test
    print("\n🤖 Running LLM Behavior Test...")
    behavior_results = await LLMBehaviorTester.test_llm_behavior(agent)
    print_behavior_report(behavior_results)
    
    return (
        compliance_results['status'] == 'PASSED' and 
        behavior_results['status'] == 'PASSED'
    )

if __name__ == "__main__":
    asyncio.run(main()) 