from agents.mcp import MCPServerSse
import time
from colorama import Fore, Style, init

class FilteredMCPServerSse(MCPServerSse):
    """MCP server implementation that extends MCPServerSse with tool filtering capabilities.
    
    This allows including or excluding specific tools by name when listing available tools.
    """

    def __init__(
        self,
        params: dict,
        include_tools: list[str] = None,
        exclude_tools: list[str] = None,
        cache_tools_list: bool = False,
        name: str | None = None,
    ):
        """Create a new MCP server with tool filtering capabilities.

        Args:
            params: The params that configure the server. This includes the URL of the server,
                the headers to send to the server, the timeout for the HTTP request, and the
                timeout for the SSE connection.
                
            include_tools: Optional list of tool names to include. If provided, only tools
                with these names will be returned by list_tools(). Cannot be used with exclude_tools.
                
            exclude_tools: Optional list of tool names to exclude. If provided, tools with
                these names will be filtered out from list_tools(). Cannot be used with include_tools.

            cache_tools_list: Whether to cache the tools list. If True, the tools list will be
                cached and only fetched from the server once. If False, the tools list will be
                fetched from the server on each call to list_tools(). The cache can be
                invalidated by calling invalidate_tools_cache().

            name: A readable name for the server. If not provided, we'll create one from the
                URL.
        """
        if include_tools and exclude_tools:
            raise ValueError("Cannot specify both include_tools and exclude_tools")
            
        super().__init__(params, cache_tools_list, name)
        self.include_tools = include_tools
        self.exclude_tools = exclude_tools

    def filter_tools(self, tools_list):
        """Filter tools based on include_tools or exclude_tools specifications.
        
        Args:
            tools_list: List of MCPTool objects returned from the server
            
        Returns:
            Filtered list of MCPTool objects
        """
        if self.include_tools:
            return [tool for tool in tools_list if tool.name in self.include_tools]
        elif self.exclude_tools:
            return [tool for tool in tools_list if tool.name not in self.exclude_tools]
        else:
            return tools_list

    async def list_tools(self) -> list:
        """List the tools available on the server, filtered according to include/exclude settings."""
        # Get the unfiltered tools list from the parent implementation
        start_time = time.time()
        unfiltered_tools = await super().list_tools()

        # Apply filtering
        filtered_tools = self.filter_tools(unfiltered_tools)
        print(Fore.YELLOW + Style.BRIGHT + "Time fetching tools:" + Style.RESET_ALL, time.time() - start_time)
        return filtered_tools