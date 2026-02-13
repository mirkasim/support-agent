"""Base LLM interface."""

from abc import ABC, abstractmethod
from typing import Optional, List


class BaseLLM(ABC):
    """Base class for LLM providers.

    Provides a consistent interface for different LLM providers
    (Ollama, OpenAI, etc.).
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        hide_reasoning: bool = True,
    ):
        """Initialize LLM.

        Args:
            model: Model name to use
            base_url: Base URL for API
            api_key: API key (if required)
            hide_reasoning: Hide reasoning/thinking tokens from responses
        """
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.hide_reasoning = hide_reasoning

    @abstractmethod
    async def generate(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt to prepend
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict:
        """Generate a response with tool calling support.

        Args:
            messages: List of message dicts
            tools: List of tool schemas
            system_prompt: System prompt
            temperature: Sampling temperature

        Returns:
            Dict with 'type' ('text' or 'tool_call') and 'content'
        """
        pass
