from a2a_mcp.common.base_agent.base_agent import BaseAgent, ResponseFormat
from a2a_mcp.common.prompts import A2A_NOVA_BASE_PROMPT
import boto3
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
import time
from colorama import Fore, Style, init

class A2ANovaAgent(BaseAgent):
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        super().__init__(agent_card.modelName, agent_card, card_discovery)  # Call BaseAgent's __init__

        self.mcp_server = mcp_server
        self.bedrock_client = boto3.client(
            os.environ.get("AWS_CLIENT_TYPE"),
            region_name=os.environ.get("AWS_REGION_NAME"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )

        # TODO: Still need memory manager here?
        print("=============== Using Nova ===============")

    async def invoke(self, query, context_id: str, task_id: str) -> ResponseFormat:
        history = "" # TODO: Load Memory
        agent_info = self.card_discovery.get_remote_agent_info()
        session = self.mcp_server[0]
        tools_result = await session.list_tools()
        tools_list = [{"name": tool.name, "description": tool.description,
          "inputSchema": tool.inputSchema} for tool in tools_result]
        print("Accessible tools: ", [tool['name'] for tool in tools_list])

        inst = self.root_instruction(chat_history=history, tools=json.dumps(tools_list, ensure_ascii=False), agent_info=agent_info)
        print(inst)

        system = [
            {
                "text": inst
            }
        ]

        messages = [
            {
                "role": "user",
                "content": [{"text": query}]
            }
        ]
        start_time = time.time()
        while True:
            response = self.bedrock_client.converse(
                modelId=self.model_name,
                messages=messages,
                system=system,
                inferenceConfig={
                    "maxTokens": 2024,
                    "temperature": 0
                },
                toolConfig=self.convert_tool_format(tools_result)
            )
            print(json.dumps(response, indent=4, ensure_ascii=False))

            output_message = response['output']['message']
            messages.append(output_message)
            stop_reason = response['stopReason']

            if stop_reason == 'tool_use':
                    tool_usage = []
                    # Tool use requested. Call the tool and send the result to the model.
                    tool_requests = response['output']['message']['content']
                    for tool_request in tool_requests:
                        if 'toolUse' in tool_request:
                            tool = tool_request['toolUse']
                            logger.info("Requesting tool %s. Request: %s",
                                        tool['name'], tool['toolUseId'])

                            try:
                                # Call the tool through the MCP session
                                tool_response = await session.call_tool(tool['name'], tool['input'])

                                # Convert tool response to expected format
                                tool_result = {
                                    "toolUseId": tool['toolUseId'],
                                    "content": [{"text": str(tool_response)}]
                                }
                            except Exception as err:
                                logger.error("Tool call failed: %s", str(err))
                                tool_result = {
                                    "toolUseId": tool['toolUseId'],
                                    "content": [{"text": f"Error: {str(err)}"}],
                                    "status": "error"
                                }

                            # Add tool result to messages
                            tool_usage.append({"toolResult": tool_result})

                    messages.append({
                        "role": "user",
                        "content": tool_usage
                    })
            else:
                # No more tool use requests, we're done
                break
        print(Fore.GREEN + Style.BRIGHT + "[Runner.run]:" + Style.RESET_ALL, time.time() - start_time)
        print("="*25)
        response_object = self.parse_structure_output(output_message['content'][0]['text'])
        print(response_object)

        # TODO: Shold we save conversation history here ? 

        return response_object

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:
        history = "" # TODO: Load Memory
        agent_info = self.card_discovery.get_remote_agent_info() # TODO: Add agent discovery information
        print("sessionId: ", sessionId)
        session = self.mcp_server[0]
        tools_result = await session.list_tools()
        
        tools_list = [{"name": tool.name, "description": tool.description,
          "inputSchema": tool.inputSchema} for tool in tools_result]
        
        inst = self.root_instruction(chat_history=history, tools=json.dumps(tools_list, ensure_ascii=False), agent_info=agent_info)
        print(inst)

        system = [
            {
                "text": inst
            }
        ]

        messages = [
            {
                "role": "user",
                "content": [{"text": query}]
            }
        ]

        while True:
            response = self.bedrock_client.converse_stream(
                modelId=self.model_name,
                messages=messages,
                system=system,
                inferenceConfig={
                    "maxTokens": 2024,
                    "temperature": 0
                },
                toolConfig=self.convert_tool_format(tools_result)
            )

            stop_reason = ""
        
            message = {}
            content = []
            message['content'] = content
            text = ''
            tool_use = {}

            # buffer for steaming
            in_message = False
            buffer = "" # This is temporary string buffer to collect chunk and be clear after yield response
            end_tag = "</" # "</message>"
            has_response = False # Flag to check if calling tool but also have quick message back to user, if true -> break conversation 
            all_chunk_string = "" # This is the string that collect all chunk, will be converted in to ResponseFormat object later

            #stream the response into a message.
            for chunk in response['stream']:
                if 'messageStart' in chunk:
                    message['role'] = chunk['messageStart']['role']
                elif 'contentBlockStart' in chunk:
                    tool = chunk['contentBlockStart']['start']['toolUse']
                    tool_use['toolUseId'] = tool['toolUseId']
                    tool_use['name'] = tool['name']
                elif 'contentBlockDelta' in chunk:
                    delta = chunk['contentBlockDelta']['delta']
                    if 'toolUse' in delta:
                        if 'input' not in tool_use:
                            tool_use['input'] = ''
                        tool_use['input'] += delta['toolUse']['input']
                    elif 'text' in delta:
                        text += delta['text']
                        all_chunk_string += delta['text']
                        buffer += delta['text']

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

                elif 'contentBlockStop' in chunk:
                    if 'input' in tool_use:
                        tool_use['input'] = json.loads(tool_use['input'])
                        content.append({'toolUse': tool_use})

                        tool_use = {}
                    else:
                        content.append({'text': text})
                        text = ''

                elif 'messageStop' in chunk:
                    stop_reason = chunk['messageStop']['stopReason']

            print(stop_reason)
            print(message)
            messages.append(message)

            if stop_reason == 'tool_use':
                    tool_usage = []
                    # Tool use requested. Call the tool and send the result to the model.
                    tool_requests = message["content"]
                    for tool_request in tool_requests:
                        if 'toolUse' in tool_request:
                            tool = tool_request['toolUse']
                            logger.info("Requesting tool %s. Request: %s",
                                        tool['name'], tool['toolUseId'])

                            try:
                                # Call the tool through the MCP session
                                tool_response = await session.call_tool(tool['name'], tool['input'])
                                print("tool_response: ", tool_response)
                                # Convert tool response to expected format
                                tool_result = {
                                    "toolUseId": tool['toolUseId'],
                                    "content": [{"text": str(tool_response.content[0].text)}]
                                }
                            except Exception as err:
                                logger.error("Tool call failed: %s", str(err))
                                tool_result = {
                                    "toolUseId": tool['toolUseId'],
                                    "content": [{"text": f"Error: {str(err)}"}],
                                    "status": "error"
                                }
                            # Add tool result to messages
                            tool_usage.append({"toolResult": tool_result})

                    messages.append({
                        "role": "user",
                        "content": tool_usage
                    })
            else:
                # No more tool use requests, we're done
                break

            if has_response:
                # already response some msg to user already, so break conversation | model call tool but no need to wait tool result
                break

        print("="*25)
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
                "require_user_input": require_input,
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
                "toolSpec": {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": {
                        "json": tool.inputSchema
                    }
                }
            }
            converted_tools.append(converted_tool)

        return {
                "toolChoice": {
                    "auto": {}
                },
                "tools": converted_tools
            }

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
        return A2A_NOVA_BASE_PROMPT.format(system_prompt=prompt, chat_history=chat_history, tools=tools, agent_info=agent_info)