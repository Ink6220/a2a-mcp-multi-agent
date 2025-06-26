from abc import ABC, abstractmethod
from typing import Any, Dict, Literal, Union, AsyncGenerator, Self, Optional, List
from collections.abc import AsyncIterable
from pydantic import BaseModel, Field, model_validator, ValidationError
from a2a.types import MessageSendParams, AgentCard, Task, TextPart, FilePart, DataPart
from a2a_mcp.common.types import CustomAgentCard, AgentCard, ToolCall, ToolOutput
from a2a_mcp.common.card_discovery import A2ACardDiscovery
import json
import uuid
import time
from colorama import Fore, Style, init
from datetime import datetime, timezone, timedelta

# Define UTC+7 timezone
UTC_PLUS_7 = timezone(timedelta(hours=7))

def current_time_utc7_str() -> str:
    return datetime.now(UTC_PLUS_7).isoformat()

class ResponseFormat(BaseModel):
    """Standardized response for LLM Agent interactions."""
    
    action: Literal["answer", "call_next_agent"] = Field(
        ...,
        description="Primary action: either respond to the user or delegate to the next agent."
    )
    
    # As needed per A2A protocol
    status: Literal["input_required", "completed", "failed"] = Field(
        ...,
        description="System-defined flow status. Indicates if the task is complete, requires input, or has failed."
    )
    
    message: str = Field(
        ...,
        description="Message content, passed to caller of the agent (can be user or another agent)."
    )

    # Optional fields with proper defaults
    custom_status: Optional[str] = Field(
        default=None,
        description="Optional custom state such as 'hang_up', 'timeout', etc. for extended flow semantics."
    )

    agent_name: Optional[str] = Field(
        default=None,
        description="Name of the agent to call, required if action is 'call_next_agent'."
    )

    next_agent_instruction: Optional[str] = Field(
        None,
        description="Message content, passed to the next agent as Clear description of the task to be executed"
    )
    
    artifacts: Optional[str] = Field(
        default=None,
        description="Optional structured JSON data to be passed as artifacts; must be JSON-serializable."
    )

    @model_validator(mode="after")
    def validate_required_fields(self) -> Self:
        if self.action == "call_next_agent":
            if not self.agent_name:
                raise ValueError("`agent_name` is required when action is 'call_next_agent'")
            if not self.next_agent_instruction:
                raise ValueError("`next_agent_instruction` is required when action is 'call_next_agent'")
        return self

class ExtraUsage(BaseModel):
    reasoning_tokens: int
    cache_tokens: int

