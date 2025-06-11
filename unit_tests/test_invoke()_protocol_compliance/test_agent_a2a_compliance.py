#!/usr/bin/env python3
"""
Unit Test for Agent A2A Protocol Compliance using ResponseFormat BaseModel

Tests whether an agent's invoke() method returns a ResponseFormat object that 
complies with the A2A protocol.

The A2A protocol specifies ONLY these required fields on the ResponseFormat object:
- action: Literal["answer", "call_next_agent"]
- status: Literal["input_required", "completed", "failed"] 
- message: str

This test validates the attributes of the returned ResponseFormat object.

Usage:
    # Test your agent class
    python test_agent_a2a_compliance.py
    
    # Run as a module
    python -m unittest_tests.test_invoke()_protocol_compliance.test_agent_a2a_compliance
"""

import asyncio
from typing import Dict, Any, Optional, List, Type, Literal
import sys
import os

# --- Mock BaseModel and ResponseFormat for testing ---
# This simulates Pydantic's BaseModel without requiring Pydantic for the test.
class MockBaseModel:
    def __init__(self, **kwargs: Any):
        # Set default values for all annotated fields
        for name, _ in self.__annotations__.items():
            setattr(self, name, kwargs.get(name))

class ResponseFormat(MockBaseModel):
    """ Mocks the agent's ResponseFormat(BaseModel) for consistent testing """
    action: str  # Literal["answer", "call_next_agent"] 
    status: str  # Literal["input_required", "completed", "failed"]
    message: str
    
    # Optional fields
    custom_status: Optional[str] = None
    agent_name: Optional[str] = None
    next_agent_instruction: Optional[str] = None
    next_agent_schema: Optional[Dict[str, Any]] = None


# Add project root for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from basic_executor import GenericAgentExecutor


class A2AComplianceError(Exception):
    """Raised when an agent's invoke() response is not A2A compliant"""
    pass


