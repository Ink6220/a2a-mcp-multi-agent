#!/usr/bin/env python3
"""
Unit Test for Agent A2A Protocol Compliance

Tests whether an agent's invoke() method returns responses that comply with the A2A protocol.
This is a "black box" test that only checks the agent's invoke() output format.

The A2A protocol specifies ONLY these required fields:
- is_task_complete: bool
- require_user_input: bool  
- content: str

Additional fields (hang_up, call_next_agent, etc.) are custom extensions and are allowed
but not validated by this A2A compliance tester.

Usage:
    # Test your agent class
    python test_agent_a2a_compliance.py
    
    # Run as a module
    python -m unittest_tests.test_invoke()_protocol_compliance.test_agent_a2a_compliance
"""

import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from unittest.mock import Mock
import sys
import os

# Add the project root to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from basic_executor import GenericAgentExecutor


class A2AComplianceError(Exception):
    """Raised when an agent's invoke() response is not A2A compliant"""
    pass


class A2AComplianceTester:
    """Utility class to test A2A compliance of agent invoke() methods"""
    
    @staticmethod
    def validate_invoke_response(response: Dict[str, Any]) -> None:
        """
        Validates that an agent's invoke() response is A2A compliant.
        
        A2A Protocol Requirements (ONLY these are required):
        - is_task_complete: bool
        - require_user_input: bool
        - content: str
        
        Additional fields are allowed (hang_up, call_next_agent, etc.) 
        but are not part of the A2A protocol specification.
        
        Args:
            response: The response dict from agent.invoke()
            
        Raises:
            A2AComplianceError: If response is not A2A compliant
        """
        # A2A Protocol - ONLY these fields are required
        required_fields = ['is_task_complete', 'require_user_input', 'content']
        
        # Check required fields exist
        for field in required_fields:
            if field not in response:
                raise A2AComplianceError(f"Missing required A2A field: '{field}'")
        
        # Validate field types and values
        if not isinstance(response['is_task_complete'], bool):
            raise A2AComplianceError("'is_task_complete' must be a boolean")
        
        if not isinstance(response['require_user_input'], bool):
            raise A2AComplianceError("'require_user_input' must be a boolean")
        
        if not isinstance(response['content'], str):
            raise A2AComplianceError("'content' must be a string")
        
        # Validate logical constraints
        if response['is_task_complete'] and response['require_user_input']:
            raise A2AComplianceError(
                "Invalid state: 'is_task_complete' and 'require_user_input' cannot both be True"
            )
        
        # NOTE: We do NOT validate optional/custom fields like hang_up, call_next_agent, etc.
        # These are part of your custom ResponseFormat, not the A2A protocol specification.
    
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
                "I need more information about this topic",
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
                response = await agent.invoke(query, session_id)
                
                # Validate A2A compliance
                A2AComplianceTester.validate_invoke_response(response)
                
                test_result['status'] = 'PASSED'
                test_result['response'] = response
                results['passed'] += 1
                
            except Exception as e:
                test_result['status'] = 'FAILED'
                test_result['error'] = str(e)
                results['failed'] += 1
            
            results['test_details'].append(test_result)
        
        results['compliance_percentage'] = (results['passed'] / results['total_tests']) * 100
        results['is_fully_compliant'] = results['failed'] == 0
        
        return results


# Example compliant agent for testing
class ExampleCompliantAgent:
    """Example agent that is A2A compliant for testing purposes"""
    
    def __init__(self):
        self.agent_name = "example-compliant-agent"
    
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        """A2A compliant invoke method with custom extensions"""
        if "error" in query.lower():
            return {
                # A2A Core Protocol
                "is_task_complete": False,
                "require_user_input": True,
                "content": "I encountered an error. Please rephrase your request.",
                # Custom extensions (not part of A2A protocol)
                "hang_up": False
            }
        elif "delegate" in query.lower():
            return {
                # A2A Core Protocol
                "is_task_complete": True,
                "require_user_input": False,
                "content": "I will delegate this task to a specialist.",
                # Custom extensions (not part of A2A protocol)
                "hang_up": False,
                "call_next_agent": True,
                "agent_name": "specialist-agent"
            }
        elif "help" in query.lower():
            return {
                # A2A Core Protocol
                "is_task_complete": False,
                "require_user_input": True,
                "content": "I'd be happy to help! What specifically do you need assistance with?",
                # Custom extensions (not part of A2A protocol)
                "hang_up": False
            }
        else:
            return {
                # A2A Core Protocol
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"I have processed your request: {query}",
                # Custom extensions (not part of A2A protocol)
                "hang_up": False
            }


