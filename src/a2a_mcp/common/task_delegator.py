# task delegator to be instantiated inside the executor 
# Hanldes the logic how to pass tasks to other agents
import logging
import asyncio
from typing import AsyncGenerator, List, Optional
from uuid import uuid4
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, MessageSendParams, Part, TextPart, Role, TaskState, TaskStatus, Artifact
from a2a.utils import new_agent_text_message
from a2a.types import DataPart
from a2a_mcp.common.base_agent.base_agent import ResponseFormat, BaseAgent, MessageSendParams
from a2a_mcp.common.utils import append_message_metadata
import json 
from a2a_mcp.common.memory_management import MemoryManagement

class TaskDelegator():
    def __init__(self, updater: TaskUpdater, agent: BaseAgent, task_context_id: str, memory: Optional[MemoryManagement] = None) -> None:
        # updater handles updating parent state and task, adding artifacts etc
        self.task_updater = updater
        self.agent = agent  # Store the agent for later use
        self.task_context_id = task_context_id
        self.memory = memory

    async def delegate_task(self, response_obj: ResponseFormat, sender_name: str) -> List[AsyncGenerator[dict, None]]:
        """Delegates tasks to multiple agents in parallel based on ResponseFormat.
        
        Args:
            response_obj: The response object containing delegation info
            sender_name: Name of the delegating agent
            
        Returns:
            List of async generators for each delegation stream
        """
        if response_obj.action != "call_next_agent":
            # Not a delegation action, nothing to do
            return []

        # Extract required fields
        agent_names = response_obj.agent_names
        instructions = response_obj.next_agent_instructions
        artifacts = json.loads(response_obj.artifacts) if response_obj.artifacts else {}
        
        streams = []
        
        # Process each delegation in parallel
        for agent_name, instruction in zip(agent_names, instructions):
            # Get agent card for delegation
            target_agent_card = self.agent.card_discovery.get_remote_agent_card_by_name(agent_name)
            if not target_agent_card:
                logger.error(f"Agent card for '{agent_name}' not found.")
                continue

            # Create task ID for this delegation
            task_id = str(uuid4())

            # Construct message params
            request = MessageSendParams(
                message=Message(
                    messageId=str(uuid4()),
                    taskId=task_id,
                    contextId=self.task_context_id,
                    metadata={"agent_name": sender_name},
                    parts=[Part(root=TextPart(text=instruction)), Part(root=DataPart(data=artifacts))],
                    role=Role.agent,
                ),
            )

            # Get stream for this delegation
            try:
                stream = await self.agent.make_remote_agent_connection(target_agent_card, request)
                if stream:
                    streams.append(stream)
            except Exception as e:
                logger.error(f"Failed to create stream for agent {agent_name}: {e}")
                continue

        return streams

    async def manage_streams(self, ongoing_streams: List[AsyncGenerator], agent_names: str = "remote_agent"):
        """
        Consumes all ongoing async generator streams, updates the task, and returns True if all streams are complete.
        
        Args:
            ongoing_streams: List of stream generators to manage
            agent_names: Comma-separated list of agent names for logging
        """
        logger = logging.getLogger(__name__)
        streams_done = [False] * len(ongoing_streams)
        tasks = []

        async def consume_stream(idx, stream):
            try:
                async for event in stream:
                    logger.info(f"[{agent_names}] Stream {idx} event: {event}")
                    # Normalize event discriminator to Fast-MCP standard
                    evt_kind = event.get("kind") or event.get("type")
                    if evt_kind == "message":
                        # Create proper message for task update
                        message = new_agent_text_message(
                            event.get("content", str(event)),
                            self.task_updater.context_id,
                            self.task_updater.task_id,
                        )
                        message = append_message_metadata(message, {"agent_name": agent_names})
                        await self.task_updater.update_status(TaskState.working, message)

                    elif evt_kind == "status-update":
                        if event.get('status'):
                            task_status = event.get('status', None)
                            if isinstance(task_status, TaskStatus) and task_status.message:
                                message_status = task_status.message
                                
                                # Create proper message for task update
                                root_part = message_status.parts[0].root if message_status.parts else None
                                if hasattr(root_part, "text"):
                                    root_text_val = getattr(root_part, "text")
                                else:
                                    root_text_val = str(root_part)
                                message = new_agent_text_message(
                                    event.get("content", root_text_val),
                                    self.task_updater.context_id,
                                    self.task_updater.task_id,
                                )
                                message = append_message_metadata(message, {"agent_name": agent_names})
                                await self.task_updater.update_status(TaskState.working, message)
                    elif evt_kind == "artifact-update":
                        artifact = event.get("artifact")
                        
                        if artifact:
                            # Ensure proper type conversion
                            if isinstance(artifact, dict):
                                parts = artifact.get('parts', [])
                                await self.task_updater.add_artifact(
                                    parts=parts,
                                    metadata={"agent_name": agent_names}
                                )
                            elif hasattr(artifact, 'parts'):
                                await self.task_updater.add_artifact(
                                    parts=artifact.parts,
                                    metadata={"agent_name": agent_names}
                                )
                    elif evt_kind == "error":
                        # Handle error events
                        error_message = new_agent_text_message(
                            f"Remote agent error: {event.get('error', 'Unknown error')}",
                            self.task_updater.context_id,
                            self.task_updater.task_id,
                        )
                        error_message = append_message_metadata(error_message, {"agent_name": agent_names})
                        await self.task_updater.update_status(TaskState.failed, error_message)
            except Exception as e:
                logger.error(f"[{agent_names}] Stream {idx} error: {e}")
                error_message = new_agent_text_message(
                    f"Stream processing error: {str(e)}",
                    self.task_updater.context_id,
                    self.task_updater.task_id,
                )
                error_message = append_message_metadata(error_message, {"agent_name": agent_names})
                await self.task_updater.update_status(TaskState.failed, error_message)
            finally:
                streams_done[idx] = True

        # Launch all stream consumers
        for idx, stream in enumerate(ongoing_streams):
            tasks.append(asyncio.create_task(consume_stream(idx, stream)))

        # Wait for all streams to finish
        await asyncio.gather(*tasks)

        # All streams are done if all True
        return all(streams_done)


    
