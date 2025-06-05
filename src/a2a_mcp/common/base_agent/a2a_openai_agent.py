from base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.prompts import A2A_OPENAI_BASE_PROMPT
from agents import Agent, ModelSettings, Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
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
from a2a_mcp.common.types import CustomAgentCard
import traceback
import time
from colorama import Fore, Style, init

class A2AOpenaiAgent(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, mcp_server: list=[]):
        super().__init__(agent_card.modelName, agent_card)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.agent = None

        # TODO: Still need memory manager here?
        print("=============== Using Openai ===============")

    def get_agent(self, history, agent_info):
        inst = self.root_instruction(chat_history=history, agent_info=agent_info)
        print(inst)
        return Agent(
            name=self.agent_card.name,
            instructions=inst,
            model=self.model_name,
            mcp_servers=self.mcp_server,
            output_type=ResponseFormat,
            model_settings=ModelSettings(temperature=0.0)
        )
         
    async def invoke(self, query, session_id):
        try:
            history = "" # TODO: Load Memory
            agent_info = "" # TODO: Add agent discovery information
            self.agent = self.get_agent(history, agent_info)

            start_time = time.time()
            result = await Runner.run(self.agent, query)
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print(result.final_output)

            # TODO: Shold we save conversation history here ? 
        
        except OpenAIError as e:
            traceback.print_exc()
            print(e)

        return self.parse_agent_response(result.final_output)

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:

        history = "" # TODO: Load Memory
        agent_info = "" # TODO: Add agent discovery information
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
                if first_json!= "":
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
                    arguments = response_function_tool_call.arguments
                    call_id = response_function_tool_call.call_id
                    tool_name = response_function_tool_call.name
                    tool_status = response_function_tool_call.status

                    print(arguments, call_id, tool_name, tool_status)
                elif event.item.type == "tool_call_output_item":
                    print(f"-- Tool output: {event.item.output}")
                    raw_item = event.item.raw_item
                    call_id = raw_item['call_id']
                    output = json.loads(raw_item['output'])['text']

                elif event.item.type == "message_output_item":
                    print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
                else:
                    pass  # Ignore other event types
        
        # At the end, parse the complete response to get the final status
        try:
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

    def parse_structure_output(self, s: str) -> ResponseFormat:
        """
        Input:
            '{"model":"Mazda CX-5","brand":"Mazda"}{"model":"Mazda CX-5","brand":"Mazda"}' -> '{"model":"Mazda CX-5","brand":"Mazda"}'
            '{"model":"Mazda CX-5","brand":' -> ""
            '{"model":"Mazda CX-5","brand":"Mazda"}MMM' -> '{"model":"Mazda CX-5","brand":"Mazda"}'
        """
        open_brace_count = 0
        start_index = -1

        for i, char in enumerate(s):
            if char == '{':
                if open_brace_count == 0:
                    start_index = i
                open_brace_count += 1
            elif char == '}':
                open_brace_count -= 1
                if open_brace_count == 0 and start_index != -1:
                    return s[start_index:i+1]
        return ""

    def convert_tool_format(self, tools):
        pass

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
        return A2A_OPENAI_BASE_PROMPT.format(system_prompt=prompt, chat_history=chat_history, agent_info=agent_info)