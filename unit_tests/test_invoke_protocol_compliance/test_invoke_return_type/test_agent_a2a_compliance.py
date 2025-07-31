#!/usr/bin/env python3
"""
Unit Test for Agent A2A Protocol Compliance using ResponseFormat BaseModel

Tests whether an agent's invoke() method returns a ResponseFormat object that 
complies with the A2A protocol.

Usage:
    python test_agent_a2a_compliance.py
"""

import asyncio
from typing import Dict, Any
import sys
import os

# Add project root for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.a2a_mcp.common.base_agent.base_agent import ResponseFormat
from pydantic import BaseModel, ValidationError

class A2AComplianceError(Exception):
    """Raised when an agent's invoke() response is not A2A compliant"""
    pass

class ExampleCompliantAgent:
    """Example agent that demonstrates proper A2A protocol compliance"""
    agent_name = "example-compliant-agent"
    
    async def invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Any]) -> ResponseFormat:
        """Example compliant invoke() implementation"""
        return ResponseFormat(
            action="answer",
            status="completed",
            message="I have processed your request...",
            next_agent_instructions=None,
            agent_names=None
        )

class A2AComplianceTester:
    """Utility class for testing A2A protocol compliance"""
    
    # Define expected states and their requirements
    STATE_REQUIREMENTS = {
        "answer": {
            "completed": {
                "required_fields": ["message"],
                "optional_fields": ["artifacts", "custom_status"],
                "forbidden_fields": ["agent_names", "next_agent_instructions"]
            },
            "input_required": {
                "required_fields": ["message"],
                "forbidden_fields": ["agent_names", "next_agent_instructions", "artifacts"]
            },
            "failed": {
                "required_fields": ["message"],
                "optional_fields": ["custom_status"],
                "forbidden_fields": ["agent_names", "next_agent_instructions"]
            }
        },
        "call_next_agent": {
            "input_required": {
                "required_fields": ["message", "agent_names", "next_agent_instructions"],
                "optional_fields": ["custom_status"],
                "field_requirements": {
                    "agent_names": lambda x: bool(x and len(x) > 0 and isinstance(x, list)),
                    "next_agent_instructions": lambda x, response=None: bool(x and len(x) > 0 and isinstance(x, list) and (response is None or len(x) == len(response.agent_names)))
                }
            }
        }
    }
    
    @staticmethod
    def validate_response_state(response: Any) -> Dict[str, Any]:
        """
        Validate response state and field relationships
        
        Args:
            response: The response object to validate
            
        Returns:
            Dict with validation results and any issues found
        """
        issues = []
        
        # Check required A2A fields exist
        required_fields = ["action", "status", "message"]
        for field in required_fields:
            if not hasattr(response, field):
                issues.append(f"Missing required A2A field: {field}")
                continue
            
            value = getattr(response, field)
            if value is None:
                issues.append(f"Required field {field} cannot be None")
                
        if issues:
            return {
                "valid": False,
                "issues": issues
            }
            
        # Get expected state requirements
        if response.action not in A2AComplianceTester.STATE_REQUIREMENTS:
            return {
                "valid": False,
                "issues": [f"Invalid action: {response.action}"]
            }
            
        state_config = A2AComplianceTester.STATE_REQUIREMENTS[response.action]
        if response.status not in state_config:
            return {
                "valid": False,
                "issues": [f"Invalid status '{response.status}' for action '{response.action}'"]
            }
            
        requirements = state_config[response.status]
        
        # Check required fields
        for field in requirements.get("required_fields", []):
            if not hasattr(response, field) or getattr(response, field) is None:
                issues.append(f"Missing required field: {field}")
                
        # Check forbidden fields
        for field in requirements.get("forbidden_fields", []):
            if hasattr(response, field) and getattr(response, field) is not None:
                issues.append(f"Field should not be present: {field}")
                
        # Check field requirements
        for field, validator in requirements.get("field_requirements", {}).items():
            if not validator(getattr(response, field, None)):
                issues.append(f"Field validation failed: {field}")
                
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    async def test_agent_invoke_compliance(agent: Any) -> Dict[str, Any]:
        """Test if an agent's invoke() method returns a proper ResponseFormat"""
        try:
            # Test basic invoke
            response = await agent.invoke(
                query="Test query",
                context_id="test-context",
                task_id="test-task",
                context={}
            )
            
            # Verify response is a Pydantic BaseModel
            if not isinstance(response, BaseModel):
                return {
                    'status': 'FAILED',
                    'error': f'Response must be a Pydantic BaseModel instance, got {type(response)}'
                }
            
            # Validate state and fields
            validation = A2AComplianceTester.validate_response_state(response)
            if not validation["valid"]:
                return {
                    'status': 'FAILED',
                    'error': "State validation failed: " + "; ".join(validation["issues"])
                }
            
            return {
                'status': 'PASSED',
                'agent_name': agent.agent_name,
                'response': response
            }
            
        except ValidationError as e:
            return {
                'status': 'FAILED',
                'error': f'Pydantic validation error: {str(e)}'
            }
        except Exception as e:
            return {
                'status': 'FAILED',
                'error': f'Unexpected error: {str(e)}'
            }

def print_compliance_report(results: Dict[str, Any]) -> None:
    """Print formatted compliance test results"""
    print("\nA2A COMPLIANCE REPORT")
    print(f"Agent Name: {results.get('agent_name', 'unknown')}")
    print(f"Status: {results['status']}")
    
    if results['status'] == 'PASSED':
        response = results['response']
        print(f"Response: action={response.action}, status={response.status}")
        print(f"Message: {response.message}")
    else:
        print(f"Error: {results.get('error', 'Unknown error')}")

async def main():
    """Main test function"""
    print("🧪 A2A Protocol Compliance Tester")
    print("="*50)
    
    # Test example compliant agent
    agent = ExampleCompliantAgent()
    results = await A2AComplianceTester.test_agent_invoke_compliance(agent)
    print_compliance_report(results)
    
    return results['status'] == 'PASSED'

if __name__ == "__main__":
    asyncio.run(main()) 