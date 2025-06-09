## This is a very simple executor that just calls invoke() and handles the response based on the A2A protocol
## This is used to test the invoke() method of the agent

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.base_agent.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GenericAgentExecutor(AgentExecutor):
    """Simplified AgentExecutor that black boxes the agent and just calls invoke()."""

    def __init__(self, agent: BaseAgent):
        self.agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None: # Takes default arguments from AgentExecutor
        logger.info(f'Executing agent {self.agent.agent_name}')
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        task = context.current_task

        # Create task if it doesn't exist
        if not task:
            if context.message is None:
                raise ServerError(error=InvalidParamsError()) # no message in context
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.contextId) # TaskUpdater is managed by us manually

        # Send initial "working" status to show processing has started
        updater.update_status(
            TaskState.working,
            new_agent_text_message(
                "Processing your request...",
                task.contextId, # contextId is the sessionId for simplicity
                task.id,
            ),
        )

        try:
            # Simply call invoke() method - this is the "black box" approach
            session_id = task.contextId  # Using contextId as session_id
            result = await self.agent.invoke(query, session_id)
            
            # Handle the response based on A2A protocol
            if result['is_task_complete']:
                # Task is complete - add artifact and mark as complete
                part = TextPart(text=result['content'])
                updater.add_artifact(
                    [part],  # type: ignore  # TextPart is compatible with Part at runtime
                    name=f'{self.agent.agent_name}-result',
                )
                updater.complete()
            elif result['require_user_input']:
                # Task needs user input
                updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        result['content'],
                        task.contextId,
                        task.id,
                    ),
                    final=True,
                )
            else:
                # Task is still working
                updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        result['content'],
                        task.contextId,
                        task.id,
                    ),
                )

        except Exception as e:
            logger.error(f"Error executing agent {self.agent.agent_name}: {e}")
            updater.update_status(
                TaskState.input_required,
                new_agent_text_message(
                    "An error occurred while processing your request.",
                    task.contextId,
                    task.id,
                ),
                final=True,
            )

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())