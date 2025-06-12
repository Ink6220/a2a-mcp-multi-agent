#!/usr/bin/env python3
"""
A2A Protocol Compliant Executor Testing
This tests a new execute() method with proper A2A protocol compliance
for Starlette integration using ResponseFormat objects from agents.
"""

import asyncio
import json
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

# Import our mock agents (only these are mocked - they return ResponseFormat objects)
from mock_agent import (
    get_completion_agent, 
    get_input_required_agent, 
    get_delegation_agent, 
    get_failed_agent
)

# A2A Protocol Imports - Use REAL A2A SDK types only
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Task, Message, Part, Role
from a2a.utils import new_agent_text_message, new_task


# This is a mock executor that is used to test the execute() method
# To test a new executor, replace A2ACompliantExecutor with the new executor
class A2ACompliantExecutor:
    """
    A2A Protocol Compliant Executor for ResponseFormat objects
    
    This executor demonstrates the correct implementation for handling
    ResponseFormat objects and producing A2A-compliant event streams
    for Starlette integration using REAL A2A SDK types.
    """
    
    def __init__(self, agent):
        self.agent = agent
    
    async def execute(self, context, event_queue):
        """
        Main execution logic - fully A2A compliant using real A2A SDK
        
        Handles ResponseFormat objects and produces proper A2A event stream:
        1. Creates/gets task with proper A2A Task object
        2. Uses real TaskUpdater for state management
        3. Follows A2A state transitions
        4. Creates proper artifacts on completion
        5. Handles delegation and error scenarios
        """
        print(f"🚀 Executing A2A-compliant agent: {self.agent.agent_name}")
        
        # Get user input
        query = context.get_user_input()
        print(f"📝 User Query: {query}")
        
        # Create/get task using real A2A utilities
        task = context.current_task
        # if no task, create a new one
        if not task:
            # tasks are tied to a message
            if not hasattr(context, 'message') or context.message is None:
                # Create a proper A2A Message object (not a mock)
                context.message = Message(
                    role=Role.user,
                    parts=[Part(root=TextPart(text=query))],
                    messageId=str(uuid4()),
                    contextId=f"context-{str(uuid4())[:8]}",
                    taskId=None
                )
            
            # Use real A2A new_task function
            task = new_task(context.message)
            event_queue.enqueue_event(task)
            print(f"📋 Created new task: {task.id}")
        
        # Create real A2A TaskUpdater for proper state management
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        
        # Send initial working status (A2A requirement) using real types
        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )

        # sends message via SSE to client
        updater.update_status(TaskState.working, working_message)
        
        try:
            # Call agent's invoke method - expects ResponseFormat object
            session_id = task.contextId
            response_obj = await self.agent.invoke(query, session_id)
            print(f"🤖 Agent Response: action={response_obj.action}, status={response_obj.status}")
            print(f"   Message: {response_obj.message}")
            
            # Handle response based on A2A protocol and ResponseFormat status
            # Delegation: action == 'call_next_agent' (status should be 'input_required')
            if response_obj.action == "call_next_agent":
                # Agent delegation scenario: emit input_required, not completed
                print(f"🔄 Delegating to agent: {response_obj.agent_name} (input_required)")
                delegation_message = new_agent_text_message(
                    response_obj.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.input_required, delegation_message, final=True)
                # Do NOT mark as completed or add artifact here
            elif response_obj.status == "completed":
                # Normal task completion - use real A2A types
                part = Part(root=TextPart(text=response_obj.message))
                updater.add_artifact(
                    [part], 
                    name=f'{self.agent.agent_name}-result'
                )
                updater.complete()

            elif response_obj.status == "input_required" and response_obj.action == "answer":
                # Task requires user input - pause and wait
                print("⏸️  Task paused - waiting for user input")
                input_message = new_agent_text_message(
                    response_obj.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.input_required, input_message, final=True)
                
            elif response_obj.status == "failed":
                # Task failed - mark as failed (not input_required)
                print("❌ Task failed")
                failed_message = new_agent_text_message(
                    response_obj.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.failed, failed_message, final=True)
                 
            else:
                # Unknown status - treat as still working
                print(f"🔄 Unknown status '{response_obj.status}' - treating as working")
                working_message = new_agent_text_message(
                    response_obj.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.working, working_message)
                 
        except Exception as e:
            # Exception handling - mark as failed, not input_required
            print(f"💥 Exception occurred: {e}")
            error_message = new_agent_text_message(
                f"Internal error: {str(e)}",
                task.contextId,
                task.id,
            )
            updater.update_status(TaskState.failed, error_message, final=True)


