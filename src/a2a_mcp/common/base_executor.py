""" 
This is the base class for the development of new agents. 
They are 2 helper classes 
1. uses the base task_delegator to delegate tasks to other agents.
2. uses memory management to store task context and history.

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
    InvalidParamsError,
    Artifact
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from a2a_mcp.common.task_delegator import TaskDelegator
from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.memory_management import MemoryManagement
from a2a_mcp.common.utils import artifact_dict_to_parts, get_message_data, append_message_metadata
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

class BaseAgentExecutor(AgentExecutor):
    """Base executor class with memory management and delegation capabilities.
    
    This executor provides:
    1. Memory management for maintaining conversation history and tool usage
    2. Task delegation capabilities via TaskDelegator
    3. Proper type safety and error handling
    """
    
    def __init__(self, agent: BaseAgent, memory: MemoryManagement):
        """Initialize the executor with an agent and memory manager.
        
        Args:
            agent: The base agent implementation
            memory: Memory management instance for task history
        """
        self.agent = agent
        self.memory = memory
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
        incoming_data = get_message_data(context.message)
        print(f"📝 User Query: {query+"\n"+incoming_data}")
        
        message = cast(Message, context.message)  # Safe cast after validation
        task = context.current_task or new_task(message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
            await self.memory.save(task)

        task_id = task.id
        context_id = task.contextId
        updater = TaskUpdater(event_queue, task_id, context_id)

        # Initialize TaskDelegator
        self.delegator = TaskDelegator(updater, self.agent, context_id, self.memory)
        
        # Initial working message
        working_message = new_agent_text_message(
            "Processing your request...",
            task.contextId,
            task.id,
        )
        working_message = append_message_metadata(working_message, {"agent_name": self.agent.agent_card.name})
        await updater.update_status(TaskState.working, working_message)

        try:
            context_tasks = await self.memory.get_tasks_by_context(context_id)
            
            # Log parameters before invoke
            print(f"\033[92m=== INVOKE PARAMETERS ===\033[0m")
            print(f"Query: {query}")
            print(f"Context ID: {context_id}")
            print(f"Task ID: {task_id}")
            print(f"Context Tasks Count: {len(context_tasks)}")
            if context_tasks:
                for task_id, context_task in context_tasks.items():
                    print(f"  Task {task_id}: {context_task.id}")
            print(f"\033[92m========================\033[0m")
            
            # --- INITIAL INVOKE ---
            response = await self.agent.invoke(query, context_id, task_id, context_tasks)
            
            print(f"🤖 Agent Response: action={response.action}, status={response.status}")
            print(f"   Message: {response.message}")

            # Handle response based on action
            # --- DELEGATION LOOP ---
            while response.action == "call_next_agent":
                agent_names_str = ", ".join(response.agent_names) if response.agent_names else "unknown agents"
                print(f"🔄 Delegating to agents: {agent_names_str} (input_required)")
                delegation_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                delegation_message = append_message_metadata(delegation_message, {"agent_name": self.agent.agent_card.name})
                await updater.update_status(TaskState.input_required, delegation_message, final=False)

                # Use TaskDelegator for parallel delegation
                streams = await self.delegator.delegate_task(response, self.agent.agent_card.name)
                if streams:
                    self.ongoing_tasks.extend(streams)
                
                # Use TaskDelegator's stream management with comma-separated agent names
                delegation_complete = await self.delegator.manage_streams(
                    self.ongoing_tasks,
                    agent_names_str
                )

                # --- FOLLOW-UP INVOKE ---
                # The agent re-evaluates with the new observation
                print("🤔 Agent is re-evaluating with new information...")
                response = await self.agent.follow_up_invoke(
                    query=query, # Pass original query for context
                    context_id=context_id,
                    task_id=task_id,
                    context=context_tasks,
                )
                print(f"🤖 Agent Response after delegation: action={response.action}, status={response.status}")


            if response.status == "completed":
                if response.artifacts and isinstance(response.artifacts, dict):
                    parts = artifact_dict_to_parts(response.artifacts)
                    await updater.add_artifact(parts, name=f'{self.agent.agent_name}-result', metadata={"agent_name": self.agent.agent_card.name})
                else:
                    part = Part(root=TextPart(text=response.message))
                    await updater.add_artifact([part], name=f'{self.agent.agent_name}-result', metadata={"agent_name": self.agent.agent_card.name})
                await updater.complete()
                
            elif response.status == "input_required" and response.action == "answer":
                print("⏸️  Task paused - waiting for user input")
                input_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                input_message = append_message_metadata(input_message, {"agent_name": self.agent.agent_card.name})
                await updater.update_status(TaskState.input_required, input_message, final=True)
                
            elif response.status == "failed":
                print("❌ Task failed")
                failed_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                failed_message = append_message_metadata(failed_message, {"agent_name": self.agent.agent_card.name})
                await updater.update_status(TaskState.failed, failed_message, final=True)
                
            else:
                print(f"🔄 Unknown status '{response.status}' - treating as working")
                working_message = new_agent_text_message(
                    response.message,
                    task.contextId,
                    task.id,
                )
                working_message = append_message_metadata(working_message, {"agent_name": self.agent.agent_card.name})
                await updater.update_status(TaskState.working, working_message)
                
        except Exception as e:
            logger.error(f"Execution error: {e}")
            print(f"💥 Exception occurred: {e}")
            error_message = new_agent_text_message(
                f"Internal error: {str(e)}",
                task.contextId,
                task.id,
            )
            error_message = append_message_metadata(error_message, {"agent_name": self.agent.agent_card.name})
            await updater.update_status(TaskState.failed, error_message, final=True)

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
    