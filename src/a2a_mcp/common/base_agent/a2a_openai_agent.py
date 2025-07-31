from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat, Usage, ExtraUsage, ToolCall, ToolOutput, ApiUsage
from a2a_mcp.common.prompts import A2A_OPENAI_BASE_PROMPT, A2A_OPENAI_FOLLOW_UP_BASE_PROMPT
from agents import Agent, ModelSettings, Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
from openai import AsyncOpenAI, OpenAIError
import json
import re
import xml.etree.ElementTree as ET
import os
from typing import Any, Dict, Literal, Union, AsyncGenerator, Optional
from collections.abc import AsyncIterable
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from a2a_mcp.common.types import CustomAgentCard
from a2a.types import (
    AgentCard, 
    MessageSendParams, 
    SendMessageRequest, 
    SendStreamingMessageRequest, 
    JSONRPCErrorResponse,
    Task,
    Message
)
from a2a.client import A2AClient
from a2a_mcp.common.card_discovery import A2ACardDiscovery
import traceback
import time
from colorama import Fore, Style, init
from pydantic import ValidationError
import httpx
from uuid import uuid4
import litellm
class A2AOpenaiAgent(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[], litellm_model: Optional[str] = None):
        super().__init__(agent_card.modelName, agent_card, card_discovery, litellm_model)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.context_stores = {}

        # Initialize the base agent once
        instruction = self.root_instruction(chat_history="", agent_info="")
        
        # Check if model supports response_format (eg. aws nova-lite does not)
        supports_response_format = self._check_response_format_support()
        
        # Configure agent based on response_format support
        if supports_response_format:
            self.agent = Agent(
                name=self.agent_card.name,
                instructions=instruction,
                model=self.litellm_model,
                mcp_servers=self.mcp_server,
                output_type=ResponseFormat,
                model_settings=ModelSettings(temperature=0.0),
            )
        else:
            print(f"{Fore.YELLOW}Model {self.model_name} does not support response_format, initializing without structured output{Style.RESET_ALL}")
            self.agent = Agent(
                name=self.agent_card.name,
                instructions=instruction,
                model=self.litellm_model,
                mcp_servers=self.mcp_server,
                model_settings=ModelSettings(temperature=0.0),
            )
        
        # Ensure agent is initialized
        if not self.agent:
            raise RuntimeError("Failed to initialize OpenAI agent")

        print("=============== Using Openai ===============")

    def _check_response_format_support(self) -> bool:
        """Check if the current model supports structured response_format using json_schema."""
        try:
            from litellm.utils import supports_response_schema
            return supports_response_schema(model=self.litellm_model, custom_llm_provider="bedrock") #hardcoded to bedrock for now
        except Exception as e:
            logger.warning(f"Could not determine json_schema support for model {self.litellm_model}: {e}")
            return False  # safer default

    def _parse_to_response_format(self, data: Union[str, ResponseFormat]) -> ResponseFormat:
        if isinstance(data, ResponseFormat):
            return data

        # Helper function to try parsing JSON
        def try_parse_json(text: str) -> Optional[Dict]:
            try:
                return json.loads(text)
            except Exception:
                return None

        # If input is string, try various parsing strategies
        if isinstance(data, str):
            # Strategy 1: Direct JSON parse
            parsed = try_parse_json(data)
            if parsed:
                try:
                    return ResponseFormat(**parsed)
                except Exception:
                    pass

            # Strategy 2: Strip markdown code blocks
            if "```" in data:
                # Extract content between ```json and ``` or just between ``` and ```
                import re
                code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
                matches = re.findall(code_block_pattern, data)
                
                for match in matches:
                    parsed = try_parse_json(match.strip())
                    if parsed:
                        try:
                            return ResponseFormat(**parsed)
                        except Exception:
                            continue

            # Strategy 3: Find JSON-like structure in text
            # Look for patterns like {..."action": "answer"...} or {..."action":"answer"...}
            import re
            json_pattern = r"\{[^{]*\"action\"[\s]*:[\s]*\"(?:answer|call_next_agent)\"[^}]*\}"
            matches = re.findall(json_pattern, data)
            
            for match in matches:
                parsed = try_parse_json(match)
                if parsed:
                    try:
                        return ResponseFormat(**parsed)
                    except Exception:
                        continue

            # Strategy 4: Handle escaped JSON in artifacts
            # Sometimes the JSON might be double-escaped due to being in artifacts
            escaped_data = data.replace('\\"', '"').replace('\\\\', '\\')
            if escaped_data != data:
                parsed = try_parse_json(escaped_data)
                if parsed:
                    try:
                        return ResponseFormat(**parsed)
                    except Exception:
                        pass

        # Fallback: Return default response format with original text as message
        logger.warning(f"All parsing strategies failed, falling back to default ResponseFormat")
        return ResponseFormat(
            action="answer",
            status="completed",  # Hacky fix; might cause failures
            message=str(data),
            agent_names=None,
            next_agent_instructions=None,
            artifacts=None
        )

        

    def update_agent_instructions(self, history: str, agent_info: str, is_follow_up: bool = False) -> str:
        """Update agent instructions while keeping the same agent instance"""
        if not self.agent:
            raise RuntimeError("Agent not initialized")
            
        instruction = (
            self.root_follow_up_instruction(chat_history=history, agent_info=agent_info)
            if is_follow_up
            else self.root_instruction(chat_history=history, agent_info=agent_info)
        )
        if is_follow_up:
            print(f"{Fore.BLUE}{instruction}{Style.RESET_ALL}")
        self.agent.instructions = instruction
        return instruction

    async def make_remote_agent_connection(
        self,
        target_agent_card: AgentCard, 
        request: MessageSendParams
    ) -> AsyncGenerator[dict, None]:
        """Form a connection and stream messages to a remote agent, yielding events as they arrive."""
        
        async def _stream_connection():
            async with httpx.AsyncClient(timeout=60) as httpx_client:
                agent_client = A2AClient(httpx_client, target_agent_card)
                
                # Check if agent supports streaming
                supports_streaming = (
                    hasattr(target_agent_card, "capabilities") and 
                    target_agent_card.capabilities and 
                    getattr(target_agent_card.capabilities, "streaming", False)
                )
                
                if supports_streaming:
                    # Stream from streaming agent
                    async for response in agent_client.send_message_streaming(
                        SendStreamingMessageRequest(id=str(uuid4()), params=request)
                    ):
                        if isinstance(response.root, JSONRPCErrorResponse):
                            yield {"kind": "error", "error": str(response.root)}
                            return
                        
                        if hasattr(response.root, 'result') and response.root.result:
                            event = response.root.result
                            # Convert to dict for consistency
                            if hasattr(event, '__dict__'):
                                yield event.__dict__
                            else:
                                # Fallback – treat as generic message event
                                yield {"kind": "message", "content": str(event)}
                        else:
                            yield {"kind": "error", "error": "Empty response"}
                            return
                else:
                    # Handle non-streaming agent
                    response = await agent_client.send_message(
                        SendMessageRequest(id=str(uuid4()), params=request)
                    )
                    
                    if isinstance(response.root, JSONRPCErrorResponse):
                        yield {"kind": "error", "error": str(response.root)}
                    else:
                        result = response.root.result
                        if hasattr(result, '__dict__'):
                            yield result.__dict__
                        else:
                            yield {"kind": "message", "content": str(result)}
        
        return _stream_connection()

    async def invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        if not self.agent:
            raise RuntimeError("Agent not initialized")
            
        usage_id = str(uuid4())
        result = None
        try:
            history = self.postprocess(context)
            
            #Generate agent result
            agent_info = self.card_discovery.get_remote_agent_info()
            instruction = self.update_agent_instructions(history, agent_info, is_follow_up=False)
            print(Fore.GREEN + Style.BRIGHT + "Updated agent instructions" + Style.RESET_ALL)
            print(Fore.BLUE + Style.BRIGHT + instruction + Style.RESET_ALL)
            start_time = time.time()
            result = await Runner.run(self.agent, query)
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print(result.raw_responses[0].usage)
            print(result.final_output)
            api_usage = result.raw_responses[0].usage
            #Get tool calls and outputs and save to context store
            tool_calls, tool_outputs = self._extract_tool_calls_and_outputs(result)
            
            # Save tool calls and outputs to current task in context
            if tool_calls or tool_outputs:
                if task_id in context:
                    current_task = context[task_id]
                    if not hasattr(current_task, 'metadata') or current_task.metadata is None:
                        current_task.metadata = {}
                    
                    if tool_calls:
                        current_task.metadata['tool_calls'] = [
                            {"tool_name": tc.tool_name, "arguments": tc.arguments} 
                            for tc in tool_calls
                        ]
                    if tool_outputs:
                        current_task.metadata['tool_outputs'] = [
                            {"output": to.output} 
                            for to in tool_outputs
                        ]
            self._create_and_store_usage(
                    usage_id=usage_id,
                    context_id=context_id,
                    task_id=task_id,
                    query=query,
                    result=self._parse_to_response_format(result.final_output),
                    api_usage=ApiUsage(
                        prompt_tokens=api_usage.input_tokens,
                        completion_tokens=api_usage.output_tokens,
                        extra_usage=ExtraUsage(
                            reasoning_tokens=api_usage.input_tokens_details.cached_tokens, 
                            cache_tokens=api_usage.output_tokens_details.reasoning_tokens
                        ),
                    ),
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs            
                )
            # Convert result to ResponseFormat
            try:
                # If model supports structured output, ResponseFormat is already enforced
                if self._check_response_format_support():
                    return result.final_output
                else:
                    # For models without structured output support, parse the text response
                    return self._parse_to_response_format(result.final_output)

            except ValidationError as ve:
                print("Validation error while formatting response:", ve)
                return ResponseFormat(
                    action="answer",
                    status="failed", 
                    message="The response format was invalid.",
                    agent_names=None,
                    next_agent_instructions=None,
                    artifacts=None
                )

        except OpenAIError as e:
            traceback.print_exc()
            print(e)
            return ResponseFormat(
                action="answer",
                status="input_required",
                message="We are unable to process your request at the moment. Please try again.",
                agent_names=None,
                next_agent_instructions=None,
                artifacts=None
            )

    async def follow_up_invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        if not self.agent:
            raise RuntimeError("Agent not initialized")
            
        usage_id = str(uuid4())
        result = None
        try:
            history = self.postprocess(context)
            
            #Generate agent result
            agent_info = self.card_discovery.get_remote_agent_info()
            instruction = self.update_agent_instructions(history, agent_info, is_follow_up=True)
            print(Fore.GREEN + Style.BRIGHT + "Updated agent instructions" + Style.RESET_ALL)
            start_time = time.time()
            result = await Runner.run(self.agent, query, max_turns=20)
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print(result.raw_responses[0].usage)
            print(result.final_output)
            api_usage = result.raw_responses[0].usage
            tool_calls, tool_outputs = self._extract_tool_calls_and_outputs(result)
            
            # Save tool calls and outputs to current task in context
            if tool_calls or tool_outputs:
                if task_id in context:
                    current_task = context[task_id]
                    if not hasattr(current_task, 'metadata') or current_task.metadata is None:
                        current_task.metadata = {}
                    
                    if tool_calls:
                        current_task.metadata['tool_calls'] = [
                            {"tool_name": tc.tool_name, "arguments": tc.arguments} 
                            for tc in tool_calls
                        ]
                    if tool_outputs:
                        current_task.metadata['tool_outputs'] = [
                            {"output": to.output} 
                            for to in tool_outputs
                        ]
            
            # สร้างและเก็บ Usage
            self._create_and_store_usage(
                    usage_id=usage_id,
                    context_id=context_id,
                    task_id=task_id,
                    query=query,
                    result=self._parse_to_response_format(result.final_output),
                    api_usage=ApiUsage(
                        prompt_tokens=api_usage.input_tokens,
                        completion_tokens=api_usage.output_tokens,
                        extra_usage=ExtraUsage(
                            reasoning_tokens=api_usage.input_tokens_details.cached_tokens, 
                            cache_tokens=api_usage.output_tokens_details.reasoning_tokens
                        ),
                    ),
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs            
                )
            # Convert result to ResponseFormat
            try:
                # If model supports structured output, ResponseFormat is already enforced
                if self._check_response_format_support():
                    return result.final_output
                else:
                    # For models without structured output support, parse the text response
                    return self._parse_to_response_format(result.final_output)

            except ValidationError as ve:
                print("Validation error while formatting response:", ve)
                return ResponseFormat(
                    action="answer",
                    status="failed", 
                    message="The response format was invalid.",
                    agent_names=None,
                    next_agent_instructions=None,
                    artifacts=None
                )

        except OpenAIError as e:
            traceback.print_exc()
            print(e)
            return ResponseFormat(
                action="answer",
                status="input_required",
                message="We are unable to process your request at the moment. Please try again.",
                agent_names=None,
                next_agent_instructions=None,
                artifacts=None
            )


    
    def _extract_message_content(self, chunk):
        """Helper method to extract relevant message content from a chunk"""
        # Skip JSON structural tokens
        skip_tokens = ['{', '}', ':', ',', '"status"', '"message"', '"input_required"', 
                    '"completed"', '"error"', '"hang_up"', '":"']
        
        for token in skip_tokens:
            if chunk == token or chunk.startswith(token) or chunk.endswith(token):
                return ""
        
        # Remove escaping of quotes that might be in the actual message content
        return chunk.replace('\\"', '"').replace('"', "")


    def convert_tool_format(self, tools) -> Any:
        pass
    
    def root_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        prompt = self.agent_card.systemPrompt or "You are a helpful assistant."
        # Escape curly braces in dynamic content to prevent format errors
        safe_chat_history = chat_history.replace('{', '{{').replace('}', '}}') if chat_history else ""
        safe_agent_info = agent_info.replace('{', '{{').replace('}', '}}') if agent_info else ""
        
        return A2A_OPENAI_BASE_PROMPT.format(
            agent_name=self.agent_card.name, 
            system_prompt=prompt, 
            chat_history=safe_chat_history, 
            agent_info=safe_agent_info
        )

    def root_follow_up_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        prompt = self.agent_card.systemPrompt or "You are a helpful assistant."
        # Escape curly braces in dynamic content to prevent format errors
        safe_chat_history = chat_history.replace('{', '{{').replace('}', '}}') if chat_history else ""
        safe_agent_info = agent_info.replace('{', '{{').replace('}', '}}') if agent_info else ""
        
        return A2A_OPENAI_FOLLOW_UP_BASE_PROMPT.format(
            agent_name=self.agent_card.name, 
            system_prompt=prompt, 
            chat_history=safe_chat_history, 
            agent_info=safe_agent_info
        )

    def _extract_tool_calls_and_outputs(self, result) -> tuple[list[ToolCall], list[ToolOutput]]:
        tool_calls = []
        tool_outputs = []
        
        # Debug: แสดง RunItems ที่เกิดขึ้น
        print(f"\n{Fore.YELLOW}=== DEBUG: RunItems Analysis ==={Style.RESET_ALL}")
        if hasattr(result, 'new_items') and result.new_items:
            print(f"Total new_items: {len(result.new_items)}")
            for i, item in enumerate(result.new_items):
                print(f"[{i}] Item type: {item.type}")
                if hasattr(item, 'raw_item'):
                    print(f"    Raw item type: {type(item.raw_item)}")
                    if hasattr(item.raw_item, '__dict__'):
                        print(f"    Raw item attributes: {list(item.raw_item.__dict__.keys())}")
                    elif isinstance(item.raw_item, dict):
                        print(f"    Raw item keys: {list(item.raw_item.keys())}")
        else:
            print("No new_items found or new_items is empty")
        print(f"{Fore.YELLOW}================================{Style.RESET_ALL}\n")
        
        # วนลูปผ่าน new_items เพื่อเก็บข้อมูล tool calls และ outputs
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                print(f"Processing item type: {item.type}")
                
                if item.type == "tool_call_item":
                    tool_call = self._extract_tool_call(item)
                    if tool_call:
                        tool_calls.append(tool_call)
                
                elif item.type == "tool_call_output_item":
                    tool_output = self._extract_tool_output(item)
                    if tool_output:
                        tool_outputs.append(tool_output)
        
        print(f"\n{Fore.GREEN}Collected {len(tool_calls)} tool calls and {len(tool_outputs)} tool outputs{Style.RESET_ALL}")
        return tool_calls, tool_outputs

    def _extract_tool_call(self, item) -> ToolCall:
        print("  -> Found tool_call_item")
        tool_name = 'unknown'
        arguments = {}
        
        # สำหรับ ResponseFunctionToolCall
        if hasattr(item.raw_item, 'function'):
            if hasattr(item.raw_item.function, 'name'):
                tool_name = item.raw_item.function.name
            if hasattr(item.raw_item.function, 'arguments'):
                try:
                    arguments = json.loads(item.raw_item.function.arguments) if isinstance(item.raw_item.function.arguments, str) else item.raw_item.function.arguments or {}
                except (json.JSONDecodeError, TypeError):
                    arguments = {"raw_arguments": str(item.raw_item.function.arguments)}
        
        # สำหรับ tool calls อื่นๆ ที่อาจมี name และ arguments โดยตรง
        elif hasattr(item.raw_item, 'name'):
            tool_name = item.raw_item.name
            if hasattr(item.raw_item, 'arguments'):
                try:
                    arguments = json.loads(item.raw_item.arguments) if isinstance(item.raw_item.arguments, str) else item.raw_item.arguments or {}
                except (json.JSONDecodeError, TypeError):
                    arguments = {"raw_arguments": str(item.raw_item.arguments)}
        
        print(f"     Tool name: {tool_name}")
        print(f"     Arguments: {arguments}")
        
        return ToolCall(tool_name=tool_name, arguments=arguments)

    def _extract_tool_output(self, item) -> ToolOutput:
        print("  -> Found tool_call_output_item")
        output_str = ""
        
        # ตาม RunItem structure, ToolCallOutputItem มี output attribute
        if hasattr(item, 'output') and item.output:
            output_str = str(item.output)
        # และมี raw_item ที่เป็น dict มี output key
        elif hasattr(item.raw_item, 'output'):
            raw_output = item.raw_item['output'] if isinstance(item.raw_item, dict) else item.raw_item.output
            output_str = str(raw_output)
        
        print(f"     Output: {output_str[:100]}...")
        return ToolOutput(output=output_str)