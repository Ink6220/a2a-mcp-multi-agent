import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
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
    UnsupportedOperationError,
    InternalError,
    MessageSendParams,
    MessageSendConfiguration,
    Message,
)
from uuid import uuid4
import json
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.memory_management import MemoryManagement
import httpx  
from a2a_mcp.common.remote_agent_connection import RemoteAgentConnections

class GenericAgentExecutor(AgentExecutor):
    """AgentExecutor used by the tragel agents."""

    def __init__(self, agent: BaseAgent, memory: MemoryManagement):  
        self.agent = agent
        self.memory = memory

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        print(f'Executing agent {self.agent.agent_name}')
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()

        task = context.current_task

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.contextId)        
        context_tasks = await self.memory.get_tasks_by_context(task.contextId)
        
        # Log parameters before invoke
        print(f"\033[92m=== INVOKE PARAMETERS ===\033[0m")
        print(f"Query: {query}")
        print(f"Context ID: {task.contextId}")
        print(f"Task ID: {task.id}")
        print(f"Context Tasks Count: {len(context_tasks)}")
        if context_tasks:
            for task_id, context_task in context_tasks.items():
                print(f"  Task {task_id}: {context_task.id}")
        print(f"\033[92m========================\033[0m")

        item = await self.agent.invoke(query, task.contextId, task.id, context_tasks)
        # TODO: Implement agent.stream() later

        # Agent to Agent call will return events,
        # Update the relevant ids to proxy back.
        if hasattr(item, 'root') and isinstance(
            item.root, SendStreamingMessageSuccessResponse
        ):
            event = item.root.result
            if isinstance(
                event,
                (TaskStatusUpdateEvent | TaskArtifactUpdateEvent),
            ):
                event_queue.enqueue_event(event)
        
        print("item", item)
        if isinstance(item, ResponseFormat):
            print("\n\n")
            print("got response format")
            if item.action == "answer":
                is_task_complete = item.status == "completed"
                require_user_input = (item.status == "input_required" or item.status == "failed")

                if is_task_complete:
                    # Always create a TextPart for the response content
                    part = TextPart(text=item.message)

                    updater.add_artifact(
                        [part],
                        name=f'{self.agent.agent_name}-result',
                    )
                    updater.complete()
                elif require_user_input:
                    updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item.message,
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                else:
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item.message,
                            task.contextId,
                            task.id,
                        ),
                    )
            elif item.action == "call_next_agent":
                # TODO: Task delegator when action space is call_next_agent to item.agent_name

                # https://github.com/dmesquita/multi-agent-communication-a2a-python/blob/main/server_event_detection_a2a.py
                async with httpx.AsyncClient() as httpx_client:
                    remote_agent_card =  self.agent.card_discovery.get_remote_agent_card_by_name(item.agent_name)
                    remote_agent_connection = RemoteAgentConnections(httpx_client, remote_agent_card)

                    message = Message(
                        role="user",
                        #TODO: parts=[TextPart(text=item.next_agent_instruction), DataPart(data=json.loads(item.next_agent_schema))],
                        parts=[TextPart(text=item.next_agent_instruction)],
                        messageId=str(uuid4()),
                        taskId=str(uuid4()), # TODO: generate task_id
                        contextId=task.contextId, # TODO: Get contextId
                    )

                    payload = MessageSendParams(
                        id=str(uuid4()),
                        message=message,
                        configuration=MessageSendConfiguration(
                            acceptedOutputModes=["text"],
                        ),
                    )

                    async for event in remote_agent_connection.send_message_streaming(payload):
                        if isinstance(event, Message):
                            print("Final message:", event)
                        elif isinstance(event, TaskStatusUpdateEvent):
                            print("Status update:", event)
                        elif isinstance(event, TaskArtifactUpdateEvent):
                            print("Artifact update:", event)
                        else:
                            print("Other event:", event)

                # Mockup Artifact back to client
                # Always create a TextPart for the response content
                part = TextPart(text=item.message)

                updater.add_artifact(
                    [part],
                    name=f'{self.agent.agent_name}-result',
                )
                updater.complete()
            else:
                raise ServerError(error=InternalError(message="Invalid Action Space generated by Agent."))

    def _validate_request(self, context: RequestContext) -> bool:
        return False


    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())