class ApiUsage(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    extra_usage: ExtraUsage | None

class Usage(BaseModel):
    usage_id: str
    context_id: str
    task_id: str
    model_name: str
    user_input: str
    output: ResponseFormat
    prompt_tokens: int
    completion_tokens: int
    extra_usage: Optional[ExtraUsage] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_outputs: Optional[List[ToolOutput]] = None
    timestamp: str = Field(default_factory=current_time_utc7_str)

class BaseAgent(ABC):
    def __init__(self, model_name: str, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery):
        self.model_name = model_name
        self.agent_card: CustomAgentCard = agent_card
        self._usage_logs: Dict[str, Usage] = {}

        # TODO: Previous implementation was doing agent discovery inside BaseAgent class -> Fix this on Task: Agent Discovery from MCP Server 
        # The cache is always dirty at startup, so that we discovery at least once
        # self._cache_dirty = True
        # self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        # self.cards: dict[str, CustomAgentCard] = {}
        # self.agent_info: str | None = None
        self.card_discovery = card_discovery

        self.model_config = {
            'arbitrary_types_allowed': True,
            'extra': 'allow',
        }

        self.agent_name: str = self.agent_card.name # The name of the agent.
        self.description: str = self.agent_card.description # A brief description of the agent's purpose.
        self.content_types: list[str] = self.agent_card.defaultInputModes # Supported content types.


    @abstractmethod
    async def invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        """Invoke the agent with a query and return a single response."""
        pass

    @abstractmethod
    async def follow_up_invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        """Follow up Invoke the agent after delegated task have been done, to decide to `call_next_agent` or `answer` based on intermediate message between agents."""
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
    def parse_structure_output(self, text: str) -> Union[ResponseFormat, str]:
        """Parse structured output from text."""
        pass

    @abstractmethod
    def root_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        """Generate the root instruction for the agent."""
        pass

    @abstractmethod
    async def make_remote_agent_connection(
        self,
        target_agent_card: AgentCard,
        request: MessageSendParams
    ) -> AsyncGenerator[dict, None]:
        """Form a connection and stream messages to a remote agent by name, yielding events as they arrive."""
        pass
    
    @abstractmethod
    def _extract_tool_calls_and_outputs(self, result) -> tuple[list[ToolCall], list[ToolOutput]]:
        """Extract tool calls and outputs from the agent's result."""
        pass
    
    @abstractmethod
    def _extract_tool_call(self, item) -> ToolCall:
        """Extract tool call from a single item."""
        pass
    
    @abstractmethod
    def _extract_tool_output(self, item) -> ToolOutput:
        """Extract tool output from a single item."""
        pass
    
    def record_usage(self, usage: Usage) -> None:
        self._usage_logs[usage.usage_id] = usage

    def get_usage_by_usage_id(self, usage_id: str) -> Optional[Usage]:
        return self._usage_logs.get(usage_id)
    
    def postprocess(self, context: Dict[str, Task]) -> str:
        lines = []
        # print(f"\n{Fore.CYAN}=== RAW CONTEXT ==={Style.RESET_ALL}")
        # print(context)
        # print(f"\n{Fore.CYAN}=========================={Style.RESET_ALL}")

        #loop through each task in the context
        for task_id, task in context.items():
            lines.append(f"=== Task {task.id} ===")
            
            # task's tool
            if hasattr(task, 'metadata') and task.metadata:
                metadata = task.metadata
                if metadata.get('tool_calls'):
                    for i, tool_call in enumerate(metadata['tool_calls']):
                        tool_name = tool_call.get('tool_name')
                        arguments = tool_call.get('arguments')
                        lines.append(f"Tool Call {i+1} - Name: {tool_name}, Arguments: {json.dumps(arguments, ensure_ascii=False)}")
                if metadata.get('tool_outputs'):
                    for i, tool_output in enumerate(metadata['tool_outputs']):
                        output = tool_output.get('output')
                        lines.append(f"Tool Result {i+1} - Output: {output}")
            
            # task's history
            if hasattr(task,'history') and task.history:
                for i, message in enumerate(task.history):
                    if hasattr(message, 'kind'):
                        role_str = message.role.value
                        if hasattr(message, 'metadata') and message.metadata:
                            agent_name = message.metadata.get('agent_name')
                            if agent_name:
                                role_str = agent_name
                        if message.parts:
                            parts = []
                            for part in message.parts:
                                if hasattr(part, 'root'):
                                    actual_part = part.root
                                    if isinstance(actual_part, TextPart):
                                        parts.append(actual_part.text)
                                    elif isinstance(actual_part, DataPart):
                                        parts.append(f"[Data: {json.dumps(actual_part.data, ensure_ascii=False)}]")
                                    elif isinstance(actual_part, FilePart):
                                        file_name = getattr(actual_part.file, 'name', 'unknown')
                                        parts.append(f"[File: {file_name}]")
                                    else:
                                        parts.append(str(actual_part))
                            if parts:
                                lines.append(f"{role_str.capitalize()}: {' '.join(parts)}")
                        else:
                            content = getattr(message, 'content', str(message))
                            lines.append(f"{role_str}: {content}")

            # task's artifacts
            if hasattr(task, 'artifacts') and task.artifacts:
                for artifact in task.artifacts:
                    if artifact.parts:
                        artifact_parts = []
                        for part in artifact.parts:
                            if hasattr(part, 'root'):
                                actual_part = part.root
                                if isinstance(actual_part, TextPart):
                                    artifact_parts.append(actual_part.text)
                                elif isinstance(actual_part, DataPart):
                                    artifact_parts.append(f"[Data: {json.dumps(actual_part.data)}]")
                                elif isinstance(actual_part, FilePart):
                                    file_name = getattr(actual_part.file, 'name', 'unknown')
                                    artifact_parts.append(f"[File: {file_name}]")
                                else:
                                    artifact_parts.append(str(actual_part))
                        if artifact_parts:
                            agent_role = "Agent"
                            if hasattr(artifact, 'metadata') and artifact.metadata:
                                agent_name = artifact.metadata.get('agent_name')
                                if agent_name:
                                    agent_role = agent_name
                            lines.append(f"{agent_role}: {' '.join(artifact_parts)}")
            
            lines.append("")
        
        result = "\n".join(lines)
        print(f"\n{Fore.CYAN}=== POSTPROCESS RESULT ==={Style.RESET_ALL}")
        print(result)
        print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
        
        return result
    
    def _create_and_store_usage(self, usage_id: str, context_id: str, task_id: str, 
                               query: str, result, api_usage, tool_calls: list[ToolCall], 
                               tool_outputs: list[ToolOutput]) -> Usage:
        usage = Usage(
            usage_id=usage_id,
            context_id=context_id,
            task_id=task_id,
            model_name=self.model_name,
            user_input=query,
            output=result.final_output,
            prompt_tokens=api_usage.input_tokens,
            completion_tokens=api_usage.output_tokens,
            extra_usage=ExtraUsage(
                reasoning_tokens=api_usage.input_tokens_details.cached_tokens, 
                cache_tokens=api_usage.output_tokens_details.reasoning_tokens
            ),
            tool_calls=tool_calls if tool_calls else None,
            tool_outputs=tool_outputs if tool_outputs else None
        )

        self.record_usage(usage)
        
        # Print usage details
        print(f"\n{Fore.MAGENTA}=== USAGE DETAILS ==={Style.RESET_ALL}")
        print(f"Usage ID: {usage.usage_id}")
        print(f"Context ID: {usage.context_id}")
        print(f"Task ID: {usage.task_id}")
        print(f"Model: {usage.model_name}")
        print(f"Prompt Tokens: {usage.prompt_tokens}")
        print(f"Completion Tokens: {usage.completion_tokens}")
        if usage.extra_usage:
            print(f"Reasoning Tokens: {usage.extra_usage.reasoning_tokens}")
            print(f"Cache Tokens: {usage.extra_usage.cache_tokens}")
        if usage.tool_calls:
            print(f"Tool Calls: {len(usage.tool_calls)}")
            for i, tool_call in enumerate(usage.tool_calls):
                print(f"  [{i+1}] {tool_call.tool_name}: {tool_call.arguments}")
        if usage.tool_outputs:
            print(f"Tool Outputs: {len(usage.tool_outputs)}")
        print(f"{Fore.MAGENTA}==================={Style.RESET_ALL}\n")