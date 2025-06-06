"""Convience methods to start servers."""

import click

from a2a_mcp.mcp import server, temp_server


@click.command()
@click.option('--run', 'command', default='mcp-server', help='Command to run')
@click.option(
    '--host',
    'host',
    default='localhost',
    help='Host on which the server is started or the client connects to',
)
@click.option(
    '--port',
    'port',
    default=8000,
    help='Port on which the server is started or the client connects to',
)
@click.option(
    '--transport',
    'transport',
    default='stdio',
    help='MCP Transport',
)
def main(command, host, port, transport) -> None:
    # TODO: Add other servers, perhaps dynamic port allocation
    if command == 'mcp-server':
        server.serve(host, port, transport)
    elif command == 'temp-mcp-server':
        temp_server.serve(host, port, transport)
    else:
        raise ValueError(f'Unknown run option: {command}')
