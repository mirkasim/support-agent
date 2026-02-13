"""Message models for standardized communication across channels."""

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class MessageType(str, Enum):
    """Types of messages supported by the system."""

    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class Message(BaseModel):
    """Standardized message format across all channels.

    This model provides a consistent interface for messages regardless of
    the underlying channel (WhatsApp, Slack, Telegram, etc.).
    """

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: Any  # Text string, bytes for media, or file path
    message_type: MessageType = MessageType.TEXT
    sender_id: str  # Unique identifier for the sender (phone number, user ID, etc.)
    sender_name: Optional[str] = None
    channel: Optional[str] = None  # Channel name (whatsapp, slack, etc.)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reply_to: Optional[str] = None  # ID of message being replied to
    is_group: bool = False
    group_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def create_reply(self, content: str, message_type: MessageType = MessageType.TEXT) -> "Message":
        """Create a reply message to this message."""
        return Message(
            content=content,
            message_type=message_type,
            sender_id="agent",
            channel=self.channel,
            reply_to=self.message_id,
            is_group=self.is_group,
            group_id=self.group_id,
        )

    @property
    def is_text(self) -> bool:
        """Check if message is text type."""
        return self.message_type == MessageType.TEXT

    @property
    def is_voice(self) -> bool:
        """Check if message is voice type."""
        return self.message_type == MessageType.VOICE

    @property
    def is_media(self) -> bool:
        """Check if message contains media (image, video, document)."""
        return self.message_type in (
            MessageType.IMAGE,
            MessageType.VIDEO,
            MessageType.DOCUMENT,
        )


class ConversationContext(BaseModel):
    """Manages conversation history for a user."""

    user_id: str
    messages: list[dict] = Field(default_factory=list)
    max_history: int = 10  # Keep last N message pairs
    last_activity: Optional[datetime] = None
    session_id: Optional[str] = None  # Track current session (for web UI)

    def add_message(self, role: str, content: str, timestamp: Optional[datetime] = None) -> None:
        """Add a message to the conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
            timestamp: Message timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": timestamp.isoformat()
        })
        self.last_activity = timestamp

        # Trim to max history (keep system message + last N pairs)
        if len(self.messages) > (self.max_history * 2):
            # Keep all messages except the middle ones
            self.messages = self.messages[-(self.max_history * 2) :]

    def get_messages(self) -> list[dict]:
        """Get conversation history in OpenAI format (without timestamps)."""
        # Return messages without timestamp field for LLM compatibility
        return [{"role": msg["role"], "content": msg["content"]} for msg in self.messages]

    def should_reset(self, timeout_seconds: int) -> bool:
        """Check if context should be reset due to inactivity.

        Args:
            timeout_seconds: Timeout threshold in seconds

        Returns:
            True if time gap exceeds threshold
        """
        if self.last_activity is None:
            return False

        time_since_last = datetime.utcnow() - self.last_activity
        return time_since_last.total_seconds() > timeout_seconds

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
        self.last_activity = None
