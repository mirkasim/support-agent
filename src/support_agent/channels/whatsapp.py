"""WhatsApp channel implementation via Baileys bridge."""

import json
import base64
from typing import AsyncIterator
import aiohttp
import websockets
from ..core.message import Message, MessageType
from ..security.whitelist import ContactWhitelist
from .base import BaseChannel


class WhatsAppChannel(BaseChannel):
    """WhatsApp channel via Baileys bridge.

    Communicates with the Node.js Baileys bridge server via HTTP and WebSocket.
    """

    def __init__(self, bridge_url: str, whitelist: ContactWhitelist):
        """Initialize WhatsApp channel.

        Args:
            bridge_url: URL of Baileys bridge server (e.g., http://localhost:3000)
            whitelist: ContactWhitelist instance for authorization
        """
        super().__init__({"bridge_url": bridge_url})
        self.bridge_url = bridge_url.rstrip("/")
        self.whitelist = whitelist
        self.ws = None

    async def connect(self) -> None:
        """Connect to Baileys bridge WebSocket."""
        ws_url = self.bridge_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/messages"

        print(f"Connecting to WhatsApp bridge at {ws_url}...")
        self.ws = await websockets.connect(ws_url)
        self._connected = True
        print("Connected to WhatsApp bridge")

    async def disconnect(self) -> None:
        """Disconnect from Baileys bridge."""
        if self.ws:
            await self.ws.close()
            self.ws = None
        self._connected = False
        print("Disconnected from WhatsApp bridge")

    async def listen(self) -> AsyncIterator[Message]:
        """Listen for incoming messages from WhatsApp.

        Yields:
            Message objects from WhatsApp
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")

        async for raw_message in self.ws:
            try:
                data = json.loads(raw_message)

                # Handle different message types from bridge
                if data.get("type") == "message":
                    message_data = data.get("data", {})
                    message = await self._convert_to_message(message_data)

                    if message:
                        # Check whitelist
                        if not self.whitelist.is_whitelisted(message.sender_id):
                            print(f"⚠️  Message from non-whitelisted contact: {message.sender_id}")
                            print(f"    To whitelist this contact, run:")
                            print(f"    python scripts/add_contact.py '{message.sender_id}'")
                            continue

                        yield message

                elif data.get("type") == "status":
                    # Handle status updates
                    status = data.get("data", {})
                    print(f"WhatsApp status: {status}")

            except Exception as e:
                print(f"Error processing WebSocket message: {e}")
                continue

    async def send(self, message: Message) -> None:
        """Send message via Baileys bridge.

        Args:
            message: Message object to send
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.bridge_url}/api/send"

            # Determine recipient
            recipient = message.metadata.get("recipient") or message.sender_id

            payload = {"to": recipient, "text": str(message.content)}

            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to send message: {error_text}")

                print(f"Message sent to {recipient}")

    async def is_authorized(self, sender_id: str) -> bool:
        """Check if sender is authorized.

        Args:
            sender_id: WhatsApp contact ID (phone number)

        Returns:
            True if sender is whitelisted
        """
        return self.whitelist.is_whitelisted(sender_id)

    async def _convert_to_message(self, data: dict) -> Message | None:
        """Convert bridge message format to standard Message.

        Args:
            data: Message data from Baileys bridge

        Returns:
            Message object or None if conversion fails
        """
        try:
            message_id = data.get("id", "")
            from_id = data.get("from", "")
            from_name = data.get("fromName")
            body = data.get("body")
            timestamp = data.get("timestamp", 0)
            is_group = data.get("isGroup", False)
            message_type_str = data.get("messageType", "text")

            # Map message type
            message_type = MessageType.TEXT
            if message_type_str == "voice":
                message_type = MessageType.VOICE
            elif message_type_str == "image":
                message_type = MessageType.IMAGE
            elif message_type_str == "video":
                message_type = MessageType.VIDEO
            elif message_type_str == "document":
                message_type = MessageType.DOCUMENT

            # Handle voice data
            content = body
            if message_type == MessageType.VOICE and "voiceData" in data:
                # Voice data is base64 encoded in the bridge
                voice_data_b64 = data.get("voiceData", "")
                if voice_data_b64:
                    content = base64.b64decode(voice_data_b64)

            return Message(
                message_id=message_id,
                content=content,
                message_type=message_type,
                sender_id=from_id,
                sender_name=from_name,
                channel="whatsapp",
                is_group=is_group,
                metadata=data,
            )

        except Exception as e:
            print(f"Error converting message: {e}")
            return None

    @property
    def channel_name(self) -> str:
        """Return channel name."""
        return "whatsapp"

    async def get_status(self) -> dict:
        """Get WhatsApp bridge status.

        Returns:
            Status dictionary
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.bridge_url}/api/status"
            async with session.get(url) as response:
                return await response.json()

    async def get_qr_code(self) -> str | None:
        """Get QR code for WhatsApp linking.

        Returns:
            QR code data URL or None
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.bridge_url}/api/qr"
            async with session.get(url) as response:
                data = await response.json()
                return data.get("qr")
