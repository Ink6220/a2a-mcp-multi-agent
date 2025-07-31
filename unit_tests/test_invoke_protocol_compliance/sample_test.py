#!/usr/bin/env python3
"""
Sample Test Runner for OpenAI and AWS A2A Agent Types
Tests both A2A protocol compliance and LLM behavior for OpenAI and AWS unified agents.

This test suite now focuses on:
- OpenAI agents (via OpenAI API through LiteLLM)
- AWS agents (via AWS Bedrock Nova through LiteLLM)

Usage:
    python sample_test.py

Environment Variables Required:
- For OpenAI: OPENAI_API_KEY
- For AWS: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME

The test will run with whatever providers are available based on environment variables.
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

from src.a2a_mcp.common.base_agent.a2a_agent_selector import A2AAgentSelector
from src.a2a_mcp.common.types import CustomAgentCard
from src.a2a_mcp.common.card_discovery import A2ACardDiscovery
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report  # type: ignore
from test_llm_behavior import LLMBehaviorTester, print_behavior_report  # type: ignore
from a2a.types import AgentProvider, AgentCapabilities, AgentSkill

# --- Agent Type Registry ---
AGENT_TYPES = [
    {
        "name": "OpenAI Unified Agent",
        "env_check": lambda: bool(os.getenv("OPENAI_API_KEY")),
        "model_name": "gpt-4.1-mini",
        "provider": {"organization": "openai", "url": "None"},
    },
    {
        "name": "AWS Unified Agent",
        "env_check": lambda: all([
            os.getenv("AWS_REGION_NAME"),
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
        ]),
        "model_name": "amazon.nova-lite-v1:0",
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

## CRITICAL DECISION RULES
Before choosing an action, ask yourself:
1. Am I responding directly to the user? → Use "answer"
2. Am I asking the user a question? → Use "answer" 
3. Am I reporting an error or failure? → Use "answer"
4. Am I delegating a task to another agent from DISCOVERY? → Use "call_next_agent"

## STRICT ACTION-STATUS PAIRING RULES
**THESE RULES ARE MANDATORY AND CANNOT BE VIOLATED:**

### Rule 1: call_next_agent = input_required ALWAYS
- If action is "call_next_agent" → status MUST be "input_required"
- You are NOT completing the task - you are waiting for another agent
- NEVER use status "completed" with "call_next_agent"

### Rule 2: answer + completed = YOU finished the task
- If action is "answer" and status is "completed" → YOU have fully resolved the user's request
- Use this ONLY when you provide the final answer yourself

### Rule 3: answer + input_required = YOU need more info from USER
- If action is "answer" and status is "input_required" → YOU need the USER to provide more information
- Use this when asking the user questions

### Rule 4: answer + failed = Error occurred
- If action is "answer" and status is "failed" → An error occurred
- Use this for error reporting

## ACTION SPACE

### [1] answer
**Use this action when:**
- Responding directly to the user
- Asking the user for more information
- Providing final answers or results
- Reporting errors, failures, or completion status
- ANY interaction with the user

**Parameters:**
- message (str): Your response to the user
- artifacts (str): Optional structured JSON data to be passed as artifacts; must be JSON-serializable.

**CORRECT Examples:**
```json
{
  "action": "answer",
  "status": "completed",
  "message": "Here's the information you requested...",
  "artifacts": null
}
```

```json
{
  "action": "answer", 
  "status": "input_required",
  "message": "Could you please provide more details about your request?",
  "artifacts": null
}
```

```json
{
  "action": "answer",
  "status": "failed", 
  "message": "I encountered an error while processing your request.",
  "artifacts": null
}
```

```json
{
  "action": "answer",
  "status": "completed",
  "message": "Here is your requested data.",
  "artifacts": "{\\"result\\": \\"success\\", \\"data\\": \\"mock_output\\"}"
}
```

### [2] call_next_agent
**Use this action ONLY when:**
- Delegating tasks to agents listed in DISCOVERY section above
- You have identified specific agents to handle the task
- You are NOT asking the user anything
- **CRITICAL: Status MUST ALWAYS be "input_required" - you are waiting for the other agent!**

**REQUIRED Parameters:**
- agent_names (list[str]): List of agent names from DISCOVERY (NEVER null, NEVER empty)
- next_agent_instructions (list[str]): Instructions for each agent (NEVER null, must match agent_names length)
- artifacts (str): Optional JSON data (can be null)

**CORRECT Examples:**
```json
{
  "action": "call_next_agent",
  "status": "input_required",
  "message": "I will delegate this task to test-agent-2",
  "agent_names": ["test-agent-2"],
  "next_agent_instructions": ["Please handle the customer inquiry about pricing"],
  "artifacts": null
}
```

```json
{
  "action": "call_next_agent",
  "status": "input_required", 
  "message": "I will delegate tasks to both agents",
  "agent_names": ["test-agent-1", "test-agent-2"],
  "next_agent_instructions": [
    "Calculate the pricing for this customer",
    "Check if there are any technical limitations"
  ],
  "artifacts": null
}
```

**FORBIDDEN Examples (NEVER DO THIS):**
```json
{
  "action": "call_next_agent",
  "status": "completed",  // ❌ WRONG! NEVER use "completed" with delegation
  "message": "Task delegated",
  "agent_names": ["test-agent-1"],
  "next_agent_instructions": ["Handle this"]
}
```

## VALIDATION CHECKLIST
Before responding, verify EVERY point:
- ✅ If action is "answer": Include message field, artifacts optional
- ✅ If action is "call_next_agent": Include agent_names (never null) and next_agent_instructions (never null, same length as agent_names)
- ✅ If action is "call_next_agent": Status MUST be "input_required" (NEVER "completed")
- ✅ If action is "answer" and status is "completed": I have fully resolved the user's request myself
- ✅ Status is one of: "input_required", "completed", "failed"
- ✅ Message explains what you're doing

## FINAL ACTION-STATUS CHECK
**Before submitting your response, ask yourself:**
- Am I delegating? → action="call_next_agent", status="input_required"
- Am I answering the user directly with final results? → action="answer", status="completed"  
- Am I asking the user for more info? → action="answer", status="input_required"
- Did an error occur? → action="answer", status="failed"

Your task is to respond to queries in a way that tests different aspects of the A2A protocol:
1. Basic answers with completed status
2. Delegation to other agents
3. Input required scenarios
4. Error handling

Set response status to input_required if the user needs to provide more information.
Set response status to failed if there is an error while processing the request.
Set response status to completed if the request is completed.""",
        nextAgent=["http://localhost:10002/", "http://localhost:10001/"]
    )

