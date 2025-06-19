import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
import logging
import asyncio
import json
from a2a.types import (
    DataPart,
    InvalidParamsError,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
    FilePart,
    Part,
    UnsupportedOperationError,
    InternalError,
    MessageSendParams,
    MessageSendConfiguration,
    Message,
)
from uuid import uuid4
from typing import AsyncGenerator, List, Dict, Any
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.task_delegator import TaskDelegator
from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.context_memory import ContextMemory
logger = logging.getLogger(__name__)
import httpx  

def artifact_dict_to_parts(artifact_dict: Dict[str, Any]) -> List[Part]:
    return [Part(root=TextPart(text=json.dumps(artifact_dict, indent=2, ensure_ascii=False)))]

class GenericDelegatorAgentExecutor(AgentExecutor):
    """AgentExecutor used by the tragel agents."""

    def __init__(self, agent: BaseAgent, task_store: InMemoryTaskStore):  
        self.agent = agent
        self.task_store = task_store
        self.context_stores: Dict[ContextMemory] = {}
        self.delegator: TaskDelegator
        self.ongoing_tasks: list[AsyncGenerator[dict, None]] = []

    def postprocess(self, context_store: ContextMemory) -> str:
        """Process history from all tasks in the context memory
        
        Args:
            context_store: ContextMemory containing multiple tasks
            
        Returns:
            str: Formatted history from all tasks
        """
        lines = []
        
        # Process all tasks in the context memory
        for task in context_store.tasks:
            if task.history:
                lines.append(f"=== Task {task.id} ===")
                for message in task.history:
                    if hasattr(message, 'kind') and message.kind == 'message':
                        if message.parts:
                            parts = []
                            for part in message.parts:
                                if hasattr(part, 'root'):
                                    root_part = part.root
                                    if hasattr(root_part, 'text'):
                                        parts.append(root_part.text)
                                    elif hasattr(root_part, 'data'):
                                        parts.append(f"[Data: {json.dumps(root_part.data, ensure_ascii=False)}]")
                                    elif hasattr(root_part, 'file') and hasattr(root_part.file, 'name'):
                                        parts.append(f"[File: {root_part.file.name}]")
                                    else:
                                        parts.append(str(root_part))
                                else:
                                    if hasattr(part, 'text'):
                                        parts.append(part.text)
                                    else:
                                        parts.append(str(part))
            
                            if parts:
                                lines.append(f"{message.role}: {' '.join(parts)}")
                lines.append("")
        return "\n".join(lines)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Main execution logic - fully A2A compliant using real A2A SDK
        
        Handles ResponseFormat objects and produces proper A2A event stream:
        1. Creates/gets task with proper A2A Task object
        2. Uses real TaskUpdater for state management
        3. Follows A2A state transitions
        4. Creates proper artifacts on completion
        5. Handles delegation and error scenarios
        """
        logger.info(f'Executing agent {self.agent.agent_name}')
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        print(f"🚀 Executing A2A-compliant agent: {self.agent.agent_name}")
        query = context.get_user_input()
        print(f"📝 User Query: {query}")

        task = context.current_task

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        task_id = context.task_id
        context_id = context.context_id

        # A2A TaskUpdater for local state management
        updater = TaskUpdater(event_queue, task.id, context_id)
        
        # TaskDelegator for delegation to remote agents
        self.delegator = TaskDelegator(updater, self.agent, task.contextId) # instantiate the delegator
        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )
        updater.update_status(TaskState.working, working_message) # sends message via SSE to client

        # Get or create context store for this context
        if context_id not in self.context_stores:
            self.context_stores[context_id] = ContextMemory()
        context_store = self.context_stores[context_id]
        
        existing_task = context_store.get_task(task_id)

        if existing_task:
            # Update existing task
            context_store.update_task(task_id, task)
            logger.info(f'Updated existing task {task_id} in context memory')
        else:
            # Add new task
            context_store.add_task(task)
            logger.info(f'Added new task {task_id} to context memory')

        try:
            task_history = await self.task_store.get(task_id)
            if(task_history): logger.info(f'History: {task_history.model_dump_json(indent=2, exclude_none=True)}')
            history = self.postprocess(context_store)

            # TODO: Implement agent.stream() later
            response_obj = await self.agent.invoke(query, task.contextId, task.id, history)
    
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

    def _validate_request(self, context: RequestContext) -> bool:
        return False


    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
    
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
