# FilteredMCPServerSse Class

This Python class, `FilteredMCPServerSse`, extends the base `MCPServerSse` (presumably from an `agents.mcp` module) to provide enhanced capabilities for interacting with an MCP (Multi-Agent Control Plane) server, specifically by adding tool filtering.

It allows developers to specify lists of tools to either exclusively include or exclude when querying the MCP server for available tools. This is useful for tailoring the set of tools an agent or system component is aware of or interacts with.

## Features

*   **Inherits from `MCPServerSse`**: Leverages all the base functionality of `MCPServerSse` for connecting to and interacting with an MCP server via Server-Sent Events (SSE).
*   **Tool Filtering**:
    *   **Include List (`include_tools`)**: If provided, `list_tools()` will only return tools whose names are in this list.
    *   **Exclude List (`exclude_tools`)**: If provided, `list_tools()` will return all tools from the server *except* those whose names are in this list.
    *   **Mutual Exclusivity**: `include_tools` and `exclude_tools` cannot be specified simultaneously.
*   **Caching**: Inherits the `cache_tools_list` functionality from `MCPServerSse`, allowing the fetched (and potentially filtered) tool list to be cached.
*   **Resource Discovery**: Provides a `find_resource()` method to read arbitrary resources from the connected MCP server.
*   **Performance Logging**: The `list_tools()` method includes basic timing output (using `colorama`) for fetching tools, aiding in debugging and performance monitoring.

## Class Definition

### `__init__(self, params, include_tools=None, exclude_tools=None, cache_tools_list=False, name=None)`

Initializes a new `FilteredMCPServerSse` instance.

**Parameters:**

*   `params` (dict): Configuration parameters for the MCP server connection. This typically includes:
    *   `url`: The URL of the MCP server.
    *   `headers` (optional): Headers to send with requests.
    *   `timeout` (optional): HTTP request timeout.
    *   SSE connection specific timeouts.
    (Refer to `MCPServerSse` documentation for full `params` details.)
*   `include_tools` (Optional[list[str]]): A list of tool names to exclusively include. If provided, only tools matching these names will be returned by `list_tools()`. Default: `None`.
*   `exclude_tools` (Optional[list[str]]): A list of tool names to exclude. Tools matching these names will be filtered out by `list_tools()`. Default: `None`.
    *   **Note**: A `ValueError` is raised if both `include_tools` and `exclude_tools` are provided.
*   `cache_tools_list` (bool): Whether to cache the tools list. If `True`, the list is fetched once and stored. If `False`, it's fetched on every call to `list_tools()`. The cache can be invalidated using methods from the parent `MCPServerSse` class (e.g., `invalidate_tools_cache()`). Default: `False`.
*   `name` (Optional[str]): A human-readable name for the server instance. If not provided, one might be generated based on the URL (behavior inherited from `MCPServerSse`). Default: `None`.

### Methods

#### `filter_tools(self, tools_list: list) -> list`

Filters a given list of tool objects based on the `self.include_tools` or `self.exclude_tools` specifications.

*   **Parameters:**
    *   `tools_list` (list): A list of tool objects (presumably `MCPTool` instances or similar, as returned by the base `MCPServerSse.list_tools()`).
*   **Returns:** (list) A new list containing only the filtered tool objects.

#### `async list_tools(self) -> list`

Asynchronously fetches the list of available tools from the MCP server and applies the configured include/exclude filters.

*   This method overrides the `list_tools()` method from `MCPServerSse`.
*   It first calls `super().list_tools()` to get the unfiltered list.
*   Then, it applies `self.filter_tools()` to the result.
*   Prints the time taken for the operation using `colorama`.
*   **Returns:** (list) The filtered list of tool objects.

#### `async find_resource(self, resource: str) -> mcp.types.ReadResourceResult`

Asynchronously reads a specified resource from the connected MCP server. This method likely delegates to the active `ClientSession`.

*   **Parameters:**
    *   `resource` (str): The URI of the resource to read (e.g., `'resource://agent_cards/list'`).
*   **Returns:** (`mcp.types.ReadResourceResult`) The result of the resource read operation, as defined by `mcp.types`.


## Dependencies

*   `colorama`: For colored terminal output (used in `list_tools`).
*   The base `MCPServerSse` class (presumably from `agents.mcp.MCPServerSse` or a similar path).
*   `mcp.types`: For type hints, specifically `ReadResourceResult`.
*   `mcp.ClientSession`: Implicitly used by `find_resource` via `self.session`.

## Notes

*   This class is designed to be used asynchronously, with its methods `list_tools` and `find_resource` being `async` methods.
*   The actual `MCPTool` object structure and `mcp.types.ReadResourceResult` are dependent on the specific MCP library being used. The documentation assumes these are well-defined in the broader context of the `mcp` package.
*   For `find_resource` to work, the `self.session` attribute (likely an instance of `mcp.ClientSession` or similar) must be properly initialized, typically when the server object is used as an asynchronous context manager (i.e., with `async with`).
