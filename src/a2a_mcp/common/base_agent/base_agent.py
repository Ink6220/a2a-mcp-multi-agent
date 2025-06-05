from abc import ABC, abstractmethod
from typing import Any, Dict, Literal, Union, AsyncGenerator
from collections.abc import AsyncIterable
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from a2a_mcp.common.types import CustomAgentCard
import json
import uuid
import time
from colorama import Fore, Style, init

class ResponseFormat(BaseModel):
    # TODO: We might need to redo some stuff for the logic here, but for now, we will keep it as is.
    """Respond to the user in this format."""

    action: Literal["answer", "call_next_agent"] = Field(
        ...,
        description="Action to be taken, either respond directly or delegate to another agent."
    )
    status: Literal["input_required", "completed","hang_up"] = Field(
        ...,
        description="The current status of the conversation flow."
    )
    agent_name: str = Field(
        ...,
        description="Name of the agent responsible for the current response, if action is call_next_agent."
    )
    message: str = Field(
        ...,
        description="The message to deliver to the user or to another agent."
    )

class BaseAgent(ABC):
    def __init__(self, model_name: str, agent_card: CustomAgentCard):
        self.model_name = model_name
        self.agent_card: CustomAgentCard = agent_card

        # TODO: Previous implementation was doing agent discovery inside BaseAgent class -> Fix this on Task: Agent Discovery from MCP Server 
        # The cache is always dirty at startup, so that we discovery at least once
        # self._cache_dirty = True
        # self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        # self.cards: dict[str, AgentCard] = {}
        # self.agent_info: str | None = None

        self.model_config = {
            'arbitrary_types_allowed': True,
            'extra': 'allow',
        }

        self.agent_name: str = self.agent_card.name # The name of the agent.
        self.description: str = self.agent_card.description # A brief description of the agent's purpose.
        self.content_types: list[str] = self.agent_card.defaultInputModes # Supported content types.


    @abstractmethod
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        """Invoke the agent with a query and return a single response."""
        pass

    @abstractmethod
    async def stream(self, query: str, context_id: str, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream responses from the agent. Must yield dictionaries with standardized format."""
        pass

    @abstractmethod
    def convert_tool_format(self, tools) -> Any:
        """Convert tools to the format expected by the specific agent implementation."""
        pass

    @abstractmethod
    def parse_agent_response(self, response) -> Dict[str, Any]:
        """Parse the agent's response into standardized format."""
        pass

    @abstractmethod
    def parse_structure_output(self, text: str) -> Union[ResponseFormat, str]:
        """Parse structured output from text."""
        pass

    @abstractmethod
    def root_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        """Generate the root instruction for the agent."""
        pass