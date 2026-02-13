"""OpenAI-compatible LLM implementation."""

import json
from typing import List, Optional, Dict
from openai import AsyncOpenAI
from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI-compatible LLM provider.

    Works with OpenAI API and compatible services (OpenRouter, etc.).
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        hide_reasoning: bool = True,
    ):
        """Initialize OpenAI LLM.

        Args:
            model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4', 'o1')
            base_url: Base URL for API (None for default OpenAI)
            api_key: API key
            hide_reasoning: Hide reasoning/thinking tokens (for o1 models)
        """
        super().__init__(model=model, base_url=base_url, api_key=api_key, hide_reasoning=hide_reasoning)

        # Initialize client
        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate response using OpenAI API.

        Args:
            messages: Conversation history
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            Generated response text
        """
        # Prepend system message if provided
        full_messages = messages.copy()
        if system_prompt:
            full_messages.insert(0, {"role": "system", "content": system_prompt})

        # For o1 models, we need different parameters
        is_o1_model = self.model.startswith("o1")

        if is_o1_model:
            # o1 models don't support temperature or max_tokens
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
            )
        else:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        message = response.choices[0].message
        content = message.content or ""

        # For reasoning models: hide reasoning tokens if configured
        # o1 models may include reasoning in the response metadata
        if self.hide_reasoning and hasattr(message, 'reasoning_content') and message.reasoning_content:
            # Reasoning content is separate, we just return the main content
            pass

        return content

    async def generate_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict:
        """Generate response with native function calling.

        Args:
            messages: Conversation history
            tools: Available tools in OpenAI format
            system_prompt: System prompt
            temperature: Sampling temperature

        Returns:
            Dict with response type and content
        """
        # Prepend system message if provided
        full_messages = messages.copy()
        if system_prompt:
            full_messages.insert(0, {"role": "system", "content": system_prompt})

        # Convert tools to OpenAI function format
        functions = self._convert_tools_to_functions(tools)

        # o1 models don't support function calling or temperature
        is_o1_model = self.model.startswith("o1")

        if is_o1_model:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
            )
        else:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                functions=functions,
                temperature=temperature,
            )

        message = response.choices[0].message

        # Check if function was called (not available for o1 models)
        if not is_o1_model and message.function_call:
            return {
                "type": "tool_call",
                "content": {
                    "tool": message.function_call.name,
                    "args": json.loads(message.function_call.arguments),
                },
            }

        # Get content and optionally filter reasoning
        content = message.content or ""

        # Hide reasoning tokens if configured
        if self.hide_reasoning and hasattr(message, 'reasoning_content') and message.reasoning_content:
            # For o1 models with separate reasoning, it's already filtered
            pass

        # Fallback: Try to parse tool call from text (for models without function calling or o1)
        if content:
            tool_call = self._try_parse_tool_call(content)
            if tool_call:
                return {"type": "tool_call", "content": tool_call}

            # Strip common thinking patterns if hide_reasoning is enabled
            if self.hide_reasoning:
                content = self._strip_thinking_patterns(content)

        # Regular text response
        return {"type": "text", "content": content}

    def _try_parse_tool_call(self, text: str) -> Optional[Dict]:
        """Try to extract tool call from text response.

        Args:
            text: Response text that might contain a tool call

        Returns:
            Tool call dict or None
        """
        text = text.strip()

        # Extract content from markdown code blocks if present
        json_content = text

        # Look for markdown code blocks anywhere in the text
        if "```" in text:
            start_marker = text.find("```")
            if start_marker >= 0:
                content_start = text.find("\n", start_marker)
                if content_start >= 0:
                    content_start += 1
                    end_marker = text.find("```", content_start)
                    if end_marker >= 0:
                        json_content = text[content_start:end_marker].strip()
                    else:
                        json_content = text[content_start:].strip()

        # Try to extract JSON from text (support nested braces)
        if "{" in json_content and "}" in json_content:
            start = json_content.find("{")
            if start >= 0:
                # Count braces to find matching closing brace
                brace_count = 0
                end = start
                for i in range(start, len(json_content)):
                    if json_content[i] == '{':
                        brace_count += 1
                    elif json_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break

                if end > start:
                    json_str = json_content[start:end]
                    try:
                        tool_call = json.loads(json_str)
                        if "tool" in tool_call and "args" in tool_call:
                            return tool_call
                    except json.JSONDecodeError:
                        pass

        return None

    def _strip_thinking_patterns(self, text: str) -> str:
        """Strip common thinking/reasoning patterns from responses.

        Args:
            text: Response text that might contain thinking patterns

        Returns:
            Text with thinking patterns removed
        """
        import re

        # Remove lines that start with thinking indicators
        thinking_patterns = [
            r"^Let me think.*?\n",
            r"^I need to.*?\n",
            r"^I'll .*?\n",
            r"^I will .*?\n",
            r"^First, .*?\n",
            r"^To answer this.*?\n",
            r"^Thinking:.*?\n",
            r"^Thought:.*?\n",
            r"^Reasoning:.*?\n",
        ]

        cleaned = text
        for pattern in thinking_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

        return cleaned.strip()

    def _convert_tools_to_functions(self, tools: List[dict]) -> List[dict]:
        """Convert tool schemas to OpenAI function format."""
        functions = []
        for tool in tools:
            functions.append(
                {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "parameters": tool.get("parameters", {}),
                }
            )
        return functions