def create_test_agent(prefer_provider: str = "openai"):
    """Return an agent instance with a mock agent card for testing.
    
    Args:
        prefer_provider: Preferred provider ("openai" or "aws"). Falls back to available provider.
    """
    # Get available agent types
    available_types = get_available_agent_types()
    
    if not available_types:
        raise RuntimeError("No agent types available with required environment variables")
    
    # Try to find the preferred provider
    preferred_type = None
    for agent_type in available_types:
        if agent_type["provider"]["organization"] == prefer_provider:
            preferred_type = agent_type
            break
    
    # If preferred provider not available, use the first available one
    if not preferred_type:
        preferred_type = available_types[0]
        print(f"⚠️  Preferred provider '{prefer_provider}' not available, using '{preferred_type['provider']['organization']}'")
    
    agent_card = create_agent_card(preferred_type)
    card_discovery = A2ACardDiscovery(agent_card=agent_card)
    selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
    return selector.get_agent()

def create_test_agents_for_all_providers():
    """Create test agents for all available providers."""
    available_types = get_available_agent_types()
    agents = []
    
    for agent_type in available_types:
        try:
            agent_card = create_agent_card(agent_type)
            card_discovery = A2ACardDiscovery(agent_card=agent_card)
            selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
            agent = selector.get_agent()
            agents.append((agent_type["name"], agent))
        except Exception as e:
            print(f"⚠️  Failed to create agent for {agent_type['name']}: {e}")
    
    return agents

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
    # Instantiate agent through selector
    selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
    agent = selector.get_agent()
    
    # Show model information
    print(f"🔧 Original Model: {agent.model_name}")
    print(f"🌐 LiteLLM Model: {agent.litellm_model}")
    
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