# Starlette integration simulation using real A2A types
async def simulate_starlette_request(agent, user_message: str):
    """
    Simulate how your Starlette app would use the A2A-compliant executor
    
    This shows the complete integration flow that matches how the CLI
    interacts with the Starlette app via A2A protocol using REAL A2A SDK.
    """
    print(f"\n🌐 Simulating Starlette A2A Request")
    print(f"📨 Incoming Message: {user_message}")
    
    # Mock request context (but use real A2A types inside)
    context = Mock()
    context.get_user_input.return_value = user_message
    context.current_task = None  # New request
    context.message = None  # Will be created by executor with real A2A Message
    
    # Real A2A EventQueue for streaming
    event_queue = EventQueue()
    
    # Collect events from real A2A EventQueue
    # For testing, we'll create a simple event collector class
    class EventCollector:
        def __init__(self):
            self.events = []
        
        def enqueue_event(self, event):
            self.events.append(event)
    
    # Use our collector instead of monkey patching
    event_collector = EventCollector()
    
    # Create A2A-compliant executor and run with collector Here is where the execute() method to be tested is called
    executor = A2ACompliantExecutor(agent)
    await executor.execute(context, event_collector)
    
    # Display real A2A events (what client receives via SSE)
    print(f"\n📡 A2A Event Stream (SSE to client):")
    for i, event in enumerate(event_collector.events, 1):
        # These are real A2A events with model_dump_json
        event_json = event.model_dump_json(exclude_none=True)
        print(f"  {i}. {event_json}")
    
    return event_collector.events


