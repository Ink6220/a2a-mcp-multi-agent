import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack

from agents.mcp import MCPServerStdio
from agents.mcp.server import MCPServerStdioParams

logger = logging.getLogger(__name__)


class MCPToolServerManager:
    """Manages multiple MCP tool servers loaded from JSON configuration."""
    
    def __init__(self, server_names: Optional[List[str]] = None, config_path: str = "src/a2a_mcp/common/base_mcp/mcp_config.json"):
        self.config_path = Path(config_path)
        self.server_names = server_names or []
        self.servers: List[MCPServerStdio] = []
        self.exit_stack: Optional[AsyncExitStack] = None
    
    async def load_servers_from_config(self) -> List[MCPServerStdio]:
        """Load and initialize MCP servers from JSON configuration."""
        if not self.server_names:
            logger.info("No MCP tool servers requested - skipping tool server initialization")
            return []
            
        if not self.config_path.exists():
            logger.warning(f"Configuration file {self.config_path} not found!")
            return []
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            servers = []
            mcp_config = config.get('mcpServers', {})
            
            # Filter to only requested servers
            requested_servers = {name: mcp_config[name] for name in self.server_names if name in mcp_config}
            
            # Warn about requested servers that don't exist in config
            missing_servers = set(self.server_names) - set(mcp_config.keys())
            if missing_servers:
                logger.warning(f"Requested MCP servers not found in config: {missing_servers}")
            
            logger.info(f"Loading {len(requested_servers)} MCP tool servers: {list(requested_servers.keys())}")
            
            for server_name, server_config in requested_servers.items():
                try:
                    logger.info(f"  Initializing {server_name}...")
                    
                    # Prepare server parameters
                    server_params: MCPServerStdioParams = {
                        "command": server_config["command"],
                        "args": server_config["args"]
                    }
                    
                    # Handle environment variables
                    if "env" in server_config:
                        server_params["env"] = {}
                        for key, value in server_config["env"].items():
                            # Handle JSON string values (like OPENAPI_MCP_HEADERS)
                            if isinstance(value, str) and key.endswith("_HEADERS"):
                                try:
                                    # Parse and re-encode JSON strings to ensure proper escaping
                                    headers = json.loads(value)
                                    server_params["env"][key] = json.dumps(headers)
                                except json.JSONDecodeError:
                                    # If it's not valid JSON, use as is
                                    server_params["env"][key] = value
                            else:
                                server_params["env"][key] = value
                    
                    # Create server instance
                    server = MCPServerStdio(
                        params=server_params,
                        cache_tools_list=True
                    )
                    
                    servers.append(server)
                    logger.info(f"  ✅ {server_name} server ready")
                    
                except Exception as e:
                    logger.error(f"  ❌ Failed to initialize {server_name}: {e}")
                    continue
            
            logger.info(f"Successfully loaded {len(servers)} MCP tool servers")
            self.servers = servers
            return servers
            
        except Exception as e:
            logger.error(f"Error loading MCP tool server configuration: {e}")
            return []
    
    async def initialize_servers(self) -> List[MCPServerStdio]:
        """Initialize all servers and return them ready for use."""
        servers = await self.load_servers_from_config()
        
        if not servers:
            logger.warning("No MCP tool servers loaded")
            return []
        
        # Initialize the async exit stack for lifecycle management
        self.exit_stack = AsyncExitStack()
        
        # Enter each server's context
        initialized_servers = []
        for server in servers:
            try:
                await self.exit_stack.enter_async_context(server)
                initialized_servers.append(server)
                logger.debug(f"Server {server} initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize server {server}: {e}")
                continue
        
        logger.info(f"Initialized {len(initialized_servers)} MCP tool servers")
        return initialized_servers
    
    async def cleanup(self):
        """Cleanup all servers properly."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
                logger.info("MCP tool servers cleaned up successfully")
            except Exception as e:
                logger.error(f"Error during MCP tool server cleanup: {e}")
            finally:
                self.exit_stack = None
        
        self.servers = [] 