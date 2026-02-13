"""Web chat channel implementation."""

import json
import asyncio
from typing import AsyncIterator, Set, Dict
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
import uuid

from .base import BaseChannel
from ..core.message import Message, MessageType


class WebChannel(BaseChannel):
    """Web chat channel via WebSocket.

    Handles real-time chat communication through web browser.
    """

    def __init__(self):
        """Initialize web channel."""
        super().__init__({"name": "web"})
        self.active_connections: Set[WebSocket] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.user_sessions: Dict[str, str] = {}  # websocket id -> user id

    async def connect(self) -> None:
        """Connect to web channel (no-op for web)."""
        self._connected = True
        logger.info("Web channel ready")

    async def disconnect(self) -> None:
        """Disconnect from web channel."""
        # Close all active WebSocket connections
        for websocket in list(self.active_connections):
            try:
                await websocket.close()
            except:
                pass
        self.active_connections.clear()
        self._connected = False
        logger.info("Web channel disconnected")

    async def handle_websocket(self, websocket: WebSocket):
        """Handle individual WebSocket connection.

        Args:
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        self.active_connections.add(websocket)

        # Generate unique session ID for this WebSocket connection
        # This will be different on every page refresh, triggering history reset
        session_id = str(uuid.uuid4())
        user_id = f"web_{session_id[:8]}"
        self.user_sessions[str(id(websocket))] = user_id

        logger.info(f"New web client connected: {user_id} (session: {session_id})")

        try:
            # Send welcome message
            await websocket.send_json({
                "type": "system",
                "message": "Connected to Support Agent. How can I help you?",
                "user_id": user_id,
                "session_id": session_id
            })

            # Listen for messages
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # Create message object with session_id in metadata
                # This allows agent to detect page refresh and clear history
                message = Message(
                    content=message_data.get("message", ""),
                    message_type=MessageType.TEXT,
                    sender_id=user_id,
                    sender_name=message_data.get("username", "User"),
                    channel="web",
                    metadata={
                        "websocket_id": str(id(websocket)),
                        "session_id": session_id  # Track session for history management
                    }
                )

                # Put in queue for processing
                await self.message_queue.put(message)

        except WebSocketDisconnect:
            logger.info(f"Web client disconnected: {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.active_connections.discard(websocket)
            ws_id = str(id(websocket))
            if ws_id in self.user_sessions:
                del self.user_sessions[ws_id]

    async def listen(self) -> AsyncIterator[Message]:
        """Listen for incoming messages from web clients.

        Yields:
            Message objects from web chat
        """
        while True:
            message = await self.message_queue.get()
            yield message

    async def send(self, message: Message) -> None:
        """Send message to web client(s).

        Args:
            message: Message object to send
        """
        # Find the target WebSocket connection
        target_ws_id = message.metadata.get("websocket_id")

        response_data = {
            "type": "message",
            "message": str(message.content),
            "sender": "agent",
            "timestamp": message.timestamp.isoformat()
        }

        if target_ws_id:
            # Send to specific connection
            for websocket in self.active_connections:
                if str(id(websocket)) == target_ws_id:
                    try:
                        await websocket.send_json(response_data)
                        logger.info(f"Sent message to web client")
                    except Exception as e:
                        logger.error(f"Failed to send message: {e}")
                    break
        else:
            # Broadcast to all connections (shouldn't happen normally)
            for websocket in list(self.active_connections):
                try:
                    await websocket.send_json(response_data)
                except Exception as e:
                    logger.error(f"Failed to broadcast message: {e}")

    async def is_authorized(self, sender_id: str) -> bool:
        """Check if sender is authorized.

        Args:
            sender_id: Web user ID

        Returns:
            True (web users are authorized by default, add auth if needed)
        """
        # For web channel, all connected users are authorized
        # You can add authentication here if needed
        return True

    @property
    def channel_name(self) -> str:
        """Return channel name."""
        return "web"
