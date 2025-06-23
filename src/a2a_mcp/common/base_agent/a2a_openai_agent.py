from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat, Usage, ExtraUsage, ToolCall, ToolOutput
from a2a_mcp.common.prompts import A2A_OPENAI_BASE_PROMPT
from agents import Agent, ModelSettings, Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
from openai import AsyncOpenAI, OpenAIError
import json
import re
import xml.etree.ElementTree as ET
import os
from typing import Any, Dict, Literal, Union, AsyncGenerator
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
class A2AOpenaiAgent(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        super().__init__(agent_card.modelName, agent_card, card_discovery)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.agent = None
        self.context_stores = {}

        # TODO: Still need memory manager here?
        print("=============== Using Openai ===============")

    def get_agent(self, history, agent_info):
        instruction = self.root_instruction(chat_history=history, agent_info=agent_info)
        # print(instruction)
        return instruction, Agent(
            name=self.agent_card.name,
            instructions=instruction,
            model=self.model_name,
            mcp_servers=self.mcp_server,
            output_type=ResponseFormat,
            model_settings=ModelSettings(temperature=0.0),
            
        )
    
    async def make_remote_agent_connection(
        self,
        target_agent_card: AgentCard, 
        request: MessageSendParams
    ) -> AsyncGenerator[dict, None]:
        """Form a connection and stream messages to a remote agent, yielding events as they arrive."""
        
        async def _stream_connection():
            async with httpx.AsyncClient(timeout=30) as httpx_client:
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
                            yield {"type": "error", "error": str(response.root)}
                            return
                        
                        if hasattr(response.root, 'result') and response.root.result:
                            event = response.root.result
                            # Convert to dict for consistency
                            if hasattr(event, '__dict__'):
                                yield event.__dict__
                            else:
                                yield {"data": str(event)}
                        else:
                            yield {"type": "error", "error": "Empty response"}
                            return
                else:
                    # Handle non-streaming agent
                    response = await agent_client.send_message(
                        SendMessageRequest(id=str(uuid4()), params=request)
                    )
                    
                    if isinstance(response.root, JSONRPCErrorResponse):
                        yield {"type": "error", "error": str(response.root)}
                    else:
                        result = response.root.result
                        if hasattr(result, '__dict__'):
                            yield result.__dict__
                        else:
                            yield {"data": str(result)}
        
        return _stream_connection()

    async def invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        # TODO: maybe we should go through together on invoke(), if we are going to change response format etc (im not too clear on this)
        usage_id = str(uuid4())
        result = None
        try:
            history = self.postprocess(context)
            
            #Generate agent result
            agent_info = self.card_discovery.get_remote_agent_info()
            instruction, self.agent = self.get_agent(history, agent_info)
            print(Fore.GREEN + Style.BRIGHT + "Init agent complete" + Style.RESET_ALL)
            start_time = time.time()
            result = await Runner.run(self.agent, query)
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
                    result=result,
                    api_usage=api_usage,
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs            
                )
            # Convert result to ResponseFormat
            try:
                return result.final_output
            except ValidationError as ve:
                print("Validation error while formatting response:", ve)
                return ResponseFormat(
                    action="answer",
                    status="failed",
                    custom_status="",
                    message="The response format was invalid.",
                    agent_name=None,
                    next_agent_instruction=None,
                    artifacts=None
                )

        except OpenAIError as e:
            traceback.print_exc()
            print(e)
            return ResponseFormat(
                action="answer",
                status="input_required",
                custom_status="",
                message="We are unable to process your request at the moment. Please try again.",
                agent_name=None,
                next_agent_instruction=None,
                artifacts=None
            )

    async def stream(self, query: str, context_id: str, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:

        history = "" # TODO: Load Memory
        agent_info = self.card_discovery.get_remote_agent_info()
        self.agent = self.get_agent(history, agent_info)

        result = Runner.run_streamed(self.agent, input=query)
        raw_json_chunks = ""
        message_content = ""
        
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                chunk = event.data.delta
                raw_json_chunks += chunk
                
                # Found first json object --is-> Generate complete
                # Sometimes there is a chance that it generate duplicate answer {"status": ..., "message": ...}{"status": ..., "message": ...}
                first_json = self.parse_structure_output(raw_json_chunks)
                if isinstance(first_json, str) and first_json != "":
                    print(f"\nExtracted {raw_json_chunks} -> {first_json}\n")
                    raw_json_chunks = first_json
                    break

                # Try to extract structured content as we go
                try:
                    # As we receive chunks, try to parse what we've received so far

                    # If we found that agent decide to forward task to another agent, we will wait for complete response.
                    if 'call_next_agent' in raw_json_chunks:
                        continue

                    # This is a simple approach - we're looking for "message":"content" patterns
                    if '"message":"' in raw_json_chunks or '"message":' in raw_json_chunks:
                        # If we find a new piece of the message field
                        new_content = self._extract_message_content(chunk)
                        if new_content:
                            message_content += new_content
                            yield {
                                "is_task_complete": False,
                                "require_user_input": False,
                                "content": new_content,
                                "hang_up": False,
                                "call_next_agent": False,
                                "agent_name": ""
                            }
                except:
                    # If parsing fails, continue collecting chunks
                    pass
            elif event.type == "agent_updated_stream_event":
                print(f"Agent updated: {event.new_agent.name}")
                continue
            # When items are generated, print them
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    print("-- Tool was called")
                    response_function_tool_call = event.item.raw_item
                    # Safely access attributes that might not exist on all tool call types (returns none if attribute doesnt exist )
                    arguments = getattr(response_function_tool_call, 'arguments', None)
                    call_id = getattr(response_function_tool_call, 'call_id', None)
                    tool_name = getattr(response_function_tool_call, 'name', None)
                    tool_status = getattr(response_function_tool_call, 'status', None)

                    print(arguments, call_id, tool_name, tool_status)
                elif event.item.type == "tool_call_output_item":
                    print(f"-- Tool output: {event.item.output}")
                    raw_item = event.item.raw_item
                    call_id = raw_item.get('call_id') if isinstance(raw_item, dict) else None # improves type safety
                    if isinstance(raw_item, dict) and 'output' in raw_item:
                        try:
                            output_value = raw_item['output']
                            # Ensure we have a string for json.loads
                            if isinstance(output_value, str):
                                output = json.loads(output_value)['text']
                            else:
                                output = str(output_value)
                        except (json.JSONDecodeError, KeyError):
                            output = str(raw_item['output'])

                elif event.item.type == "message_output_item":
                    print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
                else:
                    pass  # Ignore other event types
        
        # At the end, parse the complete response to get the final status
        try:
            # First try to get a valid JSON string from parse_structure_output
            structured_output = self.parse_structure_output(raw_json_chunks)
            if isinstance(structured_output, str) and structured_output: #type safety check
                parsed_response = json.loads(structured_output)
            else:
                # Fallback to parsing raw_json_chunks directly
                parsed_response = json.loads(raw_json_chunks)
                
            print("parsed_response => ", parsed_response)
            action = parsed_response.get("action", "answer")
            status = parsed_response.get("status", "input_required")
            agent_name = parsed_response.get("agent_name", "")
            
            # TODO: Shold we save conversation history here ? 

            # Determine if we need user input or should hang up based on status
            require_input = status == "input_required"
            hang_up = status == "hang_up"

            if action == "call_next_agent":
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": parsed_response['message'],
                    "hang_up": False,
                    "call_next_agent": True,
                    "agent_name": agent_name
                }
            else:                yield {
                    "is_task_complete": True,
                    "require_user_input": require_input,
                    "content": parsed_response['message'],
                    "hang_up": hang_up,
                    "call_next_agent": False,
                    "agent_name": ""
                }
        except json.JSONDecodeError:
            print("json.JSONDecodeError: ", raw_json_chunks)
            print("\n", message_content)
            # If we can't parse the final JSON, return what we have
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": message_content,
                "hang_up": False,
                "call_next_agent": False,
                "agent_name": ""
            }

    #TODO: refactor performance of this function and standard pylance , it is a bit messy
    def postprocess(self, context: Dict[str, Task]) -> str:
        lines = []
        # print(f"\n{Fore.CYAN}=== RAW CONTEXT ==={Style.RESET_ALL}")
        # print(context)
        # print(f"\n{Fore.CYAN}=========================={Style.RESET_ALL}")

        for task_id, task in context.items():
            lines.append(f"=== Task {task.id} ===")
            if task.history:
                for i, message in enumerate(task.history):
                    if hasattr(message, 'kind') and message.kind == 'message':
                        role = getattr(message, 'role', 'unknown')
                        role_str = role.value if hasattr(role, 'value') else str(role)
                        
                        if hasattr(message, 'parts') and message.parts:
                            parts = []
                            for part in message.parts:
                                # Part is a RootModel, access the actual content via .root
                                if hasattr(part, 'root'):
                                    actual_part = part.root
                                    if hasattr(actual_part, 'text'):
                                        parts.append(actual_part.text)
                                    elif hasattr(actual_part, 'data'):
                                        parts.append(f"[Data: {json.dumps(actual_part.data)}]")
                                    elif hasattr(actual_part, 'file'):
                                        file_name = getattr(actual_part.file, 'name', 'unknown')
                                        parts.append(f"[File: {file_name}]")
                                    else:
                                        parts.append(str(actual_part))
                                else:
                                    # Fallback if part doesn't have root
                                    if hasattr(part, 'text'):
                                        parts.append(part.text)
                                    else:
                                        parts.append(str(part))
                            
                            if parts:
                                lines.append(f"{role_str}: {' '.join(parts)}")
                        else:
                            content = getattr(message, 'content', str(message))
                            lines.append(f"{role_str}: {content}")
                
                if hasattr(task, 'artifacts') and task.artifacts:
                    print(f"  DEBUG: Found {len(task.artifacts)} artifacts")
                    for artifact in task.artifacts:
                        if hasattr(artifact, 'parts') and artifact.parts:
                            agent_parts = []
                            for part in artifact.parts:
                                if hasattr(part, 'root'):
                                    actual_part = part.root
                                    if hasattr(actual_part, 'text'):
                                        agent_parts.append(actual_part.text)
                                    else:
                                        agent_parts.append(str(actual_part))
                                else:
                                    if hasattr(part, 'text'):
                                        agent_parts.append(part.text)
                                    else:
                                        agent_parts.append(str(part))
                            
                            if agent_parts:
                                lines.append(f"agent: {' '.join(agent_parts)}")
            
            metadata = task.metadata
            tool_calls = metadata.get('tool_calls', []) if metadata else []
            tool_outputs = metadata.get('tool_outputs', []) if metadata else []

            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('tool_name', 'unknown')
                        arguments = tool_call.get('arguments', {})
                    else:
                        tool_name = tool_call.tool_name
                        arguments = tool_call.arguments
                    lines.append(f"Tool Call {i+1} - Name: {tool_name}, Arguments: {json.dumps(arguments, ensure_ascii=False)}")

            if tool_outputs:
                for i, tool_output in enumerate(tool_outputs):
                    if isinstance(tool_output, dict):
                        output = tool_output.get('output', '')
                    else:
                        output = tool_output.output
                    lines.append(f"Tool Result {i+1} - Output: {output}")
            
            lines.append("")
        
        result = "\n".join(lines)
        print(f"\n{Fore.CYAN}=== POSTPROCESS RESULT ==={Style.RESET_ALL}")
        print(result)
        print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
        
        return result
    
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

    def parse_structure_output(self, text: str) -> Union[ResponseFormat, str]: # im not too sure about what is going on here to be honest, this should allow both return types
        """
        Input:
            '{"model":"Mazda CX-5","brand":"Mazda"}{"model":"Mazda CX-5","brand":"Mazda"}' -> '{"model":"Mazda CX-5","brand":"Mazda"}'
            '{"model":"Mazda CX-5","brand":' -> ""
            '{"model":"Mazda CX-5","brand":"Mazda"}MMM' -> '{"model":"Mazda CX-5","brand":"Mazda"}'
        """
        open_brace_count = 0
        start_index = -1

        for i, char in enumerate(text):
            if char == '{':
                if open_brace_count == 0:
                    start_index = i
                open_brace_count += 1
            elif char == '}':
                open_brace_count -= 1
                if open_brace_count == 0 and start_index != -1:
                    return text[start_index:i+1]
        return ""

    def convert_tool_format(self, tools) -> Any:
        pass

    def parse_agent_response(self, response: ResponseFormat):
        if response and isinstance(response, ResponseFormat): 
            # print("[Presale]: ", response.status)
            if response.action == 'answer':
                if response.status == "input_required":
                    return {
                        "is_task_complete": False,
                        "require_user_input": True,
                        "content": response.message,
                        "hang_up": response.custom_status == "hang_up",
                        "call_next_agent": False,
                        "agent_name": "",
                        "next_agent_instruction": "",
                        "artifacts": {}
                    }
                elif response.status == "failed":
                    return {
                        "is_task_complete": False,
                        "require_user_input": True,
                        "content": response.message,
                        "hang_up": response.custom_status == "hang_up",
                        "call_next_agent": False,
                        "agent_name": "",
                        "next_agent_instruction": "",
                        "artifacts": {}
                    }
                elif response.status == "completed":
                    return {
                        "is_task_complete": True,
                        "require_user_input": False,
                        "content": response.message,
                        "hang_up": response.custom_status == "hang_up",
                        "call_next_agent": False,
                        "agent_name": "",
                        "next_agent_instruction": "",
                        "artifacts": {}
                    }
            elif response.action == 'call_next_agent':
                return {
                    "is_task_complete": response.status == "completed",
                    "require_user_input": response.status == "input_required",
                    "content": response.message,
                    "hang_up": False,
                    "call_next_agent": True,
                    "agent_name": response.agent_name,
                    "next_agent_instruction": response.next_agent_instruction,
                    "artifacts": response.artifacts
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
            "hang_up": False,
            "call_next_agent": False,
            "agent_name": "",
            "next_agent_instruction": "",
            "artifacts": {}
        }
    
    def root_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        prompt = self.agent_card.systemPrompt or "You are a helpful assistant."
        return A2A_OPENAI_BASE_PROMPT.format(system_prompt=prompt, chat_history=chat_history, agent_info=agent_info)

    def _extract_tool_calls_and_outputs(self, result) -> tuple[list[ToolCall], list[ToolOutput]]:
        """แยกข้อมูล tool calls และ tool outputs จาก result"""
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
        """แยกข้อมูล tool call จาก ToolCallItem"""
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
        """แยกข้อมูล tool output จาก ToolCallOutputItem"""
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

    def _create_and_store_usage(self, usage_id: str, context_id: str, task_id: str, 
                               query: str, result, api_usage, tool_calls: list[ToolCall], 
                               tool_outputs: list[ToolOutput]) -> Usage:
        """สร้างและเก็บ Usage object"""
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
            tool_outputs=tool_outputs if tool_outputs else None        )
        
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