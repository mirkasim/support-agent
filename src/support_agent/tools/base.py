"""Base tool system with decorator support."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field
import inspect
import asyncio
from functools import wraps


class ToolResult(BaseModel):
    """Result of tool execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.data}"
        return f"Error: {self.error}"


class BaseTool(ABC):
    """Base class for all tools.

    Tools extend the agent's capabilities by allowing it to interact
    with external systems (servers, databases, APIs, etc.).
    """

    name: str
    description: str
    args_schema: type[BaseModel]

    def __init__(self):
        if not hasattr(self, "name"):
            self.name = self.__class__.__name__

    @abstractmethod
    async def _arun(self, **kwargs) -> ToolResult:
        """Async execution - must be implemented by subclasses.

        Args:
            **kwargs: Tool-specific arguments (validated against args_schema)

        Returns:
            ToolResult with success/error information
        """
        pass

    async def run(self, **kwargs) -> ToolResult:
        """Execute the tool with automatic validation.

        Args:
            **kwargs: Tool arguments

        Returns:
            ToolResult
        """
        try:
            # Validate inputs using Pydantic schema
            validated_args = self.args_schema(**kwargs)
            return await self._arun(**validated_args.model_dump())
        except Exception as e:
            return ToolResult(success=False, error=f"Validation error: {str(e)}")

    def to_dict(self) -> dict:
        """Convert tool to dictionary format for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema(),
        }


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    args_schema: Optional[type[BaseModel]] = None,
):
    """Decorator to convert a function into a Tool.

    Example:
        @tool(
            name="get_weather",
            description="Get current weather for a location"
        )
        async def get_weather(location: str) -> dict:
            # Implementation
            return {"temp": 72, "condition": "sunny"}

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to function docstring)
        args_schema: Pydantic model for arguments (auto-generated from function signature if not provided)

    Returns:
        Tool instance
    """

    def decorator(func: Callable) -> BaseTool:
        # Auto-generate schema from function signature if not provided
        schema = args_schema
        if schema is None:
            sig = inspect.signature(func)
            # Create Pydantic model from function signature
            fields = {}
            annotations = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                annotation = param.annotation if param.annotation != inspect.Parameter.empty else Any
                default = param.default if param.default != inspect.Parameter.empty else ...

                annotations[param_name] = annotation
                if default != ...:
                    fields[param_name] = default

            # Create dynamic Pydantic model
            schema = type(
                f"{func.__name__}_Schema",
                (BaseModel,),
                {
                    "__annotations__": annotations,
                    **fields,
                },
            )

        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or f"Tool: {tool_name}"

        # Create tool class dynamically
        class DynamicTool(BaseTool):
            def __init__(self):
                self.name = tool_name
                self.description = tool_desc.strip()
                self.args_schema = schema
                self._func = func

            async def _arun(self, **kwargs) -> ToolResult:
                try:
                    # Handle both sync and async functions
                    if asyncio.iscoroutinefunction(self._func):
                        result = await self._func(**kwargs)
                    else:
                        # Run sync function in thread pool
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, lambda: self._func(**kwargs))

                    return ToolResult(success=True, data=result)
                except Exception as e:
                    return ToolResult(success=False, error=str(e))

        return DynamicTool()

    return decorator
