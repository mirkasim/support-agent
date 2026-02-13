"""Main agent orchestrator."""

from typing import Optional, Dict
from pathlib import Path
from datetime import datetime
from loguru import logger
from .message import Message, MessageType, ConversationContext
from ..llm.base import BaseLLM
from ..tools.registry import ToolRegistry
from ..voice.transcriber import Transcriber


class SupportAgent:
    """Main orchestrator for the support agent system.

    Handles message processing, LLM interaction, tool execution,
    and conversation management.
    """

    def __init__(
        self,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        transcriber: Optional[Transcriber] = None,
        system_prompt: Optional[str] = None,
        knowledge_base_path: Optional[Path] = None,
        session_timeout_seconds: int = 3600,
    ):
        """Initialize support agent.

        Args:
            llm: LLM instance for generating responses
            tool_registry: Registry of available tools
            transcriber: Whisper transcriber for voice messages
            system_prompt: System prompt for the LLM
            knowledge_base_path: Path to knowledge.md file
            session_timeout_seconds: Session timeout in seconds (default 1 hour)
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.transcriber = transcriber
        self.knowledge_base = self._load_knowledge_base(knowledge_base_path) if knowledge_base_path else ""
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.contexts: Dict[str, ConversationContext] = {}
        self.session_timeout_seconds = session_timeout_seconds

        logger.info("Support agent initialized")
        logger.info(f"Session timeout: {session_timeout_seconds} seconds")
        if self.knowledge_base:
            logger.info("Knowledge base loaded")

    def _load_knowledge_base(self, knowledge_path: Path) -> str:
        """Load knowledge base from markdown file.

        Args:
            knowledge_path: Path to knowledge.md

        Returns:
            Knowledge base content
        """
        try:
            if knowledge_path.exists():
                with open(knowledge_path, 'r') as f:
                    content = f.read()
                logger.info(f"Loaded knowledge base from {knowledge_path}")
                return content
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
        return ""

    def _default_system_prompt(self) -> str:
        """Generate default system prompt with available tools."""
        tools = self.tool_registry.get_all_tools()
        tools_desc = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])

        base_prompt = f"""You are a helpful support agent for server infrastructure.

Available tools:
{tools_desc}

When you need to use a tool, respond with a JSON object:
{{"tool": "tool_name", "args": {{"arg1": "value1"}}}}

