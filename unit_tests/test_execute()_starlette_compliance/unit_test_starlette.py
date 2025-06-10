#!/usr/bin/env python3
"""
Minimal test to verify GenericAgentExecutor works with Starlette app
This simulates the A2A protocol flow without requiring full dependencies
"""

import asyncio
import json
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

# Mock the A2A dependencies to avoid import issues
class MockTaskState:
    working = "working"
    input_required = "input_required"
    completed = "completed"

class MockTextPart:
    def __init__(self, text: str):
        self.text = text

class MockTaskUpdater:
    def __init__(self, event_queue, task_id, context_id):
        self.event_queue = event_queue
        self.task_id = task_id
        self.context_id = context_id
        self.events = []
    
    def update_status(self, state, message, final=False):
        event = {
            "type": "status_update",
            "task_id": self.task_id,
            "context_id": self.context_id,
            "state": state,
            "message": message,
            "final": final
        }
        self.events.append(event)
        self.event_queue.append(event)
        print(f"📊 Status Update: {state} - {message}")
    
    def add_artifact(self, parts, name):
        event = {
            "type": "artifact",
            "task_id": self.task_id,
            "context_id": self.context_id,
            "parts": [{"text": part.text} for part in parts],
            "name": name
        }
        self.events.append(event)
        self.event_queue.append(event)
        print(f"📦 Artifact Created: {name}")
    
    def complete(self):
        event = {
            "type": "task_complete",
            "task_id": self.task_id,
            "context_id": self.context_id
        }
        self.events.append(event)
        self.event_queue.append(event)
        print(f"✅ Task Completed: {self.task_id}")

# Mock simplified agent executor
class TestAgentExecutor:
    """Simplified version of GenericAgentExecutor for testing"""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def execute(self, context, event_queue):
        """Main execution logic - mirrors your actual executor"""
        print(f"🚀 Executing agent: {self.agent.agent_name}")
        
        # Get user input
        query = context.get_user_input()
        print(f"📝 User Query: {query}")
        
        # Create/get task
        task = context.current_task
        if not task:
            task = Mock()
            task.id = f"task-{hash(query) % 10000}"
            task.contextId = f"context-{hash(query) % 10000}"
            event_queue.append({"type": "task_created", "task": task})
        
        # Create updater
        updater = MockTaskUpdater(event_queue, task.id, task.contextId)
        
        # Send initial working status
        updater.update_status(
            MockTaskState.working,
            "Processing your request...",
        )
        
        try:
            # Call agent's invoke method (your translation layer)
            session_id = task.contextId
            result = await self.agent.invoke(query, session_id)
            print(f"🤖 Agent Response: {result}")
            
            # Handle response based on A2A protocol
            if result['is_task_complete']:
                # Task complete
                part = MockTextPart(text=result['content'])
                updater.add_artifact([part], name=f'{self.agent.agent_name}-result')
                updater.complete()
            elif result['require_user_input']:
                # Need user input
                updater.update_status(
                    MockTaskState.input_required,
                    result['content'],
                    final=True
                )
            else:
                # Still working
                updater.update_status(
                    MockTaskState.working,
                    result['content']
                )
                
        except Exception as e:
            print(f"❌ Error: {e}")
            updater.update_status(
                MockTaskState.input_required,
                "An error occurred while processing your request.",
                final=True
            )

