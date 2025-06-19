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
from a2a_mcp.common.card_discovery import A2ACardDiscovery
import traceback
import time
from colorama import Fore, Style, init
from pydantic import ValidationError
from uuid import uuid4
from a2a_mcp.common.context_memory import ContextMemory
from a2a.types import Task

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
         
    async def invoke(self, query: str, task: Task) -> ResponseFormat:
        # TODO: maybe we should go through together on invoke(), if we are going to change response format etc (im not too clear on this)
        usage_id = str(uuid4())
        result = None
        try:
            #Memory management
            context_id = task.contextId
            task_id = task.id
            context_store = self.context_stores.get(context_id)
            if not context_store:
                context_store = ContextMemory()
                context_store.add_task(task)
                self.context_stores[context_id] = context_store
            else:
                existing_task = context_store.get_task(task_id)
                if existing_task:
                    context_store.update_task(task_id, task)
                else:
                    context_store.add_task(task)
            history = self.postprocess(self.context_stores.get(context_id))
            
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
        
            #Get tool calls and outputs and save to context store
            tool_calls, tool_outputs = self._extract_tool_calls_and_outputs(result)
            context_store.update_task_tools(task_id, tool_calls, tool_outputs)
            
            # Debug: แสดงข้อมูลที่เก็บใน context store
            print(f"\n{Fore.MAGENTA}=== TOOL STORAGE DEBUG ==={Style.RESET_ALL}")
            print(f"Task ID: {task_id}")
            print(f"Stored tool calls in context: {len(tool_calls)}")
            print(f"Stored tool outputs in context: {len(tool_outputs)}")
            print(f"Context has tool info for task: {context_store.has_task_tools(task_id)}")
            print(f"{Fore.MAGENTA}========================{Style.RESET_ALL}\n")
            
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
            else:
                yield {
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

    def postprocess(self, context_store: ContextMemory) -> str:
        """Process history from all tasks in the context memory
        
        Args:
            context_store: ContextMemory containing multiple tasks

        Returns:
            str: Formatted history from all tasks
        """

        lines = []
        
        # Debug: แสดงข้อมูล context store
        print(f"\n{Fore.BLUE}=== POSTPROCESS DEBUG ==={Style.RESET_ALL}")
        print(f"Number of tasks in context_store: {len(context_store.tasks) if context_store else 0}")
        print(f"{Fore.BLUE}========================{Style.RESET_ALL}\n")
        
        # Process all tasks in the context memory
        if context_store and context_store.tasks:
            for task in context_store.tasks:
                lines.append(f"=== Task {task.id} ===")
                
                # แสดง history ถ้ามี
                if task.history:
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
                  # เพิ่มข้อมูล tool calls และ outputs จาก context store
                if context_store.has_task_tools(task.id):
                    print(f"Found tool data for task {task.id}")
                    tool_data = context_store.get_task_tools(task.id)
                    tool_calls = tool_data.get("tool_calls", [])
                    tool_outputs = tool_data.get("tool_outputs", [])
                    
                    # แสดง tool calls และ outputs
                    for i, (tool_call, tool_output) in enumerate(zip(tool_calls, tool_outputs)):
                        lines.append(f"Tool {i+1} - Name: {tool_call.tool_name}")
                        lines.append(f"Arguments: {json.dumps(tool_call.arguments, ensure_ascii=False)}")
                        lines.append(f"Tool {i+1} Output: {tool_output.output}")
                else:
                    print(f"No tool data found for task {task.id}")
                
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
        # BaseAgent จะเก็บใน self._usage_logs[usage_id] = usage แล้ว        #Debug: แสดงสรุปการใช้งาน
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 USAGE TRACKING SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"Usage ID: {usage.usage_id}")
        print(f"Context ID: {usage.context_id}")
        
        # ดึงข้อมูล tool calls/outputs จาก ContextMemory แทน
        if self.context_store.has_task_tools(task_id):
            task_tools = self.context_store.get_task_tools(task_id)
            tool_calls = task_tools.get('tool_calls', [])
            tool_outputs = task_tools.get('tool_outputs', [])
            print(f"Tool Calls: {len(tool_calls)}")
            print(f"Tool Outputs: {len(tool_outputs)}")
            if tool_calls:
                for i, tc in enumerate(tool_calls):
                    print(f"  Tool {i+1}: {tc.function.name}")
        else:
            print(f"Tool Calls: 0")
            print(f"Tool Outputs: 0")
            
        print(f"Total usage logs: {len(self._usage_logs)}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        return usage        