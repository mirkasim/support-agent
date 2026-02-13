"""Base channel interface for all messaging platforms."""

from abc import ABC, abstractmethod
from typing import AsyncIterator
from ..core.message import Message


class BaseChannel(ABC):
    """Base class for all communication channels.

    This provides a consistent interface for different messaging platforms
    (WhatsApp, Slack, Telegram, etc.) allowing the agent core to work
    with any channel without modification.
    """

    def __init__(self, config: dict):
        """Initialize the channel with configuration.

        Args:
            config: Channel-specific configuration dictionary
        """
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the channel.

        Should set self._connected = True on success.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the channel.

        Should set self._connected = False.
        """
        pass

    @abstractmethod
    async def listen(self) -> AsyncIterator[Message]:
        """Listen for incoming messages.

        Yields:
            Message objects as they arrive

        Example:
            async for message in channel.listen():
                await process_message(message)
        """
        pass

    @abstractmethod
    async def send(self, message: Message) -> None:
        """Send a message through the channel.

        Args:
            message: Message object to send
        """
        pass

    @abstractmethod
    async def is_authorized(self, sender_id: str) -> bool:
        """Check if sender is authorized to use the agent.

        Args:
            sender_id: Unique identifier for the sender

        Returns:
            True if sender is authorized, False otherwise
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if channel is currently connected."""
        return self._connected

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the channel name (e.g., 'whatsapp', 'slack')."""
        pass
