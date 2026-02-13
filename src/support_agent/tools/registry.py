"""Tool registry for managing available tools."""

from typing import Dict, List
from .base import BaseTool


class ToolRegistry:
    """Registry for managing and accessing tools.

    Provides a central location for tool registration and lookup,
    making it easy to add new tools at runtime.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool
        print(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Args:
            name: Tool name to unregister
        """
        if name in self._tools:
            del self._tools[name]
            print(f"Unregistered tool: {name}")

    def get_tool(self, name: str) -> BaseTool:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance

        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            raise ValueError(
                f"Unknown tool: {name}. Available tools: {', '.join(self._tools.keys())}"
            )
        return self._tools[name]

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools.

        Returns:
            List of all tool instances
        """
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name

        Returns:
            True if tool exists, False otherwise
        """
        return name in self._tools

    def get_tools_schema(self) -> List[dict]:
        """Get schema for all tools (for LLM function calling).

        Returns:
            List of tool schemas suitable for LLM function calling
        """
        return [tool.to_dict() for tool in self._tools.values()]

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered (supports 'in' operator)."""
        return name in self._tools
