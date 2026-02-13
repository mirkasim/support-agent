"""Web server for chat interface."""

import asyncio
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from loguru import logger

from ..core.message import Message, MessageType
from ..channels.web import WebChannel


class WebServer:
    """FastAPI web server for chat interface."""

    def __init__(self, web_channel: "WebChannel", host: str = "0.0.0.0", port: int = 8000):
        """Initialize web server.

        Args:
            web_channel: WebChannel instance for message handling
            host: Host to bind to
            port: Port to listen on
        """
        self.app = FastAPI(title="Support Agent Web Chat")
        self.web_channel = web_channel
        self.host = host
        self.port = port

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/")
        async def index():
            """Serve chat interface."""
            html_file = Path(__file__).parent / "templates" / "chat.html"
            return FileResponse(html_file)

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "ok"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for chat."""
            await self.web_channel.handle_websocket(websocket)

    async def start(self):
        """Start the web server."""
        import uvicorn

        logger.info(f"Starting web server on {self.host}:{self.port}")
        logger.info(f"Chat interface: http://{self.host}:{self.port}")

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


def create_web_server(web_channel: "WebChannel", host: str = "0.0.0.0", port: int = 8000) -> WebServer:
    """Create web server instance.

    Args:
        web_channel: WebChannel instance
        host: Host to bind to
        port: Port to listen on

    Returns:
        WebServer instance
    """
    return WebServer(web_channel, host, port)
