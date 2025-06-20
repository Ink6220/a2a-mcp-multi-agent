# type: ignore

import json
import logging
import sys

from pathlib import Path

import click
import httpx
import uvicorn
import asyncio

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier

from a2a_mcp.common.types import CustomAgentCard
# from a2a_mcp.common.memory_management import MemoryManagement
from a2a_mcp.common.base_executor import BaseAgentExecutor
from a2a_mcp.common.base_agent.a2a_agent_selector import A2AAgentSelector
from a2a_mcp.common.base_mcp.filtered_mcp_server_sse import FilteredMCPServerSse
from a2a_mcp.common.card_discovery import A2ACardDiscovery
from a2a_mcp.common.prompts import PRESALE_PROMPT

import os
from dotenv import load_dotenv
load_dotenv(".env")

logger = logging.getLogger(__name__)

def run_uvicorn(server: A2AStarletteApplication, host="127.0.0.1", port=8000):
    uvicorn.run(server.build(), host=host, port=port)

def get_agent(agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: FilteredMCPServerSse):
    """Get the agent, given an agent card."""
    try:
        # TODO: add systemprompt instruction into agent_card based on agent name, due to load agent card from .json -> cannot directly passing prompt and connot write multiple line of string into systemPrompt.
        if agent_card.name == "Presale Agent":
            agent_card.systemPrompt = PRESALE_PROMPT

        return A2AAgentSelector(agent_card=agent_card, card_discovery=card_discovery, mcp_server=[mcp_server]).get_agent()
    except Exception as e:
        raise e

async def init_agent_server(host, port, agent_card, mcp_url, include_tools, exclude_tools):
    """Initialize and start the agent server with MCP connection"""
    
    with Path(agent_card).open(encoding='utf-8') as file:
        data = json.load(file)
    agent_card = CustomAgentCard(**data)

    # Connect to MCP server using proper async context manager
    async with FilteredMCPServerSse(
        name="SSE Python Server",
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        cache_tools_list=True,
        params={
            "url": mcp_url,
        },
    ) as mcp_server:
        logger.info(f"MCP server initialized and connected to {mcp_url}")
        a2a_card_discovery = A2ACardDiscovery(agent_card)
        agent_cards, agent_info = await a2a_card_discovery.discovery_agent_card(mcp_server)        
        print("Discover:")
        print(a2a_card_discovery.get_remote_agent_info())

        memory = MemoryManagement()

        client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=BaseAgentExecutor(agent=get_agent(agent_card, a2a_card_discovery, mcp_server), memory=memory),
            task_store=memory,
            push_notifier=InMemoryPushNotifier(client),
        )

        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        logger.info(f'Starting server on {host}:{port}')

        # Since server.start() is blocking, we need to run it differently
        import threading
        server_thread = threading.Thread(target=run_uvicorn, args=(server,host,port))
        server_thread.daemon = True
        server_thread.start()

        # Keep the main event loop running to maintain the MCP connection
        try:
            # Keep the async context alive as long as the server is running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Server stopping due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in server: {e}")
        finally:
            # Server cleanup happens automatically as we exit the async context
            logger.info("Cleaning up server resources")

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10000)
@click.option('--agent-card', 'agent_card')
@click.option("--mcp-url", "mcp_url", default="http://localhost:8000/sse")
@click.option(
    "--include-tools",
    multiple=True,
    default=("save_log_customer",),
    help="List of tool names to include (allowlist)."
)
@click.option(
    "--exclude-tools",
    multiple=True,
    help="List of tool names to exclude (denylist)."
)
def main(host, port, agent_card, mcp_url, include_tools, exclude_tools):
    """Starts an Agent server."""
    try:
        if not agent_card:
            raise ValueError('Agent card is required')
        
        asyncio.run(init_agent_server(host, port, agent_card, mcp_url, include_tools, exclude_tools))

    except FileNotFoundError:
        logger.error(f"Error: File '{agent_card}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error: File '{agent_card}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()

# uv run src/a2a_mcp/agents/ --port 10000 --agent-card agent_cards/presale_agent.json --mcp-url http://localhost:8000/sse --include-tools save_log_customer --include-tools check_car_brand --include-tools data_car_insurance_2 --include-tools data_other_insurance