# Example non-compliant agent for testing
class ExampleNonCompliantAgent:
    """Example agent that is NOT A2A compliant (for negative testing)"""
    
    def __init__(self):
        self.agent_name = "example-non-compliant-agent"
    
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        """Non-A2A compliant invoke method (missing required fields)"""
        return {
            "message": "This response is missing required A2A fields",
            "status": "completed",
            "hang_up": False  # This custom field is fine, but missing A2A core fields
            # Missing: is_task_complete, require_user_input, content
        }


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
            print(f"   Response: is_complete={response['is_task_complete']}, "
                  f"need_input={response['require_user_input']}")
            print(f"   Content: {response['content'][:50]}...")
            
            # Show custom extensions if present
            custom_fields = {k: v for k, v in response.items() 
                           if k not in ['is_task_complete', 'require_user_input', 'content']}
            if custom_fields:
                print(f"   Custom fields: {custom_fields}")
        else:
            print(f"   Error: {test['error']}")


async def run_compliance_tests():
    """Run all compliance tests"""
    print("🧪 A2A Protocol Compliance Tester")
    print("="*60)
    print("ℹ️  Testing ONLY A2A core protocol fields:")
    print("   - is_task_complete, require_user_input, content")
    print("   - Custom fields (hang_up, call_next_agent, etc.) are allowed but not validated")
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
    
    return compliant_results['is_fully_compliant'] and not non_compliant_results['is_fully_compliant']


async def test_specific_responses():
    """Test specific response validation logic"""
    print(f"\n{'='*60}")
    print("🔍 Testing Response Validation Logic")
    print(f"{'='*60}")
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Valid response (minimal A2A)
    try:
        valid_response = {
            "is_task_complete": True,
            "require_user_input": False,
            "content": "Task completed successfully"
        }
        A2AComplianceTester.validate_invoke_response(valid_response)
        print("✅ Test 1: Minimal A2A response passed")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Test 1: Minimal A2A response failed: {e}")
    
    # Test 2: Valid response with custom fields
    try:
        response_with_custom = {
            "is_task_complete": True,
            "require_user_input": False,
            "content": "Task completed successfully",
            "hang_up": False,  # Custom field - should be allowed
            "call_next_agent": True,  # Custom field - should be allowed
            "agent_name": "specialist"  # Custom field - should be allowed
        }
        A2AComplianceTester.validate_invoke_response(response_with_custom)
        print("✅ Test 2: A2A response with custom fields passed")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Test 2: A2A response with custom fields failed: {e}")
    
    # Test 3: Missing required fields
    try:
        A2AComplianceTester.validate_invoke_response({"content": "incomplete"})
        print("❌ Test 3: Missing fields should have failed")
    except A2AComplianceError:
        print("✅ Test 3: Missing required fields correctly rejected")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Test 3: Unexpected error: {e}")
    
    # Test 4: Wrong types
    try:
        A2AComplianceTester.validate_invoke_response({
            "is_task_complete": "yes",  # Should be boolean
            "require_user_input": False,
            "content": "test"
        })
        print("❌ Test 4: Wrong types should have failed")
    except A2AComplianceError:
        print("✅ Test 4: Wrong types correctly rejected")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Test 4: Unexpected error: {e}")
    
    # Test 5: Logical contradiction
    try:
        A2AComplianceTester.validate_invoke_response({
            "is_task_complete": True,
            "require_user_input": True,  # Cannot both be True
            "content": "contradiction"
        })
        print("❌ Test 5: Logical contradiction should have failed")
    except A2AComplianceError:
        print("✅ Test 5: Logical contradiction correctly rejected")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Test 5: Unexpected error: {e}")
    
    print(f"\nValidation Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests


async def main():
    """Main function for command-line testing"""
    success = True
    
    # Run compliance tests
    compliance_success = await run_compliance_tests()
    
    # Run validation tests
    validation_success = await test_specific_responses()
    
    success = compliance_success and validation_success
    
    print(f"\n{'='*60}")
    print(f"🎯 OVERALL RESULT: {'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    print(f"{'='*60}")
    
    if success:
        print("\n🎉 Your A2A compliance testing framework is working correctly!")
        print("\n📝 TO TEST YOUR OWN AGENT:")
        print("1. Import this module: from test_agent_a2a_compliance import A2AComplianceTester")
        print("2. Test your agent: results = await A2AComplianceTester.test_agent_invoke_compliance(your_agent)")
        print("3. Check results: print_compliance_report(results)")
        print("\n💡 Remember: Only A2A core fields are validated.")
        print("   Your custom fields (hang_up, delegation, etc.) are allowed but not checked here.")
    
    return success


if __name__ == "__main__":
    # Run the main test function
    asyncio.run(main()) 