async def test_openai_and_aws_agents():
    """Test both OpenAI and AWS agents specifically with a simple query."""
    print("\n🎯 Testing OpenAI and AWS Agents Specifically")
    print("=" * 60)
    
    target_providers = ["openai", "aws"]
    available_agents = get_available_agent_types()
    
    # Filter to only OpenAI and AWS
    target_agents = [agent for agent in available_agents 
                    if agent["provider"]["organization"] in target_providers]
    
    if not target_agents:
        print("❌ Neither OpenAI nor AWS agents are available (missing environment variables)")
        return False
    
    print(f"✅ Found {len(target_agents)} target agent(s) available")
    
    results = []
    for agent_type in target_agents:
        print(f"\n🤖 Testing {agent_type['name']}")
        print("-" * 40)
        
        try:
            # Create agent
            agent_card = create_agent_card(agent_type)
            card_discovery = A2ACardDiscovery(agent_card=agent_card)
            selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
            agent = selector.get_agent()
            
            # Show model information
            print(f"🔧 Original Model: {agent.model_name}")
            print(f"🌐 LiteLLM Model: {agent.litellm_model}")
            
            # Simple test query
            test_query = "Please respond with a simple greeting and confirm you are working correctly."
            print(f"💬 Test Query: {test_query}")
            
            # Mock context for testing
            context = {}
            context_id = str(uuid4())
            task_id = str(uuid4())
            
            print("⏳ Processing...")
            result = await agent.invoke(test_query, context_id, task_id, context)
            
            print(f"✅ Response: {result.message[:100]}...")
            print(f"📊 Status: {result.status}")
            print(f"🎯 Action: {result.action}")
            
            # Consider it successful if we get any response
            success = bool(result.message and result.status)
            results.append((agent_type['name'], success))
            
            if success:
                print(f"✅ {agent_type['name']} test PASSED")
            else:
                print(f"❌ {agent_type['name']} test FAILED")
                
        except Exception as e:
            print(f"❌ Error testing {agent_type['name']}: {str(e)}")
            results.append((agent_type['name'], False))
    
    # Summary
    print(f"\n📊 OpenAI & AWS Test Summary")
    print("=" * 40)
    for agent_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{agent_name}: {status}")
    
    all_passed = all(success for _, success in results)
    return all_passed

async def main():
    print("🧪 A2A Agent Testing Suite")
    print("=" * 60)
    print("Testing OpenAI and AWS unified agents through LiteLLM integration")
    print()
    
    # First, run the specific OpenAI and AWS test
    openai_aws_success = await test_openai_and_aws_agents()
    
    # Then run the full compliance and behavior tests
    print("\n" + "=" * 60)
    print("🔬 Running Full Compliance and Behavior Tests")
    print("=" * 60)
    
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
    print("\n" + "=" * 60)
    print("📊 Final Test Summary")
    print("=" * 60)
    
    print("OpenAI & AWS Simple Test:")
    print(f"  {'✅ PASSED' if openai_aws_success else '❌ FAILED'}")
    
    print("\nFull Compliance & Behavior Tests:")
    for agent_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {agent_name}: {status}")
    
    all_passed = openai_aws_success and all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All tests PASSED!")
        print("Both OpenAI and AWS agents are working correctly through the unified system.")
    else:
        print("\n⚠️  Some tests FAILED. See above for details.")

if __name__ == "__main__":
    asyncio.run(main()) 