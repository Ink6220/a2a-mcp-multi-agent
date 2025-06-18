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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.a2a_mcp.common.base_agent.base_agent import ResponseFormat

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
                "forbidden_fields": ["agent_name", "next_agent_instruction"]
            }
        },
        {
            "name": "Delegation State",
            "query": "I need a JSON return, this can be done by the test-agent-2",
            "expected_state": {
                "action": "call_next_agent",
                "status": "input_required",
                "required_fields": ["message", "agent_name", "next_agent_instruction"],
                "field_requirements": {
                    "agent_name": lambda x: bool(x and len(x) > 0),
                    "next_agent_instruction": lambda x: bool(x and len(x) > 0)
                }
            }
        },
        {
            "name": "Input Required State",
            "query": "Hi this is a vague prompt, please ask for more information",
            "expected_state": {
                "action": "answer",
                "status": "input_required",
                "required_fields": ["message"],
                "forbidden_fields": ["agent_name", "next_agent_instruction"]
            }
        },
        {
            "name": "Failed State",
            "query": "This should fail, return an error",
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
                if not validator(getattr(response, field, None)):
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
                    history=""
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
                            'agent_name': getattr(response, 'agent_name', None),
                            'next_agent_instruction': getattr(response, 'next_agent_instruction', None),
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

def print_behavior_report(results: Dict[str, Any]) -> None:
    """Print formatted behavioral test results"""
    print("\n🧪 LLM STATE VALIDATION REPORT")
    print("="*50)
    print(f"Agent Name: {results['agent_name']}")
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
                        print(f"  {key}: {value}")

async def main():
    """Main test function"""
    print("🧪 LLM State Validation Suite")
    print("="*50)
    
    # Import your LLM agent here
    # agent = YourLLMAgent()
    # results = await LLMBehaviorTester.test_llm_behavior(agent)
    # print_behavior_report(results)
    
    print("\n⚠️  Please import your LLM agent and uncomment the test code")
    return True

if __name__ == "__main__":
    asyncio.run(main()) 