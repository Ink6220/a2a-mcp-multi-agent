from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.prompts import A2A_OPENAI_NATIVE_BASE_PROMPT
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
from a2a_mcp.common.types import CustomAgentCard
from a2a_mcp.common.card_discovery import A2ACardDiscovery
import traceback
import time
from colorama import Fore, Style, init
from openai import OpenAI, AsyncOpenAI


class A2AOpenaiAgentNative(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        super().__init__(agent_card.modelName, agent_card, card_discovery)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.agent = None
        
        # TODO: Still need memory manager here?
        print("=============== Using Openai ===============")

    def get_agent(self, history, agent_info):
        inst = self.root_instruction(chat_history=history, agent_info=agent_info)
        print(inst)

        client = AsyncOpenAI()
        assistant = client.beta.assistants.create(
            instructions=inst,
            model=self.model_name,
            tools=[],
            temperature=0
        )
        return client, assistant
         
    async def invoke(self, query, context_id: str, task_id: str) -> ResponseFormat:
        try:
            history = "" # TODO: Load Memory
            agent_info = self.card_discovery.get_remote_agent_info()
            inst = self.root_instruction(chat_history=history, agent_info=agent_info)
            session = self.mcp_server[0]
            tools_result = await session.list_tools()
            tools_list = [{"name": tool.name, "description": tool.description,
                            "inputSchema": tool.inputSchema} for tool in tools_result]
            start_time = time.time()
            client = AsyncOpenAI()
            
            tools = self.convert_tool_format(tools_result)
            print(json.dumps(tools, indent=4, ensure_ascii=False))

            input_messages = [{"role": "user", "content": query}]
            is_continue = True # True while agent calling tools, False after agent try to answer
            while is_continue:
                print("\n\n")
                response = await client.responses.create(
                    instructions=inst,
                    model=self.model_name,
                    input=input_messages,
                    tools=tools,
                    tool_choice='auto',
                    temperature=0
                )

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
                    else:
                        is_continue = False
                        break
                
            print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
            print("\n\n")
            response_object = self.parse_structure_output(output_message[0].content[0].text)
            print(output_message[0].content[0].text)

            # TODO: Shold we save conversation history here ? 

        except OpenAIError as e:
            traceback.print_exc()
            print(e)

        return response_object

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
        return A2A_OPENAI_NATIVE_BASE_PROMPT.format(system_prompt=prompt, chat_history=chat_history, agent_info=agent_info)