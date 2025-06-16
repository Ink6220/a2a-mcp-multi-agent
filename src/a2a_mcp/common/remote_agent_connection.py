from typing import Callable, AsyncGenerator
import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Task,
    Message,
    MessageSendParams,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    SendMessageRequest,
    SendStreamingMessageRequest,
    JSONRPCErrorResponse,
)
from uuid import uuid4

TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task]


class RemoteAgentConnections:
    """A class to hold the connections to the remote agents."""

    def __init__(self, client: httpx.AsyncClient, agent_card: AgentCard):
        self.agent_client = A2AClient(client, agent_card)
        self.card = agent_card
        self.pending_tasks = set()

    def get_agent(self) -> AgentCard:
        return self.card

    async def send_message(
        self,
        request: MessageSendParams,
        task_callback: TaskUpdateCallback | None,
    ) -> Task | Message | None:
        if self.card.capabilities.streaming:
            task = None
            async for response in self.agent_client.send_message_streaming(
                SendStreamingMessageRequest(id=str(uuid4()), params=request)
            ):
                if not response.root.result:
                    return response.root.error
                event = response.root.result
                if isinstance(event, Message):
                    return event
                if task_callback and event:
                    task = task_callback(event, self.card)
                if hasattr(event, 'final') and event.final:
                    break
            return task
        else:
            response = await self.agent_client.send_message(
                SendMessageRequest(id=str(uuid4()), params=request)
            )
            if isinstance(response.root, JSONRPCErrorResponse):
                return response.root.error
            if isinstance(response.root.result, Message):
                return response.root.result
            if task_callback:
                task_callback(response.root.result, self.card)
            return response.root.result

    async def send_message_streaming(
        self,
        request: MessageSendParams,
    ) -> AsyncGenerator[Task | Message, None]:
        """
        Async generator version: yields events as they arrive.
        Use when you want to stream and process incrementally.
        """
        if not self.card.capabilities.streaming:
            # For non-streaming agents, yield once then stop
            response = await self.agent_client.send_message(
                SendMessageRequest(id=str(uuid4()), params=request)
            )
            if isinstance(response.root, JSONRPCErrorResponse):
                yield response.root.error
            else:
                yield response.root.result
            return

        async for response in self.agent_client.send_message_streaming(
            SendStreamingMessageRequest(id=str(uuid4()), params=request)
        ):
            if not response.root.result:
                yield response.root.error
                return
            yield response.root.result  # yield each intermediate update
            if hasattr(response.root.result, 'final') and response.root.result.final:
                return
