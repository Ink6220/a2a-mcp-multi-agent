## This is a very simple executor that just calls invoke() and handles the response based on the A2A protocol
## This is used to test the invoke() method of the agent

import logging
import asyncio
import json

from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Task, Message, Part, Role, AgentCard
from a2a.utils import new_agent_text_message, new_task
from a2a.server.agent_execution import AgentExecutor, RequestContext
from uuid import uuid4
from a2a_mcp.common.task_delegator import TaskDelegator
from typing import AsyncGenerator, List, Dict, Any
from a2a_mcp.common.base_agent.base_agent import ResponseFormat

logger = logging.getLogger(__name__)

def artifact_dict_to_parts(artifact_dict: Dict[str, Any]) -> List[Part]:
    return [Part(root=TextPart(text=json.dumps(artifact_dict, indent=2)))]

class GenericAgentExecutor(AgentExecutor):
    """
    A2A Protocol Compliant Executor for ResponseFormat objects
    Inherits from AgentExecutor for full A2A SDK compatibility.
    """
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.delegator: TaskDelegator
        self.ongoing_tasks: list[AsyncGenerator[dict, None]] = []

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
        
        # A2A TaskUpdater for local state management
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        # TaskDelegator for delegation to remote agents
        self.delegator = TaskDelegator(updater, self.agent, task.contextId) # instantiate the delegator


        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )

        # sends message via SSE to client
        updater.update_status(TaskState.working, working_message)
        try:
            session_id = task.contextId
            response_dict = await self.agent.invoke(query, session_id, task.id)
            
            # Convert dict back to ResponseFormat for easier handling
            response_obj = ResponseFormat(**response_dict)
            
            print(f"🤖 Agent Response: action={response_obj.action}, status={response_obj.status}")
            print(f"   Message: {response_obj.message}")

            # Delegation logic
            if response_obj.action == "call_next_agent":
                print(f"🔄 Delegating to agent: {response_obj.agent_name} (input_required)")
                delegation_message = new_agent_text_message(
                    response_obj.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.input_required, delegation_message, final=False)

                # Send message to the next agent
                stream = await self.delegator.delegate_task(response_obj)
                if stream is not None:
                    self.ongoing_tasks.append(stream)

                # manage the streams using methods from the delegator
                delegation_complete = await self.manage_streams(
                    self.ongoing_tasks, 
                    updater, 
                    response_obj.agent_name or "unknown_agent"
                )
                
                # TODO: After delegation completes, collect artifacts and create final response

            elif response_obj.status == "completed":
                # Normal task completion - use real A2A types
                if response_obj.artifacts:
                    # add artifact id checking / logging can be done here
                    parts = artifact_dict_to_parts(response_obj.artifacts)
                    updater.add_artifact(parts, name=f'{self.agent.agent_name}-result')
                else:
                    part = Part(root=TextPart(text=response_obj.message))
                    updater.add_artifact([part], name=f'{self.agent.agent_name}-result')
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

    async def manage_streams(self, ongoing_streams, task_updater, agent_name="remote_agent"):
        """
        Consumes all ongoing async generator streams, updates the task, and returns True if all streams are complete.
        """
        logger = logging.getLogger(__name__)
        streams_done = [False] * len(ongoing_streams)
        tasks = []

        async def consume_stream(idx, stream):
            try:
                async for event in stream:
                    logger.info(f"[{agent_name}] Stream {idx} event: {event}")
                    # Handle event types
                    if event.get("type") == "Message":
                        # Create proper message for task update
                        message = new_agent_text_message(
                            event.get("content", str(event)),
                            task_updater.context_id,
                            task_updater.task_id,
                        )
                        task_updater.update_status(TaskState.working, message)
                    elif event.get("type") == "TaskArtifactUpdateEvent":
                        # Add artifact to task
                        artifact = event.get("artifact")
                        if artifact:
                            task_updater.add_artifact(artifact)
                    elif event.get("type") == "error":
                        # Handle error events
                        error_message = new_agent_text_message(
                            f"Remote agent error: {event.get('error', 'Unknown error')}",
                            task_updater.context_id,
                            task_updater.task_id,
                        )
                        task_updater.update_status(TaskState.failed, error_message)
                    # Add more event types as needed
            except Exception as e:
                logger.error(f"[{agent_name}] Stream {idx} error: {e}")
                error_message = new_agent_text_message(
                    f"Stream processing error: {str(e)}",
                    task_updater.context_id,
                    task_updater.task_id,
                )
                task_updater.update_status(TaskState.failed, error_message)
            finally:
                streams_done[idx] = True

        # Launch all stream consumers
        for idx, stream in enumerate(ongoing_streams):
            tasks.append(asyncio.create_task(consume_stream(idx, stream)))

        # Wait for all streams to finish
        await asyncio.gather(*tasks)

        # All streams are done if all True
        return all(streams_done)
