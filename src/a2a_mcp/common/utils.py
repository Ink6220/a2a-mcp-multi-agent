# type: ignore
import logging
import os
from typing import Dict, List, Any, Optional

import google.generativeai as genai

from a2a_mcp.common.types import ServerConfig

from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    DataPart
)
import json


logger = logging.getLogger(__name__)


def init_api_key():
    """Initialize the API key for Google Generative AI."""
    if not os.getenv('GOOGLE_API_KEY'):
        logger.error('GOOGLE_API_KEY is not set')
        raise ValueError('GOOGLE_API_KEY is not set')

    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))


def config_logging():
    """Configure basic logging."""
    log_level = (
        os.getenv('A2A_LOG_LEVEL') or os.getenv('FASTMCP_LOG_LEVEL') or 'INFO'
    ).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))


def config_logger(logger):
    """Logger specific config, avoiding clutter in enabling all loggging."""
    # TODO: replace with env
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration."""
    return ServerConfig(
        host='localhost',
        port=10100,
        transport='sse',
        url='http://localhost:10100/sse',
    )


def get_data_parts(parts: list[Part]) -> list[str]:
    """Extracts Data content from all DataPart objects in a list of Parts.

    Args:
        parts: A list of `Part` objects.

    Returns:
        A list of strings containing the text content from any `DataPart` objects found.
    """
    return [json.dumps(part.root.data, ensure_ascii=False) for part in parts if isinstance(part.root, DataPart)]


def get_message_data(message: Optional[Message], delimiter: str = "\n") -> str:
    """Extracts and joins all data content from a Message's parts.

    Args:
        message: The `Message` object.
        delimiter: The string to use when joining data from multiple DataParts.

    Returns:
        A single string containing all data content, or an empty string if no data parts are found.
    """
    if not message:
        return ""
    return delimiter.join(get_data_parts(message.parts))


def artifact_dict_to_parts(artifact_dict: Dict[str, Any]) -> List[Part]:
    """Convert artifact dictionary to list of parts.
    
    Args:
        artifact_dict: Dictionary containing artifact data
        
    Returns:
        List[Part]: List of parts for the artifact, converted to TextParts
    """
    return [Part(root=TextPart(text=json.dumps(artifact_dict, indent=2, ensure_ascii=False)))]

def append_message_metadata(msg: Message, new_meta: dict[str, Any]) -> Message:
    msg.metadata = {**(msg.metadata or {}), **new_meta}
    return msg