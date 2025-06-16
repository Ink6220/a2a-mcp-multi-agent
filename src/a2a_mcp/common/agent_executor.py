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
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.context_memory import ContextMemory
logger = logging.getLogger(__name__)


class GenericAgentExecutor(AgentExecutor):
    """AgentExecutor used by the tragel agents."""

    def __init__(self, agent: BaseAgent, task_store: InMemoryTaskStore):  
        self.agent = agent
        self.task_store = task_store
        self.context_store = ContextMemory()

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
                                        parts.append(f"[Data: {json.dumps(root_part.data)}]")
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
        logger.info(f'Executing agent {self.agent.agent_name}')
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()

        task = context.current_task

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        task_id = context.task_id
        context_id = context.context_id

        updater = TaskUpdater(event_queue, task.id, context_id)
        existing_task = self.context_store.get_task(task_id)

        if existing_task:
            # Update existing task
            self.context_store.update_task(task_id, task)
            logger.info(f'Updated existing task {task_id} in context memory')
        else:
            # Add new task
            self.context_store.add_task(task)
            logger.info(f'Added new task {task_id} to context memory')

        task_history = await self.task_store.get(task_id)
        if(task_history): logger.info(f'History: {task_history.model_dump_json(indent=2, exclude_none=True)}')
        history = self.postprocess(self.context_store)

        # TODO: Implement agent.stream() later
        async for item in self.agent.invoke(query, context_id, task_id, history):
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
                continue
            
            print("item", item)
            if isinstance(item, ResponseFormat):
                is_task_complete = item.status == "completed" #item['is_task_complete']
                require_user_input = (item.status == "input_required" or item.status == "failed") #item['require_user_input']

                if is_task_complete:
                    # Always create a TextPart for the response content
                    part = TextPart(text=item.message)

                    updater.add_artifact(
                        [part],
                        name=f'{self.agent.agent_name}-result',
                    )
                    updater.complete()
                    break
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
                    break
                else:
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item.message,
                            task.contextId,
                            task.id,
                        ),                    )

    def _transform_task_history(self, task_history) -> dict:
        """Transform task history to simplified conversation format grouped by contextId"""
        import json
        
        result = {}
        
        if hasattr(task_history, 'history') and task_history.history:
            context_id = getattr(task_history, 'contextId', 'unknown')
            
            conversations = []
            for message in task_history.history:
                conversation_entry = {
                    "role": message.role.value if hasattr(message.role, 'value') else str(message.role),
                    "parts": [],
                    "metadata": getattr(message, 'metadata', None)
                }
                
                # Transform parts
                if hasattr(message, 'parts') and message.parts:
                    for part in message.parts:
                        if hasattr(part, 'root'):
                            part_data = part.root
                        else:
                            part_data = part
                            
                        if hasattr(part_data, 'kind'):
                            part_type = part_data.kind
                        elif hasattr(part_data, 'type'):
                            part_type = part_data.type
                        else:
                            part_type = "text"  # default
                            
                        part_entry = {
                            "type": part_type,
                            "metadata": getattr(part_data, 'metadata', None)
                        }
                        
                        # Add content based on part type
                        if part_type == "text":
                            part_entry["text"] = getattr(part_data, 'text', '')
                        elif part_type == "toolUse":
                            part_entry["toolUseId"] = getattr(part_data, 'toolUseId', '')
                            part_entry["toolName"] = getattr(part_data, 'toolName', '')
                            part_entry["input"] = getattr(part_data, 'input', {})
                        elif part_type == "tool":
                            part_entry["toolUseId"] = getattr(part_data, 'toolUseId', '')
                            part_entry["content"] = getattr(part_data, 'content', [])
                            part_entry["status"] = getattr(part_data, 'status', '')
                        else:
                            # For other types, try to get common attributes
                            for attr in ['text', 'content', 'data']:
                                if hasattr(part_data, attr):
                                    part_entry[attr] = getattr(part_data, attr)
                                    break
                        
                        conversation_entry["parts"].append(part_entry)
                
                conversations.append(conversation_entry)
            
            result[context_id] = conversations
        
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _validate_request(self, context: RequestContext) -> bool:
        return False


    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())