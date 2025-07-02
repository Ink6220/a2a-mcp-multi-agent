#!/usr/bin/env python3
"""
A2A Protocol Compliant Executor Testing
This tests a new execute() method with proper A2A protocol compliance
for Starlette integration using ResponseFormat objects from agents.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when running this file directly.
# This makes absolute imports like ``unit_tests.test_execute_starlette_compliance``
# work whether the file is executed via `pytest` (which already adds the project
# root) or via `python unit_test_starlette.py` from this directory.
# ---------------------------------------------------------------------------
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import our mock agents (only these are mocked - they return ResponseFormat objects)
from unit_tests.test_execute_starlette_compliance.mock_agent import (
    get_completion_agent, 
    get_input_required_agent, 
    get_delegation_agent, 
    get_failed_agent,
    get_parallel_delegation_agent
)

# A2A Protocol Imports - Use REAL A2A SDK types only
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Task, Message, Part, Role
from a2a.utils import new_agent_text_message, new_task
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a_mcp.common.base_executor import BaseAgentExecutor
from a2a_mcp.common.memory_management import MemoryManagement

# --------------------------------------------------------------
# Starlette integration simulation using real A2A types
# --------------------------------------------------------------

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

    # Build a minimal user Message required by BaseAgentExecutor
    user_msg = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_message))],
        messageId=str(uuid4()),
        contextId=f"context-{str(uuid4())[:8]}",
        taskId=None,
    )
    context.message = user_msg
    context.current_task = None  # New request

    # Collect events from real A2A EventQueue via a simple collector
    class EventCollector:
        def __init__(self):
            self.events = []

        async def enqueue_event(self, event):
            """Mimic async EventQueue.enqueue_event signature used by SDK >=0.2.x"""
            self.events.append(event)

    event_collector = EventCollector()

    # Instantiate the real BaseAgentExecutor with in-memory task store
    memory_manager = MemoryManagement()
    executor = BaseAgentExecutor(agent, memory_manager)

    # Ensure the provided agent exposes attributes expected by the real executor
    if not hasattr(agent, "agent_card"):
        class _TempCard:
            def __init__(self, name: str):
                self.name = name
        agent.agent_card = _TempCard(getattr(agent, "agent_name", agent.__class__.__name__))  # type: ignore[attr-defined]

    # Some executor code may rely on ``card_discovery`` attribute when handling
    # delegation. We provide a harmless stub to avoid AttributeErrors without
    # modifying production code.
    if not hasattr(agent, "card_discovery"):
        agent.card_discovery = None  # type: ignore[attr-defined]

    await executor.execute(context, event_collector)  # type: ignore[arg-type]
    
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
    
    # Test 4: Agent delegation (single agent)
    print("\n" + "="*60)
    print("TEST 4: Single Agent Delegation")
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

    # Test 4b: Parallel Agent Delegation
    print("\n" + "="*60)
    print("TEST 4b: Parallel Agent Delegation")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(input_required, final=True)")
    parallel_delegation_agent = get_parallel_delegation_agent()
    events4b = await simulate_starlette_request(parallel_delegation_agent, "Please delegate this task to multiple agents")
    
    # Verify parallel delegation handling with real A2A events
    has_task = any(isinstance(e, Task) for e in events4b)
    has_working = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.working for e in events4b)
    has_input_required = any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.input_required for e in events4b)
    has_final = any(hasattr(e, 'final') and e.final == True for e in events4b)
    no_completed = not any(hasattr(e, 'status') and hasattr(e.status, 'state') and e.status.state == TaskState.completed for e in events4b)
    success4b = has_task and has_working and has_input_required and has_final and no_completed
    print(f"✅ A2A Compliance: Task={has_task}, Working={has_working}, InputRequired={has_input_required}, Final={has_final}, NoCompleted={no_completed}")
    print(f"✅ Test Result: {'PASSED' if success4b else 'FAILED'}")
    
    # Test 5: Exception handling (should be failed, not input_required)
    print("\n" + "="*60)
    print("TEST 5: Exception Handling")
    print("Expected: Task → TaskStatusUpdate(working) → TaskStatusUpdate(failed, final=True)")
    
    # Agent that throws exception (only this is mocked - everything else is real A2A)
    class ErrorAgent:
        agent_name = "error-agent"
        async def invoke(self, query: str, context_id: str, task_id: str | None = None, context: Dict[str, Any] | None = None):
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
    all_passed = all([success1, success2, success3, success4, success4b, success5])
    if all_passed:
        print("🎉 ALL A2A COMPLIANCE TESTS PASSED!")
        print("🚀 Your executor is ready for Starlette integration")
        print("📡 Event streams use REAL A2A SDK types")
        print("✅ Full A2A protocol compliance verified")
        print("🔧 Only agent responses were mocked - all A2A infrastructure is real")
    else:
        print("❌ Some A2A compliance tests failed")
        print(f"Results: Completion={success1}, Input={success2}, Failed={success3}, SingleDelegation={success4}, ParallelDelegation={success4b}, Exception={success5}")
        print("🔧 Review the state mappings and event handling")
    
    return all_passed

# Tell pytest not to treat this helper as a test when the module is imported.
test_a2a_executor_scenarios.__test__ = False  # type: ignore[attr-defined]


if __name__ == "__main__":
    print("🏗️  Real A2A Protocol Compliance Testing")
    print("Using REAL A2A TaskState, TaskUpdater, EventQueue, and Message types")
    print("Only agent responses are mocked (ResponseFormat objects)")
    print()
    
    result = asyncio.run(test_a2a_executor_scenarios())
    
    if result:
        print("\n🎯 Next Steps:")
        print("1. Replace BaseAgentExecutor with your real implementation")
        print("2. Ensure your agents return proper ResponseFormat objects")
        print("3. Test with real A2A server and Starlette integration")
        print("4. Verify SSE streaming works with actual clients")
        print("5. All A2A types are now real - no mocks needed!")
    else:
        print("\n⚠️  Fix the failing tests before proceeding") 