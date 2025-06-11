import random
from pathlib import Path
import os
import json
import pandas as pd
import requests
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger
logger = get_logger(__name__)

AGENT_CARDS_DIR = "agent_cards"

def load_agent_cards():
    """Loads agent card data from JSON files within a specified directory.

    Returns:
        A list containing JSON data from an agent card file found in the specified directory.
        Returns an empty list if the directory is empty, contains no '.json' files,
        or if all '.json' files encounter errors during processing.
    """
    card_uris = []
    agent_cards = []
    dir_path = Path(AGENT_CARDS_DIR)
    if not dir_path.is_dir():
        logger.error(
            f'Agent cards directory not found or is not a directory: {AGENT_CARDS_DIR}'
        )
        return agent_cards

    logger.info(f'Loading agent cards from card repo: {AGENT_CARDS_DIR}')

    for filename in os.listdir(AGENT_CARDS_DIR):
        if filename.lower().endswith('.json'):
            file_path = dir_path / filename

            if file_path.is_file():
                logger.info(f'Reading file: {filename}')
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        card_uris.append(
                            f'resource://agent_cards/{Path(filename).stem}'
                        )
                        agent_cards.append(data)
                except json.JSONDecodeError as jde:
                    logger.error(f'JSON Decoder Error {jde}')
                except OSError as e:
                    logger.error(f'Error reading file {filename}: {e}.')
                except Exception as e:
                    logger.error(
                        f'An unexpected error occurred processing {filename}: {e}',
                        exc_info=True,
                    )
    logger.info(
        f'Finished loading agent cards. Found {len(agent_cards)} cards.'
    )
    return card_uris, agent_cards


def build_agent_card_dataframe() -> pd.DataFrame:
    """Loads agent cards, generates embeddings for them, and returns a DataFrame.

    Returns:
        Optional[pd.DataFrame]: A Pandas DataFrame containing the original
        'agent_card' data and their corresponding 'Embeddings'. Returns None
        if no agent cards were loaded initially or if an exception occurred
        during the embedding generation process.
    """
    card_uris, agent_cards = load_agent_cards()
    logger.info('Generating Embeddings for agent cards')
    try:
        if agent_cards:
            df = pd.DataFrame(
                {'card_uri': card_uris, 'agent_card': agent_cards}
            )
            return df
        logger.info('Done generating embeddings for agent cards')
    except Exception as e:
        logger.error(f'An unexpected error occurred : {e}.', exc_info=True)
        return None


