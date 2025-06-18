## This is a very simple executor that just calls invoke() and handles the response based on the A2A protocol
## This is used to test the invoke() method of the agent

import logging

from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Task, Message, Part, Role
from a2a.utils import new_agent_text_message, new_task
from a2a.server.agent_execution import AgentExecutor, RequestContext
from uuid import uuid4

logger = logging.getLogger(__name__)

class GenericAgentExecutor(AgentExecutor):
    """
    A2A Protocol Compliant Executor for ResponseFormat objects
    Inherits from AgentExecutor for full A2A SDK compatibility.
    """
    def __init__(self, agent):
        super().__init__()
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue):
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
        query = context.get_user_input()
        print(f"📝 User Query: {query}")
        
        # Create/get task using real A2A utilities
        task = context.current_task
        # if no task, create a new one
        if not task:
            # Do not assign to context.message directly if it's a property
            # Instead, skip or use a method if available (for test, we just create a new message)
            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=query))],
                messageId=str(uuid4()),
                contextId=f"context-{str(uuid4())[:8]}",
                taskId=None
            )
            task = new_task(message)
            event_queue.enqueue_event(task)
            print(f"📋 Created new task: {task.id}")
        
        # Create real A2A TaskUpdater for proper state management
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )

        # sends message via SSE to client
        updater.update_status(TaskState.working, working_message)
        try:
            session_id = task.contextId
            history = "" # TODO: Load Memory
            response_obj = await self.agent.invoke(query, session_id, task.id, history)
            print(f"🤖 Agent Response: action={response_obj.action}, status={response_obj.status}")
            print(f"   Message: {response_obj.message}")
            if response_obj.action == "call_next_agent":
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

    async def cancel(self, context: RequestContext, event_queue):
        # No-op for test executor
        pass