class A2AComplianceTester:
    """Utility class to test A2A compliance of agent invoke() methods"""
    
    @staticmethod
    def validate_invoke_response(response: Any) -> None:
        """
        Validates that an agent's invoke() response object is A2A compliant.
        
        Args:
            response: The ResponseFormat object from agent.invoke()
            
        Raises:
            A2AComplianceError: If the response is not A2A compliant
        """
        # Check if it's a ResponseFormat object (or at least looks like one)
        if not hasattr(response, '__class__'):
             raise A2AComplianceError(f"Response is not an object: {response}")

        # A2A Protocol - check for required attributes
        required_attrs = ['action', 'status', 'message']
        for attr in required_attrs:
            if not hasattr(response, attr):
                raise A2AComplianceError(f"Response object missing required A2A attribute: '{attr}'")
        
        # Validate attribute types and values
        valid_actions = ["answer", "call_next_agent"]
        if response.action not in valid_actions:
            raise A2AComplianceError(f"'action' must be one of {valid_actions}, got: {response.action}")
        
        valid_statuses = ["input_required", "completed", "failed"]
        if response.status not in valid_statuses:
            raise A2AComplianceError(f"'status' must be one of {valid_statuses}, got: {response.status}")
        
        if not isinstance(response.message, str):
            raise A2AComplianceError("'message' must be a string")
        
        # Validate conditional requirements based on action (this might raise errors from the BaseAgent class first)
        if response.action == "call_next_agent":
            if not hasattr(response, 'agent_name') or not response.agent_name:
                raise A2AComplianceError("'agent_name' is required when action is 'call_next_agent'")
            if not hasattr(response, 'next_agent_instruction') or not response.next_agent_instruction:
                raise A2AComplianceError("'next_agent_instruction' is required when action is 'call_next_agent'")

    @staticmethod
    async def test_agent_invoke_compliance(
        agent: Any, 
        test_queries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Test an agent's invoke() method for A2A compliance.
        
        Args:
            agent: The agent instance to test
            test_queries: List of test queries. If None, uses default queries.
            
        Returns:
            Dict with test results
        """
        if test_queries is None:
            test_queries = [
                "Hello, can you help me?",
                "What is 2 + 2?",
                "Please process this data",
                "Can you delegate this task?"
            ]
        
        results = {
            'agent_name': getattr(agent, 'agent_name', 'Unknown'),
            'total_tests': len(test_queries),
            'passed': 0,
            'failed': 0,
            'test_details': []
        }
        
        for i, query in enumerate(test_queries):
            test_result = {
                'test_id': i + 1,
                'query': query,
                'status': 'unknown',
                'response': None,
                'error': None
            }
            
            try:
                # Call agent's invoke method
                session_id = f"test-session-{i}"
                response_obj = await agent.invoke(query, session_id)
                
                # Validate A2A compliance
                A2AComplianceTester.validate_invoke_response(response_obj)
                
                test_result['status'] = 'PASSED'
                test_result['response'] = response_obj
                results['passed'] += 1
                
            except Exception as e:
                test_result['status'] = 'FAILED'
                test_result['error'] = str(e)
                results['failed'] += 1
            
            results['test_details'].append(test_result)
        
        results['compliance_percentage'] = (results['passed'] / results['total_tests']) * 100
        results['is_fully_compliant'] = results['failed'] == 0
        
        return results


# --- Example Agents Using ResponseFormat BaseModel ---

class ExampleCompliantAgent:
    """Example agent that returns A2A compliant ResponseFormat objects"""
    agent_name = "example-compliant-agent"
    
    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
        if "delegate" in query.lower():
            return ResponseFormat(
                action="call_next_agent",
                status="completed",
                message="I will delegate this task to a specialist.",
                agent_name="specialist-agent",
                next_agent_instruction="Please handle this specialized request"
            )
        else:
            return ResponseFormat(
                action="answer",
                status="completed",
                message=f"I have processed your request: {query}"
            )

class ExampleNonCompliantAgent:
    """Example agent that returns non-A2A compliant responses"""
    agent_name = "example-non-compliant-agent"
    
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        # Returns a dict instead of a ResponseFormat object
        return {"message": "This is not a ResponseFormat object"}

class ExampleInvalidActionAgent:
    """Example agent that returns a ResponseFormat with invalid action"""
    agent_name = "example-invalid-action-agent"

    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
        return ResponseFormat(
            action="invalid_action",  # Invalid action
            status="completed",
            message="This response has an invalid action."
        )

class ExampleMissingDelegationFieldsAgent:
    """Example agent that tries to delegate but misses required fields"""
    agent_name = "example-missing-delegation-agent"

    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
        return ResponseFormat(
            action="call_next_agent",
            status="completed", 
            message="Delegating task but missing required fields."
            # Missing agent_name and next_agent_instruction
        )


def print_compliance_report(results: Dict[str, Any]) -> None:
    """Print a formatted compliance report"""
    print(f"\n{'='*60}")
    print(f"A2A COMPLIANCE REPORT")
    print(f"{'='*60}")
    print(f"Agent Name: {results['agent_name']}")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Compliance: {results['compliance_percentage']:.1f}%")
    print(f"Status: {'✅ FULLY COMPLIANT' if results['is_fully_compliant'] else '❌ NOT COMPLIANT'}")
    
    print(f"\n{'='*60}")
    print(f"TEST DETAILS")
    print(f"{'='*60}")
    
    for test in results['test_details']:
        status_icon = "✅" if test['status'] == 'PASSED' else "❌"
        print(f"\n{status_icon} Test {test['test_id']}: {test['status']}")
        print(f"   Query: {test['query']}")
        
        if test['status'] == 'PASSED':
            response = test['response']
            print(f"   Response: action={response.action}, status={response.status}")
            print(f"   Message: {response.message[:50]}...")
            
            # Show optional fields if present
            optional_fields = {}
            for field in ['custom_status', 'agent_name', 'next_agent_instruction', 'next_agent_schema']:
                if hasattr(response, field) and getattr(response, field) is not None:
                    optional_fields[field] = getattr(response, field)
            if optional_fields:
                print(f"   Optional fields: {optional_fields}")
        else:
            print(f"   Error: {test['error']}")


async def main():
    """Main function for command-line testing"""
    print("🧪 A2A Protocol Compliance Tester (Updated ResponseFormat)")
    print("="*60)
    
    # Test with example agents
    print("\n📋 Testing Example Compliant Agent:")
    compliant_agent = ExampleCompliantAgent()
    compliant_results = await A2AComplianceTester.test_agent_invoke_compliance(compliant_agent)
    print_compliance_report(compliant_results)
    
    print("\n📋 Testing Example Non-Compliant Agent:")
    non_compliant_agent = ExampleNonCompliantAgent()
    non_compliant_results = await A2AComplianceTester.test_agent_invoke_compliance(non_compliant_agent)
    print_compliance_report(non_compliant_results)
    
    print("\n📋 Testing Invalid Action Agent:")
    invalid_action_agent = ExampleInvalidActionAgent()
    invalid_action_results = await A2AComplianceTester.test_agent_invoke_compliance(invalid_action_agent)
    print_compliance_report(invalid_action_results)
    
    print("\n📋 Testing Missing Delegation Fields Agent:")
    missing_fields_agent = ExampleMissingDelegationFieldsAgent()
    missing_fields_results = await A2AComplianceTester.test_agent_invoke_compliance(missing_fields_agent)
    print_compliance_report(missing_fields_results)
    
    success = (compliant_results['is_fully_compliant'] and 
               not non_compliant_results['is_fully_compliant'] and
               not invalid_action_results['is_fully_compliant'] and
               not missing_fields_results['is_fully_compliant'])
    
    print(f"\n🎯 OVERALL RESULT: {'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    if success:
        print("\n🎉 Your A2A compliance testing framework is working correctly!")
        print("\n📝 TO TEST YOUR OWN AGENT:")
        print("1. Import this module: from test_agent_a2a_compliance import A2AComplianceTester")
        print("2. Test your agent: results = await A2AComplianceTester.test_agent_invoke_compliance(your_agent)")
        print("3. Check results: print_compliance_report(results)")
        print("\n💡 Remember: A2A core fields are action, status, and message.")
        print("   Optional fields (agent_name, next_agent_instruction, etc.) are validated conditionally.")
    
    return success


if __name__ == "__main__":
    # Run the main test function
    asyncio.run(main()) 