def serve(host, port, transport):  # noqa: PLR0915
    """Initializes and runs the Agent Cards MCP server.

    Args:
        host: The hostname or IP address to bind the server to.
        port: The port number to bind the server to.
        transport: The transport mechanism for the MCP server (e.g., 'stdio', 'sse').

    Raises:
        ValueError: If the 'GOOGLE_API_KEY' environment variable is not set.
    """
    logger.info('Starting Agent Cards MCP Server')
    mcp = FastMCP('agent-cards', host=host, port=port)

    df = build_agent_card_dataframe()
    print(df)
    @mcp.tool()
    def save_log_customer(callback_date: str, phone: str, status: str) -> str:
        """This tool is for recording the date, status, and phone number of customers. Use this tool whenever you need to record history for staff to follow up later or confirm their interest in insurance products.

        Args:
            callback_date: The date the customer scheduled an appointment or the date of the most recent call with the customer (day-month-year)
            phone: Customer's phone number
            status: Status of all types of insurance products that the customer is interested in (มาสด้า พรีเมี่ยมอินชัวร์แรน/นิสสัน พรีเมียมโพรเทคชั่น/ฟอร์ดเอนชัว/ประกันรถยนต์เกรดวอมอเตอ GWM/ประกันรถยนต์ชั้น 1/ประกันอุบัติเหตุผู้สูงอายุ PA55+/ประกันมะเร็ง ZCP/ติดต่อกลับ/ไม่สนใจ)
        """

        import requests
        print("\nsave_log_customer\n")

        url = "http://3.1.190.223:8000/tool/save_log"  # Replace with your target URL
        payload = {"callback_date": callback_date, "phone": phone, "status": status}     # Replace "gpt-4" with the actual model string
        print(payload)
        for key, value in payload.items():
            if value == "":
                return f"Please provide the '{key}' parameter."
        response = requests.get(url, params=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text



    @mcp.tool()
    def check_car_brand(model: str) -> str:
        """Use to check car's brand from model

        Args:
            model: model name of car
        """
        print("\ncheck_car_brand\n")

        import requests

        url = "http://3.1.190.223:8000/tool/car_brand"  # Replace with your target URL
        payload = {"model": model}     # Replace "gpt-4" with the actual model string

        response = requests.post(url, json=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text

    @mcp.tool()
    def data_car_insurance_2(query: str) -> str:
        """tool สำหรับดูข้อมูลประกันเกี่ยวกับรถ ใช้ตอนแนะนำประกันเกี่ยวกับรถ ถ้าไม่มีในรายชื่อ ['Mazda','Great Wall Motors','Nissan','Ford']ให้ใช้ 'ประกันชั้น 1' แทน

        Args:
            query: Information that will be used to search for the insurance that the customer wants, such as the car model or insurance level.
        """
        print("\ndata_car_insurance_2\n")

        import requests

        url = "http://3.1.190.223:8000/tool/data_car_insurance_2"  # Replace with your target URL
        payload = {"query": query}     # Replace "gpt-4" with the actual model string

        response = requests.get(url, params=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text


    @mcp.tool()
    def data_other_insurance(confirm_data: str) -> str:
        """tool For viewing other information that is not car insurance

        Args:
            confirm_data: Information that will be used to search for the insurance that the customer wants, such as the car model or insurance level.
        """
        print("\ndata_other_insurance\n")

        import requests

        url = "http://3.1.190.223:8000/tool/data_other_insurance"  # Replace with your target URL
        payload = {"confirm_data": confirm_data}     # Replace "gpt-4" with the actual model string

        response = requests.get(url, params=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text


    @mcp.tool()
    def get_memory(user_id: str) -> str:
        """tool สำหรับดึงประวัติความสนใจของลูกค้า ใช้เมื่อต้องการสรุปโปรโมชันที่ลูกค้าต้องการ

        Args:
            user_id: unique identifier
        """
        print("\nget_memory\n")

        import requests

        url = "http://3.1.190.223:8000/tool/note"  # Replace with your target URL
        payload = {"user_id": user_id, "options": "get", "content": "GETALL"}     # Replace "gpt-4" with the actual model string

        response = requests.post(url, json=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text

    @mcp.tool()
    def ops_memory(user_id: str, options: str, content: str) -> str:
        """tool สำหรับใช้ในการบันทึกความสนใจซื้อของลูกค้าในผลิตภัณฑ์ที่ได้นำเสนอให้ หากลูกค้าสนใจก็ add ข้อมูล หากลูกค้าเปลี่ยนใจให้ del (delete) 

        Args:
            user_id: unique identifier
            options: memory options (add/del).
            content: content of the memory to add or delete, ผลิตภัณฑ์ที่เป็นไปได้ (มาสด้า พรีเมี่ยมอินชัวร์แรน/นิสสัน พรีเมียมโพรเทคชั่น/ฟอร์ดเอนชัว/ประกันรถยนต์เกรดวอมอเตอ GWM/ประกันรถยนต์ชั้น 1/ประกันอุบัติเหตุผู้สูงอายุ PA55+/ประกันมะเร็ง ZCP).
        """
        print("\nops_memory\n")

        import requests

        url = "http://3.1.190.223:8000/tool/note"  # Replace with your target URL
        payload = {"user_id": user_id, "options": options, "content": content}     # Replace "gpt-4" with the actual model string

        response = requests.post(url, json=payload)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)

        return response.text

    @mcp.resource('resource://agent_cards/list', mime_type='application/json')
    def get_agent_cards() -> dict:
        """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/list'.

        Returns:
            A json / dictionary structured as {'agent_card_urls': [...], 'agent_cards': [...]}, where the value is a
            list containing all the loaded agent card dictionaries and urls. Returns
            {'agent_card_urls': [], 'agent_cards': []} if the data cannot be retrieved.
        """
        resources = {}
        logger.info('Starting read resources')
        resources['agent_card_urls'] = df['card_uri'].to_list()
        resources['agent_cards'] = df['agent_card'].to_list()
        return resources

    @mcp.resource(
        'resource://agent_cards/{card_name}', mime_type='application/json'
    )
    def get_agent_card(card_name: str) -> dict:
        """Retrieves an agent card as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/{card_name}'.

        Returns:
            A json / dictionary
        """
        resources = {}
        logger.info(
            f'Starting read resource resource://agent_cards/{card_name}'
        )
        resources['agent_card'] = (
            df.loc[
                df['card_uri'] == f'resource://agent_cards/{card_name}',
                'agent_card',
            ]
        ).to_list()

        return resources

    logger.info(
        f'Agent cards MCP Server at {host}:{port} and transport {transport}'
    )
    mcp.run(transport=transport)