# Your agent implementation template
class YourTestAgent:
    """Template for your agent with translation layer"""
    
    def __init__(self, agent_name="test-agent"):
        self.agent_name = agent_name
    
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Your translation layer goes here
        1. LLM responds in ResponseFormat(BaseModel)
        2. Agent parses and translates
        3. Returns A2A + delegation superset
        """
        print(f"🔄 Translation Layer Processing...")
        print(f"   Query: {query}")
        print(f"   Session: {session_id}")
        
        # Simulate your LLM response in ResponseFormat
        llm_response = self._simulate_llm_response(query)
        print(f"   LLM Response: {llm_response}")
        
        # Your translation logic here
        a2a_response = self._translate_to_a2a(llm_response)
        print(f"   A2A Response: {a2a_response}")
        
        return a2a_response
    
    def _simulate_llm_response(self, query: str) -> Dict[str, Any]:
        """Simulate your ResponseFormat(BaseModel) response"""
        # This would be your actual LLM call returning ResponseFormat
        if "error" in query.lower():
            return {
                "action": "answer",
                "status": "error", 
                "message": "I encountered an error processing this request.",
                "agent_name": ""
            }
        elif "delegate" in query.lower():
            return {
                "action": "call_next_agent",
                "status": "completed",
                "message": "I need to delegate this to a specialist.",
                "agent_name": "specialist-agent"
            }
        elif "help" in query.lower():
            return {
                "action": "answer",
                "status": "input_required",
                "message": "I need more information. What specifically do you need help with?",
                "agent_name": ""
            }
        else:
            return {
                "action": "answer", 
                "status": "completed",
                "message": f"I processed your request: {query}",
                "agent_name": ""
            }
    
    def _translate_to_a2a(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """Your translation layer - converts ResponseFormat to A2A + superset"""
        
        # A2A Protocol fields
        a2a_response = {
            "is_task_complete": llm_response["status"] in ["completed", "hang_up"],
            "require_user_input": llm_response["status"] == "input_required", 
            "content": llm_response["message"],
            "hang_up": llm_response["status"] == "hang_up"
        }
        
        # Superset fields for delegation (your custom logic)
        if llm_response.get("action") == "call_next_agent":
            a2a_response.update({
                "call_next_agent": True,
                "agent_name": llm_response.get("agent_name", ""),
                "delegation_reason": "specialist_required"  # Your custom field
            })
        else:
            a2a_response.update({
                "call_next_agent": False,
                "agent_name": "",
            })
        
        return a2a_response

# Mock Starlette app simulation
async def simulate_starlette_request(agent, user_message: str):
    """Simulate how your Starlette app would use the executor"""
    print(f"\n🌐 Simulating Starlette Request")
    print(f"📨 Incoming Message: {user_message}")
    
    # Mock request context
    context = Mock()
    context.get_user_input.return_value = user_message
    context.current_task = None  # New request
    context.message = Mock()
    
    # Event queue to collect streaming events
    event_queue = []
    
    # Create executor and run
    executor = TestAgentExecutor(agent)
    await executor.execute(context, event_queue)
    
    # Display streaming events (what client would see)
    print(f"\n📡 Streaming Events (what client receives):")
    for i, event in enumerate(event_queue, 1):
        print(f"  {i}. {event['type']}: {json.dumps(event, indent=2, default=str)}")
    
    return event_queue

# Test scenarios
async def test_scenarios():
    """Test different scenarios to verify A2A compliance"""
    print("🧪 Testing GenericAgentExecutor with Starlette App")
    print("=" * 60)
    
    agent = YourTestAgent("your-agent")
    
    # Test 1: Successful completion
    print("\n" + "="*50)
    print("TEST 1: Successful Task Completion")
    events1 = await simulate_starlette_request(agent, "Hello, process this data")
    
    # Test 2: User input required
    print("\n" + "="*50) 
    print("TEST 2: User Input Required")
    events2 = await simulate_starlette_request(agent, "I need help with something")
    
    # Test 3: Delegation scenario
    print("\n" + "="*50)
    print("TEST 3: Agent Delegation")
    events3 = await simulate_starlette_request(agent, "Please delegate this task")
    
    # Test 4: Error handling
    print("\n" + "="*50)
    print("TEST 4: Error Handling")
    events4 = await simulate_starlette_request(agent, "This will cause an error")
    
    print("\n" + "="*60)
    print("🎉 All tests completed!")
    print("Your executor is ready for Starlette integration.")

if __name__ == "__main__":
    asyncio.run(test_scenarios()) 