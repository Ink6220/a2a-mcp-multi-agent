#!/usr/bin/env python3
"""
Behavioral Test Suite for LLM Agent invoke() Responses

Tests whether an LLM agent's state transitions and field relationships are valid,
regardless of the actual content.

Usage:
    python test_llm_behavior.py
"""

import asyncio
import sys
import os
from typing import Dict, Any, List

# Add project root for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.a2a_mcp.common.base_agent.base_agent import ResponseFormat
from src.a2a_mcp.common.base_agent.a2a_agent_selector import A2AAgentSelector
from src.a2a_mcp.common.card_discovery import A2ACardDiscovery
from src.a2a_mcp.common.types import CustomAgentCard
from a2a.types import AgentProvider, AgentCapabilities, AgentSkill

class LLMBehaviorTester:
    """Tests LLM agent state transitions and field relationships"""
    
    # Test scenarios with expected states and field relationships
    TEST_SCENARIOS = [
        {
            "name": "Basic Answer State",
            "query": "Tell me a joke",
            "expected_state": {
                "action": "answer",
                "status": "completed",
                "required_fields": ["message"],
                "forbidden_fields": ["agent_names", "next_agent_instructions"]
            }
        },
        {
            "name": "Single Delegation State",
            "query": "Ask test-agent-2 to do help query the database based off his system prompt",
            "expected_state": {
                "action": "call_next_agent",
                "status": "input_required",
                "required_fields": ["message", "agent_names", "next_agent_instructions"],
                "field_requirements": {
                    "agent_names": lambda x: bool(x and len(x) > 0 and isinstance(x, list)),
                    "next_agent_instructions": lambda x: bool(x and len(x) > 0 and isinstance(x, list) and len(x) == 1)
                }
            }
        },
        {
            "name": "Parallel Delegation State",
            "query": "This task needs both test-agent-1 and test-agent-2 working together",
            "expected_state": {
                "action": "call_next_agent",
                "status": "input_required",
                "required_fields": ["message", "agent_names", "next_agent_instructions"],
                "field_requirements": {
                    "agent_names": lambda x: bool(x and len(x) > 1 and isinstance(x, list)),
                    "next_agent_instructions": lambda x, response=None: bool(x and len(x) > 1 and isinstance(x, list) and (response is None or len(x) == len(response.agent_names)))
                }
            }
        },
        {
            "name": "Follow up question to user State",
            "query": "Hi this is a vague prompt, please ask for more information",
            "expected_state": {
                "action": "answer",
                "status": "input_required",
                "required_fields": ["message"],
                "forbidden_fields": ["agent_names", "next_agent_instructions"]
            }
        },
        {
            "name": "Failed State",
            "query": "This should fail, return an fail into the status state",
            "expected_state": {
                "action": "answer",
                "status": "failed",
                "required_fields": ["message"],
                "optional_fields": ["custom_status"]
            }
        },
        {
            "name": "Artifact State",
            "query": "Generate a mock output in JSON, it should be returned as an artifact",
            "expected_state": {
                "action": "answer",
                "status": "completed",
                "required_fields": ["message", "artifacts"],
                "field_requirements": {
                    "artifacts": lambda x: bool(x and len(x) > 0)
                }
            }
        }
    ]
    
    @staticmethod
    def validate_response_state(response: ResponseFormat, expected_state: Dict) -> Dict[str, Any]:
        """Validate response state and field relationships"""
        issues = []
        
        # Check action
        if response.action != expected_state["action"]:
            issues.append(f"Invalid action: expected {expected_state['action']}, got {response.action}")
            
        # Check status
        if response.status != expected_state["status"]:
            issues.append(f"Invalid status: expected {expected_state['status']}, got {response.status}")
            
        # Check required fields
        for field in expected_state["required_fields"]:
            if not hasattr(response, field) or getattr(response, field) is None:
                issues.append(f"Missing required field: {field}")
                
        # Check forbidden fields
        if "forbidden_fields" in expected_state:
            for field in expected_state["forbidden_fields"]:
                if hasattr(response, field) and getattr(response, field) is not None:
                    issues.append(f"Field should not be present: {field}")
                    
        # Check field requirements
        if "field_requirements" in expected_state:
            for field, validator in expected_state["field_requirements"].items():
                value = getattr(response, field, None)
                try:
                    # Try to pass both value and response to validator
                    if not validator(value, response):
                        issues.append(f"Field validation failed: {field}")
                except TypeError:
                    # If validator doesn't accept response parameter, just pass value
                    if not validator(value):
                        issues.append(f"Field validation failed: {field}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    async def test_llm_behavior(agent: Any) -> Dict[str, Any]:
        """Run state transition tests on an LLM agent"""
        results = {
            'agent_name': getattr(agent, 'agent_name', 'unknown'),
            'total_tests': len(LLMBehaviorTester.TEST_SCENARIOS),
            'passed_tests': 0,
            'failed_tests': [],
            'status': 'RUNNING'
        }
        
        for scenario in LLMBehaviorTester.TEST_SCENARIOS:
            try:
                # Run the test scenario
                response = await agent.invoke(
                    query=scenario['query'],
                    context_id="test-context",
                    task_id="test-task",
                    context={}
                )
                
                # Validate state and fields
                validation = LLMBehaviorTester.validate_response_state(
                    response, 
                    scenario['expected_state']
                )
                
                if validation['valid']:
                    results['passed_tests'] += 1
                else:
                    results['failed_tests'].append({
                        'scenario': scenario['name'],
                        'query': scenario['query'],
                        'issues': validation['issues'],
                        'response': {
                            'action': response.action,
                            'status': response.status,
                            'message': response.message[:100] + '...' if len(response.message) > 100 else response.message,
                            'agent_names': getattr(response, 'agent_names', None),
                            'next_agent_instructions': getattr(response, 'next_agent_instructions', None),
                            'artifacts': getattr(response, 'artifacts', None),
                            'custom_status': getattr(response, 'custom_status', None)
                        }
                    })
                    
            except Exception as e:
                results['failed_tests'].append({
                    'scenario': scenario['name'],
                    'error': str(e)
                })
        
        # Set final status
        results['status'] = 'PASSED' if len(results['failed_tests']) == 0 else 'FAILED'
        return results

def create_test_agent_card(provider: str, model_name: str, agent_name: str) -> CustomAgentCard:
    """Create a test agent card for the specified provider"""
    return CustomAgentCard(
        name=agent_name,
        description=f"Test agent for protocol compliance ({provider})",
        url="http://localhost:10101/",
        provider=AgentProvider(
            organization=provider,
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
        modelName=model_name,
        systemPrompt="""You are a test agent that validates A2A protocol compliance.

## DISCOVERY
Available agents:
- test-agent-1: A simple test agent for basic tasks
- test-agent-2: A more complex test agent for advanced tasks

## RESPONSE FORMAT RULES
**CRITICAL: YOU MUST FOLLOW THESE RULES:**
1. Return ONLY raw JSON - no markdown formatting, no triple backticks
2. Do not wrap the JSON in ```json or ``` blocks
3. Do not add any text before or after the JSON
4. The response must be valid JSON that can be parsed directly

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

**CORRECT Examples (return exactly like this - no markdown):**
{
  "action": "answer",
  "status": "completed",
  "message": "Here's the information you requested...",
  "artifacts": null
}

{
  "action": "answer", 
  "status": "input_required",
  "message": "Could you please provide more details about your request?",
  "artifacts": null
}

{
  "action": "answer",
  "status": "failed", 
  "message": "I encountered an error while processing your request.",
  "artifacts": null
}

{
  "action": "answer",
  "status": "completed",
  "message": "Here is your requested data.",
  "artifacts": "{\\"result\\": \\"success\\", \\"data\\": \\"mock_output\\"}"
}

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

**CORRECT Examples (return exactly like this - no markdown):**
{
  "action": "call_next_agent",
  "status": "input_required",
  "message": "I will delegate this task to test-agent-2",
  "agent_names": ["test-agent-2"],
  "next_agent_instructions": ["Please handle the customer inquiry about pricing"],
  "artifacts": null
}

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

**FORBIDDEN Examples (NEVER DO THIS):**
{
  "action": "call_next_agent",
  "status": "completed",  // ❌ WRONG! NEVER use "completed" with delegation
  "message": "Task delegated",
  "agent_names": ["test-agent-1"],
  "next_agent_instructions": ["Handle this"]
}

## VALIDATION CHECKLIST
Before responding, verify EVERY point:
- ✅ Response is raw JSON without any markdown formatting
- ✅ No ```json or ``` blocks around the response
- ✅ No text before or after the JSON
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
        nextAgent=[]
    )

def create_openai_agent():
    """Create OpenAI test agent"""
    agent_card = create_test_agent_card("openai", "gpt-4o-mini", "OpenAI Test Agent")
    card_discovery = A2ACardDiscovery(agent_card=agent_card)
    selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
    return selector.get_agent()

def create_aws_agent():
    """Create AWS test agent"""
    agent_card = create_test_agent_card("aws", "amazon.nova-lite-v1:0", "AWS Test Agent")
    card_discovery = A2ACardDiscovery(agent_card=agent_card)
    selector = A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery)
    return selector.get_agent()

def is_provider_available(provider: str) -> bool:
    """Check if a provider is available based on environment variables"""
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    elif provider == "aws":
        return all([
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_REGION_NAME")
        ])
    return False

async def test_provider_comparison():
    """Test and compare OpenAI and AWS agents"""
    print("\n🔄 Provider Comparison Test")
    print("=" * 50)
    
    results = {}
    
    # Test OpenAI if available
    if is_provider_available("openai"):
        print("\n🧪 Testing OpenAI Agent")
        openai_agent = create_openai_agent()
        print(f"🔧 Original Model: {openai_agent.model_name}")
        print(f"🌐 LiteLLM Model: {openai_agent.litellm_model}")
        results["OpenAI"] = await LLMBehaviorTester.test_llm_behavior(openai_agent)
    else:
        print("\n⚠️  OpenAI not available (missing OPENAI_API_KEY)")
        
    # Test AWS if available
    if is_provider_available("aws"):
        print("\n🧪 Testing AWS Agent")
        aws_agent = create_aws_agent()
        print(f"🔧 Original Model: {aws_agent.model_name}")
        print(f"🌐 LiteLLM Model: {aws_agent.litellm_model}")
        results["AWS"] = await LLMBehaviorTester.test_llm_behavior(aws_agent)
    else:
        print("\n⚠️  AWS not available (missing AWS credentials)")
    
    # Print comparison results
    print("\n📊 Provider Comparison Results")
    print("=" * 50)
    
    for provider, result in results.items():
        status_emoji = "✅" if result['status'] == 'PASSED' else "❌"
        print(f"{status_emoji} {provider}: {result['passed_tests']}/{result['total_tests']} tests passed")
    
    return results

def print_behavior_report(results: Dict[str, Any]) -> None:
    """Print formatted behavioral test results"""
    print("\n🧪 LLM STATE VALIDATION REPORT\n" + "="*50)
    print(f"Agent Name: {results.get('agent_name', 'unknown')}")
    print(f"Status: {results['status']}")
    print(f"Tests Passed: {results['passed_tests']}/{results['total_tests']}")
    
    if results['failed_tests']:
        print("\nFailed Tests:")
        for failure in results['failed_tests']:
            print(f"\n❌ {failure['scenario']}")
            if 'error' in failure:
                print(f"Error: {failure['error']}")
            else:
                print("Issues:")
                for issue in failure['issues']:
                    print(f"  • {issue}")
                print("\nResponse State:")
                for key, value in failure['response'].items():
                    if value is not None:
                        if key in ['agent_names', 'next_agent_instructions'] and isinstance(value, list):
                            print(f"  {key}: {', '.join(str(v) for v in value)}")
                        else:
                            print(f"  {key}: {value}")
            # Print the full raw response if available
            if 'raw_response' in failure:
                print("\nFull Raw Response:")
                print(failure['raw_response'])
            elif 'response' in failure:
                print("\nFull Response Object:")
                print(failure['response'])

async def main():
    """Main test function"""
    print("🧪 LLM State Validation Suite")
    print("="*50)
    
    # Run provider comparison tests
    results = await test_provider_comparison()
    
    # Print detailed reports for each provider
    for provider, result in results.items():
        print(f"\n{'='*20} {provider} DETAILED REPORT {'='*20}")
        print_behavior_report(result)
    
    # Overall summary
    print(f"\n{'='*20} OVERALL SUMMARY {'='*20}")
    all_passed = all(result['status'] == 'PASSED' for result in results.values())
    total_providers = len(results)
    passed_providers = sum(1 for result in results.values() if result['status'] == 'PASSED')
    
    print(f"Providers tested: {total_providers}")
    print(f"Providers passed: {passed_providers}")
    
    if all_passed:
        print("🎉 All available providers passed all tests!")
        return True
    else:
        print("⚠️  Some providers had test failures. Check detailed reports above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main()) 