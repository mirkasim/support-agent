"""Ollama LLM implementation."""

import json
from typing import List, Optional
import aiohttp
from .base import BaseLLM


class OllamaLLM(BaseLLM):
    """Ollama LLM provider.

    Supports local Ollama instances for running LLMs like Llama2, Mistral, etc.
    """

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        hide_reasoning: bool = True,
    ):
        """Initialize Ollama LLM.

        Args:
            model: Model name (e.g., 'llama2', 'mistral', 'codellama')
            base_url: Ollama server URL
            hide_reasoning: Hide verbose thinking/reasoning from responses
        """
        super().__init__(model=model, base_url=base_url, hide_reasoning=hide_reasoning)

    async def generate(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate response using Ollama.

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

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"Ollama API error: {error}")

                data = await response.json()
                return data["message"]["content"]

    async def generate_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict:
        """Generate response with tool calling.

        Note: Ollama doesn't have native function calling yet, so we use
        prompt engineering to indicate tool usage.

        Args:
            messages: Conversation history
            tools: Available tools
            system_prompt: System prompt
            temperature: Sampling temperature

        Returns:
            Dict with response type and content
        """
        # Build enhanced system prompt with tools
        tools_desc = self._format_tools(tools)
        enhanced_prompt = f"""{system_prompt or ''}

Available tools:
{tools_desc}

⚠️ CRITICAL INSTRUCTIONS FOR TOOL USAGE:

When user asks you to DO something (check, connect, query, get, show, etc.):
1. Identify which tool matches the task
2. Respond with ONLY a JSON object (no explanations, no "I will..." text)
3. Format: {{"tool": "tool_name", "args": {{"arg1": "value1"}}}}

Examples of when to call tools:
- "connect to appserver1 and check CPU" → {{"tool": "execute_remote_server_command", "args": {{"server_name": "appserver1", "command": "top -bn1 | grep Cpu"}}}}
- "query customer database" → {{"tool": "execute_database_query", "args": {{"database": "customer", "query": "SELECT * FROM ..."}}}}
- "check system status" → {{"tool": "get_system_status", "args": {{}}}}

WRONG responses (don't do this):
- "I need to check..." ❌
- "Let me connect to..." ❌
- "I will query..." ❌

RIGHT responses:
- {{"tool": "...", "args": {{...}}}} ✅

Only respond with plain text AFTER getting tool results, to explain the results to the user.
"""

        response_text = await self.generate(messages, enhanced_prompt, temperature)

        # Try to parse as tool call
        response_text = response_text.strip()

        # Extract content from markdown code blocks if present
        json_content = response_text

        # Look for markdown code blocks anywhere in the text
        if "```" in response_text:
            # Find the first ``` and extract content until the closing ```
            start_marker = response_text.find("```")
            if start_marker >= 0:
                # Skip the opening ``` and optional language tag (json, etc.)
                content_start = response_text.find("\n", start_marker)
                if content_start >= 0:
                    content_start += 1
                    # Find closing ```
                    end_marker = response_text.find("```", content_start)
                    if end_marker >= 0:
                        json_content = response_text[content_start:end_marker].strip()
                    else:
                        # No closing marker, take rest of text
                        json_content = response_text[content_start:].strip()

        # Try to extract JSON from text (handle cases where there's text before/after JSON)
        if "{" in json_content and "}" in json_content:
            # Find the JSON object (support nested braces)
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
                            return {"type": "tool_call", "content": tool_call}
                    except json.JSONDecodeError:
                        pass

        # Regular text response - strip thinking patterns if configured
        if self.hide_reasoning:
            response_text = self._strip_thinking_patterns(response_text)

        return {"type": "text", "content": response_text}

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

    def _format_tools(self, tools: List[dict]) -> str:
        """Format tools for prompt."""
        lines = []
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            params = tool.get("parameters", {}).get("properties", {})

            param_str = ", ".join([f"{k}: {v.get('description', k)}" for k, v in params.items()])
            lines.append(f"- {name}({param_str}): {desc}")

        return "\n".join(lines)