Otherwise, respond naturally to the user's query. Be concise and professional."""

        # Add knowledge base if available
        if self.knowledge_base:
            return f"""{base_prompt}

# Knowledge Base

{self.knowledge_base}"""

        return base_prompt

    def _get_context(self, user_id: str, channel: str = "default", session_id: Optional[str] = None) -> ConversationContext:
        """Get or create conversation context for user and channel.

        Args:
            user_id: User identifier
            channel: Channel name (whatsapp, web, etc.)
            session_id: Session identifier (for web UI page refresh detection)

        Returns:
            ConversationContext for this user and channel
        """
        # Create unique context key per user per channel
        context_key = f"{channel}:{user_id}"

        # Check if context exists
        if context_key in self.contexts:
            context = self.contexts[context_key]

            # For web channel: check if this is a new session (page refresh)
            if channel == "web" and session_id:
                if context.session_id != session_id:
                    logger.info(f"Web session changed for {user_id}, clearing history")
                    context.clear()
                    context.session_id = session_id

            # For all channels: check time gap
            if context.should_reset(self.session_timeout_seconds):
                time_gap = (datetime.utcnow() - context.last_activity).total_seconds() / 60
                logger.info(f"Time gap of {time_gap:.1f} minutes detected for {context_key}, clearing history")
                context.clear()

        else:
            # Create new context
            self.contexts[context_key] = ConversationContext(user_id=user_id, session_id=session_id)
            logger.info(f"Created new context for {context_key}")

        return self.contexts[context_key]

    async def process_message(self, message: Message) -> Message:
        """Process an incoming message and generate a response.

        Args:
            message: Incoming message

        Returns:
            Response message
        """
        try:
            # Handle voice messages
            if message.is_voice:
                if not self.transcriber:
                    return message.create_reply("Voice messages are not supported.")

                logger.info(f"Transcribing voice message from {message.sender_id}")
                transcription = await self.transcriber.transcribe(message.content)
                logger.info(f"Transcribed: {transcription[:50]}...")

                # Convert to text message
                message = Message(
                    content=transcription,
                    message_type=MessageType.TEXT,
                    sender_id=message.sender_id,
                    sender_name=message.sender_name,
                    channel=message.channel,
                    is_group=message.is_group,
                    metadata={**message.metadata, "original_type": "voice"},
                )

            # Get conversation context (per user per channel)
            channel = message.channel or "default"
            session_id = message.metadata.get("session_id") if message.metadata else None
            context = self._get_context(message.sender_id, channel, session_id)
            context.add_message("user", str(message.content), message.timestamp)

            logger.info(f"Processing message from {message.sender_id}: {message.content[:50]}...")

            # Generate LLM response with tools (support chained tool calls)
            tools_schema = self.tool_registry.get_tools_schema()
            max_tool_iterations = 5  # Prevent infinite loops
            tool_iteration = 0

            while tool_iteration < max_tool_iterations:
                llm_response = await self.llm.generate_with_tools(
                    messages=context.get_messages(),
                    tools=tools_schema,
                    system_prompt=self.system_prompt,
                )

                # Check if LLM wants to use a tool
                if llm_response["type"] == "tool_call":
                    tool_call = llm_response["content"]
                    logger.info(f"Tool call {tool_iteration + 1}: {tool_call['tool']}")

                    # Execute tool
                    tool_result = await self._execute_tool_call(tool_call)

                    # Add tool result to context
                    # Format depends on whether this looks like a servers.json read
                    result_str = str(tool_result)

                    # Check if this is servers.json output (contains "servers" key)
                    if '"servers"' in result_str or "'servers'" in result_str:
                        tool_result_msg = f"""[Tool result: Got server list from servers.json]

IMPORTANT: The user wants to access a specific server from this list. You must:
1. Find the matching server entry in the JSON above
2. Extract the SSH command for that server
3. Call execute_ssh_command again with:
   - server: SSH_CONFIG["ssh_jump_host"]
   - command: <extracted_ssh_command> "systemctl status <service_name>" (or whatever command the user wants)

Server list result: {tool_result}"""
                    else:
                        tool_result_msg = f"""[Tool result from {tool_call['tool']}]
{tool_result}

[Analyze the result. If you have enough information, provide your final answer. Otherwise, call another tool.]"""

                    context.add_message("assistant", tool_result_msg)

                    # Continue loop to allow another tool call
                    tool_iteration += 1
                else:
                    # No more tool calls, we have final text response
                    response_text = llm_response["content"]
                    break
            else:
                # Max iterations reached
                logger.warning(f"Max tool iterations ({max_tool_iterations}) reached")
                response_text = "I've completed multiple operations. Let me know if you need anything else."

            # Save assistant response to context
            context.add_message("assistant", response_text)

            logger.info(f"Response generated: {response_text[:50]}...")

            # Create reply message - preserve original metadata for routing
            reply_metadata = message.metadata.copy() if message.metadata else {}
            reply_metadata["recipient"] = message.sender_id

            return Message(
                content=response_text,
                message_type=MessageType.TEXT,
                sender_id="agent",
                channel=message.channel,
                reply_to=message.message_id,
                is_group=message.is_group,
                metadata=reply_metadata,
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return message.create_reply(
                f"Sorry, I encountered an error processing your request: {str(e)}"
            )

    async def _execute_tool_call(self, tool_call: dict) -> str:
        """Execute a tool call and return result.

        Args:
            tool_call: Dict with 'tool' and 'args'

        Returns:
            Tool result as string
        """
        try:
            tool_name = tool_call["tool"]
            tool_args = tool_call.get("args", {})

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            tool = self.tool_registry.get_tool(tool_name)
            result = await tool.run(**tool_args)

            if result.success:
                logger.info(f"Tool executed successfully: {result.data}")
                return str(result.data)
            else:
                logger.error(f"Tool execution failed: {result.error}")
                return f"Error: {result.error}"

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Tool execution failed: {str(e)}"

    def clear_context(self, user_id: str) -> None:
        """Clear conversation context for a user.

        Args:
            user_id: User identifier
        """
        if user_id in self.contexts:
            self.contexts[user_id].clear()
            logger.info(f"Cleared context for user: {user_id}")
