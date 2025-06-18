# task delegator to be instantiated inside the executor 
# Hanldes the logic how to pass tasks to other agents
from typing import AsyncGenerator
from uuid import uuid4
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, MessageSendParams, Part, TextPart, Role, DataPart
from a2a_mcp.common.base_agent.base_agent import ResponseFormat, BaseAgent, MessageSendParams
import json 

class TaskDelegator():
    def __init__(self, updater: TaskUpdater, agent: BaseAgent, task_context_id: str) -> None:
        # updater handles updating parent state and task, adding artifacts etc
        self.task_updater = updater
        self.agent = agent  # Store the agent for later use
        self.task_context_id = task_context_id

    async def delegate_task(self, response_obj: ResponseFormat):
        if response_obj.action != "call_next_agent":
            # Not a delegation action, nothing to do
            return None

        # Extract required fields
        agent_name = response_obj.agent_name
        instruction = response_obj.next_agent_instruction
        artifacts = json.loads(response_obj.artifacts) if response_obj.artifacts else {} # TODO: add schema / custom data here (not included atm)
        assert instruction and agent_name is not None

        # Use the correct method to get the agent card
        target_agent_card = self.agent.card_discovery.get_remote_agent_card_by_name(agent_name)
        if not target_agent_card:
            raise ValueError(f"Agent card for '{agent_name}' not found.")
        
        # Creating a taskId for the new task
        task_id = str(uuid4()) # TODO: add tracking for delegated tasks

        # Construct MessageSendParams (adjust as needed for your actual class)
        request = MessageSendParams(
            message=Message(
                messageId=str(uuid4()),
                taskId=task_id,
                contextId=self.task_context_id,
                parts=[Part(root=TextPart(text=instruction)), Part(root=DataPart(data=artifacts))],
                role=Role.agent,
            ),
        )
        # Return the async generator (stream) for the executor to consume
        return await self.agent.make_remote_agent_connection(target_agent_card, request)


    
