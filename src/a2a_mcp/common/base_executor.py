""" 
This is the base class for the development of new agents. 
They are 2 helper classes 
1. uses the base task_delegator to delegate tasks to other agents.
2. uses context_memory to store the context of the task.

"""

from typing import Dict, List, Optional, AsyncGenerator, Any, cast
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater, InMemoryTaskStore
from a2a.types import (
    Task,
    TaskState,
    Message,
    Part,
    TextPart,
    DataPart,
    FilePart,
    InvalidParamsError
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.context_memory import ContextMemory
from a2a_mcp.common.task_delegator import TaskDelegator
from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

def artifact_dict_to_parts(artifact_dict: Dict[str, Any]) -> List[Part]:
    """Convert artifact dictionary to list of parts.
    
    Args:
        artifact_dict: Dictionary containing artifact data
        
    Returns:
        List[Part]: List of parts for the artifact
    """
    return [Part(root=TextPart(text=json.dumps(artifact_dict, indent=2, ensure_ascii=False)))]

class BaseAgentExecutor(AgentExecutor):
    """Base executor class with memory management and delegation capabilities.
    
    This executor provides:
    1. Context memory management for maintaining conversation history
    2. Task delegation capabilities via TaskDelegator
    3. Proper type safety and error handling
    """
    
    def __init__(self, agent: BaseAgent, task_store: InMemoryTaskStore):
        """Initialize the executor with an agent and task store.
        
        Args:
            agent: The base agent implementation
            task_store: Store for maintaining task history
        """
        self.agent = agent
        self.task_store = task_store
        self.context_stores: Dict[str, ContextMemory] = {}
        self.delegator: Optional[TaskDelegator] = None
        self.ongoing_tasks: List[AsyncGenerator[dict, None]] = []

    def _format_part_content(self, part: Part) -> str:
        """Format a message part's content for history.
        
        Args:
            part: Message part to format
            
        Returns:
            str: Formatted content
        """
        if isinstance(part.root, TextPart):
            return part.root.text
        if isinstance(part.root, DataPart):
            return f"[Data: {json.dumps(part.root.data, ensure_ascii=False)}]"
        if isinstance(part.root, FilePart):
            return f"[File: {part.root.file.name}]"
        return str(part.root)

    def process_history(self, context_store: ContextMemory) -> str:
        """Process conversation history from context memory.
        
        Args:
            context_store: Context memory containing tasks
            
        Returns:
            str: Formatted conversation history
        """
        lines = []
        for task in context_store.tasks:
            if not task.history:
                continue
                
            lines.append(f"=== Task {task.id} ===")
            for message in task.history:
                if not (hasattr(message, 'kind') and message.kind == 'message'):
                    continue
                    
                if message.parts:
                    parts = [self._format_part_content(part) for part in message.parts]
                    if parts:
                        lines.append(f"{message.role}: {' '.join(parts)}")
            lines.append("")
            
        return "\n".join(lines)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the agent with proper memory management and delegation.
        
        Args:
            context: Request context containing task info
            event_queue: Queue for task events
        """
        if error := self._validate_request(context):
            raise ServerError(error=InvalidParamsError())

        logger.info(f'Executing agent {self.agent.agent_name}')
        print(f"🚀 Executing A2A-compliant agent: {self.agent.agent_name}")
        
        query = context.get_user_input()
        print(f"📝 User Query: {query}")
        
        message = cast(Message, context.message)  # Safe cast after validation
        task = context.current_task or new_task(message)
        if not context.current_task:
            event_queue.enqueue_event(task)

        task_id = task.id
        context_id = task.contextId
        updater = TaskUpdater(event_queue, task_id, context_id)

        # Initialize TaskDelegator
        self.delegator = TaskDelegator(updater, self.agent, context_id)
        
        # Initial working message
        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )
        updater.update_status(TaskState.working, working_message)

        # Memory management
        if context_id not in self.context_stores:
            self.context_stores[context_id] = ContextMemory()
        context_store = self.context_stores[context_id]
        
        if existing_task := context_store.get_task(task_id):
            context_store.update_task(task_id, task)
            logger.info(f'Updated task {task_id} in context')
        else:
            context_store.add_task(task)
            logger.info(f'Added new task {task_id} to context')

        try:
            # Get history and invoke agent
            task_history = await self.task_store.get(task_id)
            if task_history:
                logger.info(f'History: {task_history.model_dump_json(indent=2, exclude_none=True)}')
            
            history = self.process_history(context_store)
            response = await self.agent.invoke(query, context_id, task_id, history)
            
            print(f"🤖 Agent Response: action={response.action}, status={response.status}")
            print(f"   Message: {response.message}")

            # Handle response based on action
            if response.action == "call_next_agent":
                print(f"🔄 Delegating to agent: {response.agent_name} (input_required)")
                delegation_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.input_required, delegation_message, final=False)

                # Use TaskDelegator for delegation
                if stream := await self.delegator.delegate_task(response):
                    self.ongoing_tasks.append(stream)
                
                # Use TaskDelegator's stream management
                delegation_complete = await self.delegator.manage_streams(
                    self.ongoing_tasks,
                    response.agent_name or "unknown_agent"
                )
                
            elif response.status == "completed":
                if response.artifacts and isinstance(response.artifacts, dict):
                    parts = artifact_dict_to_parts(response.artifacts)
                    updater.add_artifact(parts, name=f'{self.agent.agent_name}-result')
                else:
                    part = Part(root=TextPart(text=response.message))
                    updater.add_artifact([part], name=f'{self.agent.agent_name}-result')
                updater.complete()
                
            elif response.status == "input_required" and response.action == "answer":
                print("⏸️  Task paused - waiting for user input")
                input_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.input_required, input_message, final=True)
                
            elif response.status == "failed":
                print("❌ Task failed")
                failed_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.failed, failed_message, final=True)
                
            else:
                print(f"🔄 Unknown status '{response.status}' - treating as working")
                working_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                updater.update_status(TaskState.working, working_message)
                
        except Exception as e:
            logger.error(f"Execution error: {e}")
            print(f"💥 Exception occurred: {e}")
            error_message = new_agent_text_message(
                f"Internal error: {str(e)}",
                task.contextId,
                task.id,
            )
            updater.update_status(TaskState.failed, error_message, final=True)

    def _validate_request(self, context: RequestContext) -> Optional[InvalidParamsError]:
        """Validate the incoming request.
        
        Args:
            context: Request context to validate
            
        Returns:
            Optional[InvalidParamsError]: Error if validation fails
        """
        if not context.message:
            return InvalidParamsError()
        return None

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel ongoing execution.
        
        Args:
            context: Request context
            event_queue: Event queue
        """
        # TODO: Implement proper cancellation logic
        # - Stop ongoing streams
        # - Clean up resources
        # - Update task status
        pass
    