from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat, Usage, ExtraUsage, ToolCall, ToolOutput, ApiUsage
from a2a_mcp.common.prompts import A2A_OPENAI_NATIVE_BASE_PROMPT, A2A_OPENAI_NATIVE_FOLLOW_UP_BASE_PROMPT
from agents import Agent, ModelSettings, Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent, ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputItemAddedEvent, ResponseFunctionCallArgumentsDeltaEvent
from openai import AsyncOpenAI, OpenAIError
import json
import re
import xml.etree.ElementTree as ET
import os
from typing import Any, Dict, AsyncIterable, Literal
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from a2a.client import A2AClient
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
from a2a_mcp.common.card_discovery import A2ACardDiscovery
import traceback
import time
from colorama import Fore, Style, init
from openai import OpenAI, AsyncOpenAI
from uuid import uuid4
from typing import AsyncGenerator, List, Dict, Any
import traceback
import httpx

class A2AOpenaiAgentNative(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        super().__init__(agent_card.modelName, agent_card, card_discovery)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.agent = None
        
        # TODO: Still need memory manager here?
        print("=============== Using Openai ===============")

    def get_agent(self, history, agent_info):
        instruction = self.root_instruction(chat_history=history, agent_info=agent_info)
        print(instruction)

        client = AsyncOpenAI()
        assistant = client.beta.assistants.create(
            instructions=instruction,
            model=self.model_name,
            tools=[],
            temperature=0
        )
        return instruction, client, assistant

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
        try:
            usage_id = str(uuid4())
            history = self.postprocess(context)
            agent_info = self.card_discovery.get_remote_agent_info()
            instruction = self.root_instruction(chat_history=history, agent_info=agent_info)
            print(Fore.BLUE + Style.BRIGHT + instruction + Style.RESET_ALL)

            session = self.mcp_server[0]
            tools_result = await session.list_tools()
            tools_list = [{"name": tool.name, "description": tool.description,
                            "inputSchema": tool.inputSchema} for tool in tools_result]
            start_time = time.time()
            client = AsyncOpenAI()
            
            tools = self.convert_tool_format(tools_result)
            api_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0
            }

            tool_calls: List[ToolCall] = []
            tool_outputs: List[ToolCall] = []
            input_messages = [{"role": "user", "content": query}]
            is_continue = True # True while agent calling tools, False after agent try to answer
            while is_continue:
                print("\n\n")
                response = await client.responses.create(
                    instructions=instruction,
                    model=self.model_name,
                    input=input_messages,
                    tools=tools,
                    tool_choice='auto',
                    temperature=0
                )
                print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))
                api_usage["prompt_tokens"] += response.usage.input_tokens
                api_usage["completion_tokens"] += response.usage.output_tokens
                api_usage["cached_tokens"] += response.usage.input_tokens_details.cached_tokens
                api_usage["reasoning_tokens"] += response.usage.output_tokens_details.reasoning_tokens


                output_message = response.output
                for tool_call in output_message:
                    if isinstance(tool_call, ResponseFunctionToolCall):
                        args = json.loads(tool_call.arguments)
                        name = tool_call.name
                        print(f"Calling tool {name} with {args}")
                        tool_response = await session.call_tool(name, args)

                        input_messages.append(tool_call)  # append model's function call message
                        input_messages.append({                               # append result message
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": str(tool_response)
                        })

                        # --- Custom Tool logs --- #
                        tool_calls.append(ToolCall(tool_name=name, arguments=args))
                        tool_outputs.append(ToolOutput(output=str(tool_response.content[0].text)))

                    else:
                        is_continue = False
                        break
                
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print("\n\n")
            response_object = self.parse_structure_output(output_message[0].content[0].text)
            print(output_message[0].content[0].text)

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
            
            # Create and store Usage
            self._create_and_store_usage(
                    usage_id=usage_id,
                    context_id=context_id,
                    task_id=task_id,
                    query=query,
                    result=response_object,
                    api_usage=ApiUsage(
                        prompt_tokens=api_usage['prompt_tokens'],
                        completion_tokens=api_usage['completion_tokens'],
                        extra_usage=None
                    ),
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs            
                )
            
            return response_object

        except OpenAIError as e:
            traceback.print_exc()
            print(e)
            return ResponseFormat(
                action="answer",
                status="input_required",
                custom_status="",
                message="We are unable to process your request at the moment. Please try again. {e}",
                agent_name=None,
                next_agent_instruction=None,
                artifacts=None
            )

    async def follow_up_invoke(self, query: str, context_id: str, task_id: str, context: Dict[str, Task]) -> ResponseFormat:
        try:
            usage_id = str(uuid4())
            history = self.postprocess(context)
            agent_info = self.card_discovery.get_remote_agent_info()
            instruction = self.root_follow_up_instruction(chat_history=history, agent_info=agent_info)
            print(Fore.BLUE + instruction + Style.RESET_ALL)

            session = self.mcp_server[0]
            tools_result = await session.list_tools()
            tools_list = [{"name": tool.name, "description": tool.description,
                            "inputSchema": tool.inputSchema} for tool in tools_result]
            start_time = time.time()
            client = AsyncOpenAI()
            
            tools = self.convert_tool_format(tools_result)
            api_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0
            }

            tool_calls: List[ToolCall] = []
            tool_outputs: List[ToolCall] = []
            input_messages = [{"role": "user", "content": query}]
            is_continue = True # True while agent calling tools, False after agent try to answer
            while is_continue:
                print("\n\n")
                response = await client.responses.create(
                    instructions=instruction,
                    model=self.model_name,
                    input=input_messages,
                    tools=tools,
                    tool_choice='auto',
                    temperature=0
                )
                print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))
                api_usage["prompt_tokens"] += response.usage.input_tokens
                api_usage["completion_tokens"] += response.usage.output_tokens
                api_usage["cached_tokens"] += response.usage.input_tokens_details.cached_tokens
                api_usage["reasoning_tokens"] += response.usage.output_tokens_details.reasoning_tokens


                output_message = response.output
                for tool_call in output_message:
                    if isinstance(tool_call, ResponseFunctionToolCall):
                        args = json.loads(tool_call.arguments)
                        name = tool_call.name
                        print(f"Calling tool {name} with {args}")
                        tool_response = await session.call_tool(name, args)

                        input_messages.append(tool_call)  # append model's function call message
                        input_messages.append({                               # append result message
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": str(tool_response)
                        })

                        # --- Custom Tool logs --- #
                        tool_calls.append(ToolCall(tool_name=name, arguments=args))
                        tool_outputs.append(ToolOutput(output=str(tool_response.content[0].text)))

                    else:
                        is_continue = False
                        break
                
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print("\n\n")
            response_object = self.parse_structure_output(output_message[0].content[0].text)
            print(output_message[0].content[0].text)

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
            
            # Create and store Usage
            self._create_and_store_usage(
                    usage_id=usage_id,
                    context_id=context_id,
                    task_id=task_id,
                    query=query,
                    result=response_object,
                    api_usage=ApiUsage(
                        prompt_tokens=api_usage['prompt_tokens'],
                        completion_tokens=api_usage['completion_tokens'],
                        extra_usage=None
                    ),
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs            
                )
            
            return response_object

        except OpenAIError as e:
            traceback.print_exc()
            print(e)
            return ResponseFormat(
                action="answer",
                status="input_required",
                custom_status="",
                message="We are unable to process your request at the moment. Please try again. {e}",
                agent_name=None,
                next_agent_instruction=None,
                artifacts=None
            )

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:

        history = "" # TODO: Load Memory
        agent_info = self.card_discovery.get_remote_agent_info() # TODO: Add agent discovery information
        inst = self.root_instruction(chat_history=history, agent_info=agent_info)
        session = self.mcp_server[0]
        tools_result = await session.list_tools()
        tools_list = [{"name": tool.name, "description": tool.description,
            "inputSchema": tool.inputSchema} for tool in tools_result]

        client = AsyncOpenAI()

        tools = self.convert_tool_format(tools_result)
        print(json.dumps(tools, indent=4, ensure_ascii=False))

        input_messages = [{"role": "user", "content": query}]
        is_continue = True # True while agent calling tools, False after agent try to answer
        while is_continue:
            print("\n\n")
            print("="*20, "START LOOP", "="*20)
            stream = await client.responses.create(
                instructions=inst,
                model=self.model_name,
                input=input_messages,
                tools=tools,
                tool_choice='auto',
                temperature=0,
                stream=True
            )

            # buffer for steaming
            in_message = False
            buffer = "" # This is temporary string buffer to collect chunk and be clear after yield response
            end_tag = "</" # "</message>"
            has_response = False # Flag to check if calling tool but also have quick message back to user, if true -> break conversation 
            all_chunk_string = "" # This is the string that collect all chunk, will be converted in to ResponseFormat object later
            text = ''

            final_tool_calls = {}
            async for event in stream:
                if event.type == 'response.output_item.added' and isinstance(event.item, ResponseFunctionToolCall):
                    final_tool_calls[event.output_index] = event.item
                elif event.type == 'response.function_call_arguments.delta' and isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
                    index = event.output_index

                    if final_tool_calls[index]:
                        final_tool_calls[index].arguments += event.delta
                elif event.type == 'response.output_text.delta':
                        delta = event.delta
                        text += delta
                        all_chunk_string += delta
                        buffer += delta
                        print(buffer)
                        # Add logic to yield only message part
                        while buffer and 'call_next_agent' not in all_chunk_string:
                            if not in_message:
                                # Search for <message> tag
                                start_idx = buffer.find("<message>")
                                if start_idx != -1:
                                    in_message = True
                                    has_response = True
                                    buffer = buffer[start_idx + len("<message>"):]
                                    continue  # Start yielding next token
                                else:
                                    # Not yet inside message; discard buffer
                                    # buffer = ""
                                    break

                            if in_message:
                                # Check if end tag is found
                                end_idx = buffer.find(end_tag)
                                if end_idx != -1:
                                    # Yield content up to end tag, then stop
                                    yield {
                                        "is_task_complete": False,
                                        "require_user_input": False,
                                        "content": buffer[:end_idx],
                                        "hang_up": False,
                                        "call_next_agent": False,
                                        "agent_name": ""
                                    }
                                    in_message = False
                                    buffer = buffer[end_idx + len(end_tag):]
                                    break
                                else:
                                    # No end tag yet, yield all and clear buffer
                                    yield {
                                        "is_task_complete": False,
                                        "require_user_input": False,
                                        "content": buffer,
                                        "hang_up": False,
                                        "call_next_agent": False,
                                        "agent_name": ""
                                    }
                                    buffer = ""
                                    break
            
            print("final_tool_calls: ", final_tool_calls)
            print("all_chunk_string: ", all_chunk_string)
            if final_tool_calls:
                for i, tool_call in final_tool_calls.items():
                    print(type(tool_call))
                    if isinstance(tool_call, ResponseFunctionToolCall):
                        args = json.loads(tool_call.arguments)
                        name = tool_call.name
                        print(f"Calling tool {name} with {args}")
                        tool_response = await session.call_tool(name, args)

                        input_messages.append(tool_call)  # append model's function call message
                        input_messages.append({                               # append result message
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": str(tool_response)
                        })

            else:
                is_continue=False
        
        # At the end, parse the complete response to get the final status
        try:
            parsed_response = self.parse_structure_output(all_chunk_string)
            print("parsed_response => ", parsed_response)
            action = parsed_response.action
            status = parsed_response.status
            agent_name = parsed_response.agent_name
            
            # TODO: Shold we save conversation history here ? 

            # Determine if we need user input or should hang up based on status
            require_input = status == "input_required"
            hang_up = status == "hang_up"

            if action == "call_next_agent":
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": parsed_response.message,
                    "hang_up": False,
                    "call_next_agent": True,
                    "agent_name": agent_name
                }
            else:
                yield {
                    "is_task_complete": True,
                    "require_user_input": require_input,
                    "content": parsed_response.message,
                    "hang_up": hang_up,
                    "call_next_agent": False,
                    "agent_name": ""
                }
        except Exception as e:
            print("Parse result error : ", e, all_chunk_string)
            # If we can't parse the final JSON, return what we have
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "",
                "hang_up": False,
                "call_next_agent": False,
                "agent_name": ""
            }

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

    def parse_structure_output(self, text: str) -> ResponseFormat:
        """
        Extracts the <output>...</output> XML block from a string,
        handles missing tags with defaults, and returns a ResponseFormat object.
        """
        # If no <output> block, try to wrap the XML manually
        if "<output>" not in text:
            text = f"<output>{text}</output>"

        match = re.search(r"<output>.*?</output>", text, re.DOTALL)
        if not match:
            raise ValueError("No <output> block found got, \n", text)

        output_xml = match.group(0)
        print("output_xml: ", output_xml)

        try:
            root = ET.fromstring(output_xml)
            tag_values = {child.tag: (child.text or "").strip('" ').strip() for child in root}

            return ResponseFormat(
                action=tag_values.get("action", "answer"),         # Default or error-prone
                status=tag_values.get("status", "input_required"),      # Default or error-prone
                custom_status=tag_values.get("custom_status", ""),
                agent_name=tag_values.get("agent_name", ""),       # Optional or blank
                message=tag_values.get("message", ""),             # Optional or blank
                next_agent_instruction=tag_values.get("next_agent_instruction", ""),    
                next_agent_schema=tag_values.get("next_agent_schema", "")
            )
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")

    def convert_tool_format(self, tools):
        """
        Converts tools into the format required for the Bedrock API.

        Args:
            tools (list): List of tool objects

        Returns:
            dict: Tools in the format required by Bedrock
        """
        converted_tools = []

        for tool in tools:
            converted_tool = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
                "strict": True
            }

            converted_tool['parameters']['additionalProperties'] = False
            converted_tools.append(converted_tool)

        return converted_tools

    def parse_agent_response(self, response):
        if response and isinstance(response, ResponseFormat): 
            # print("[Presale]: ", response.status)
            if response.action == 'answer':
                if response.status == "input_required":
                    return {
                        "is_task_complete": False,
                        "require_user_input": True,
                        "content": response.message,
                        "hang_up": False,
                        "call_next_agent": False,
                        "agent_name": ""
                    }
                elif response.status == "error":
                    return {
                        "is_task_complete": False,
                        "require_user_input": True,
                        "content": response.message,
                        "hang_up": False,
                        "call_next_agent": False,
                        "agent_name": ""
                    }
                elif response.status == "completed":
                    return {
                        "is_task_complete": True,
                        "require_user_input": False,
                        "content": response.message,
                        "hang_up": False,
                        "call_next_agent": False,
                        "agent_name": ""
                    }
                elif response.status == "hang_up":
                    return {
                        "is_task_complete": True,
                        "require_user_input": False,
                        "content": response.message,
                        "hang_up": True,
                        "call_next_agent": False,
                        "agent_name": ""
                    }
            elif response.action == 'call_next_agent':
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": response.message,
                    "hang_up": False,
                    "call_next_agent": True,
                    "agent_name": response.agent_name
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    def root_instruction(self, chat_history, tools=None, agent_info=None):
        prompt = self.agent_card.systemPrompt or "You are a helpful assistant."
        return A2A_OPENAI_NATIVE_BASE_PROMPT.format(agent_name=self.agent_card.name, system_prompt=prompt, chat_history=chat_history, agent_info=agent_info)

    def root_follow_up_instruction(self, chat_history: str, tools: Any = None, agent_info: Any = None) -> str:
        prompt = self.agent_card.systemPrompt or "You are a helpful assistant."
        return A2A_OPENAI_NATIVE_FOLLOW_UP_BASE_PROMPT.format(agent_name=self.agent_card.name, system_prompt=prompt, chat_history=chat_history, agent_info=agent_info)

    def _create_and_store_usage(self, usage_id: str, context_id: str, task_id: str, 
                               query: str, result: ResponseFormat, api_usage: ApiUsage, tool_calls: list[ToolCall], 
                               tool_outputs: list[ToolOutput]) -> Usage:
        usage = Usage(
            usage_id=usage_id,
            context_id=context_id,
            task_id=task_id,
            model_name=self.model_name,
            user_input=query,
            output=result,
            prompt_tokens=api_usage.prompt_tokens,
            completion_tokens=api_usage.completion_tokens,
            extra_usage=api_usage.extra_usage,
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

    def _extract_tool_calls_and_outputs(self, result) -> tuple[list[ToolCall], list[ToolOutput]]:
        pass
    def _extract_tool_call(self, item) -> ToolCall:
        pass
    def _extract_tool_output(self, item) -> ToolOutput:
        pass