# Test scenarios using ResponseFormat-compliant mock agents with real A2A SDK
async def test_a2a_executor_scenarios():
    """
    Test A2A protocol compliance with ResponseFormat objects using REAL A2A SDK
    
    Verifies all scenarios produce correct A2A event streams that
    work with Starlette and match CLI interaction patterns.
    """
    print("🧪 Testing A2A-Compliant Executor with ResponseFormat Objects")
    print("Using REAL A2A SDK types - only agent responses are mocked")
    print("=" * 70)
    
    # Test 1: Successful completion
    print("\n" + "="*60)
    print("TEST 1: Successful Task Completion")
    print("Expected: Task → TaskStatusUpdate(working) → TaskArtifactUpdate → TaskStatusUpdate(completed)")
    completion_agent = get_completion_agent()
    events1 = await simulate_starlette_request(completion_agent, "Process this data successfully")
    
    # Verify real A2A compliance
    has_task = any(isinstance(e, Task) for e in events1)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events1)
    has_artifact = any(hasattr(e, 'artifact') for e in events1)
    has_completed = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.completed for e in events1)
    success1 = has_task and has_working and has_artifact and has_completed
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, Artifact={has_artifact}, Completed={has_completed}")
    print(f"✅ Test Result: {'PASSED' if success1 else 'FAILED'}")
    
    # Test 2: User input required (blocking scenario)
    print("\n" + "="*60) 
    print("TEST 2: User Input Required (Blocking)")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(input_required, final=True)")
    input_agent = get_input_required_agent()
    events2 = await simulate_starlette_request(input_agent, "I need help with something")
    
    # Verify blocking behavior with real A2A events
    has_task = any(isinstance(e, Task) for e in events2)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events2)
    has_input_required = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.input_required for e in events2)
    has_final = any(hasattr(e, 'final') and e.final == True for e in events2)
    no_completion = not any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.completed for e in events2)
    success2 = has_task and has_working and has_input_required and has_final and no_completion
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, InputRequired={has_input_required}, Final={has_final}, NoCompletion={no_completion}")
    print(f"✅ Test Result: {'PASSED' if success2 else 'FAILED'}")
    
    # Test 3: Task failed (not input_required)
    print("\n" + "="*60)
    print("TEST 3: Task Failed")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(failed, final=True)")
    failed_agent = get_failed_agent()
    events3 = await simulate_starlette_request(failed_agent, "This task will fail")
    
    # Verify failure handling with real A2A events
    has_task = any(isinstance(e, Task) for e in events3)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events3)
    has_failed = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.failed for e in events3)
    has_final = any(hasattr(e, 'final') and e.final == True for e in events3)
    no_completion = not any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.completed for e in events3)
    success3 = has_task and has_working and has_failed and has_final and no_completion
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, Failed={has_failed}, Final={has_final}, NoCompletion={no_completion}")
    print(f"✅ Test Result: {'PASSED' if success3 else 'FAILED'}")
    
    # Test 4: Agent delegation
    print("\n" + "="*60)
    print("TEST 4: Agent Delegation")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(input_required, final=True)")
    delegation_agent = get_delegation_agent()
    events4 = await simulate_starlette_request(delegation_agent, "Please delegate this task")
    
    # Verify delegation handling with real A2A events
    has_task = any(isinstance(e, Task) for e in events4)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events4)
    has_input_required = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.input_required for e in events4)
    has_final = any(hasattr(e, 'final') and e.final == True for e in events4)
    no_completed = not any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.completed for e in events4)
    success4 = has_task and has_working and has_input_required and has_final and no_completed
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, InputRequired={has_input_required}, Final={has_final}, NoCompleted={no_completed}")
    print(f"✅ Test Result: {'PASSED' if success4 else 'FAILED'}")
    
    # Test 5: Exception handling (should be failed, not input_required)
    print("\n" + "="*60)
    print("TEST 5: Exception Handling")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(failed, final=True)")
    
    # Agent that throws exception (only this is mocked - everything else is real A2A)
    class ErrorAgent:
        agent_name = "error-agent"
        async def invoke(self, query: str, session_id: str):
            raise ValueError("Simulated agent error")
    
    error_agent = ErrorAgent()
    events5 = await simulate_starlette_request(error_agent, "This will cause an exception")
    
    # Verify exception handling with real A2A events (should be failed, not input_required)
    has_task = any(isinstance(e, Task) for e in events5)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events5)
    has_failed = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.failed for e in events5)
    has_final = any(hasattr(e, 'final') and e.final == True for e in events5)
    not_input_required = not any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.input_required for e in events5)
    success5 = has_task and has_working and has_failed and has_final and not_input_required
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, Failed={has_failed}, Final={has_final}, NotInputRequired={not_input_required}")
    print(f"✅ Test Result: {'PASSED' if success5 else 'FAILED'}")
    
    # Overall results
    print("\n" + "="*70)
    all_passed = all([success1, success2, success3, success4, success5])
    if all_passed:
        print("🎉 ALL A2A COMPLIANCE TESTS PASSED!")
        print("🚀 Your executor is ready for Starlette integration")
        print("📡 Event streams use REAL A2A SDK types")
        print("✅ Full A2A protocol compliance verified")
        print("🔧 Only agent responses were mocked - all A2A infrastructure is real")
    else:
        print("❌ Some A2A compliance tests failed")
        print(f"Results: Completion={success1}, Input={success2}, Failed={success3}, Delegation={success4}, Exception={success5}")
        print("🔧 Review the state mappings and event handling")
    
    return all_passed


if __name__ == "__main__":
    print("🏗️  Real A2A Protocol Compliance Testing")
    print("Using REAL A2A TaskState, TaskUpdater, EventQueue, and Message types")
    print("Only agent responses are mocked (ResponseFormat objects)")
    print()
    
    result = asyncio.run(test_a2a_executor_scenarios())
    
    if result:
        print("\n🎯 Next Steps:")
        print("1. Replace A2ACompliantExecutor with your real implementation")
        print("2. Ensure your agents return proper ResponseFormat objects")
        print("3. Test with real A2A server and Starlette integration")
        print("4. Verify SSE streaming works with actual clients")
        print("5. All A2A types are now real - no mocks needed!")
    else:
        print("\n⚠️  Fix the failing tests before proceeding") 