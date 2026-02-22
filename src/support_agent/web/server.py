"""Web server for chat interface."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import yaml
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from loguru import logger

from ..channels.web import WebChannel

# In-memory session store: {token: {"username": str, "expires": datetime}}
_sessions: Dict[str, dict] = {}
_SESSION_DURATION = timedelta(hours=8)


def _load_users(config_dir: Path) -> Dict[str, str]:
    """Load users from users.yaml. Returns {username: sha256_password_hash}."""
    users_file = config_dir / "users.yaml"
    if not users_file.exists():
        logger.warning(f"users.yaml not found at {users_file} — no users loaded, login will always fail")
        return {}
    try:
        with open(users_file, "r") as f:
            data = yaml.safe_load(f)
        users = {}
        for entry in data.get("users", []):
            username = str(entry.get("username", "")).strip()
            password = str(entry.get("password", "")).strip()
            if username and password:
                users[username] = password
        logger.info(f"Loaded {len(users)} user(s) from users.yaml")
        return users
    except Exception as e:
        logger.error(f"Failed to load users.yaml: {e}")
        return {}


def _verify_credentials(username: str, password: str, users: Dict[str, str]) -> bool:
    """Verify plaintext password against the stored SHA256 hash."""
    expected = users.get(username)
    if not expected:
        return False
    actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(actual, expected)


def _create_session(username: str) -> str:
    """Create and store a new session token for the given username."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "username": username,
        "expires": datetime.utcnow() + _SESSION_DURATION,
    }
    return token


def _get_session_user(token: Optional[str]) -> Optional[str]:
    """Return the username for a valid, non-expired session token, or None."""
    if not token or token not in _sessions:
        return None
    session = _sessions[token]
    if datetime.utcnow() > session["expires"]:
        del _sessions[token]
        return None
    return session["username"]


def _delete_session(token: Optional[str]) -> None:
    """Remove a session token."""
    if token:
        _sessions.pop(token, None)


def _ws_cookie(websocket: WebSocket, name: str) -> Optional[str]:
    """Parse a named cookie from the WebSocket request headers."""
    cookie_header = websocket.headers.get("cookie", "")
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == name:
            return v.strip()
    return None


class WebServer:
    """FastAPI web server for chat interface."""

    def __init__(
        self,
        web_channel: "WebChannel",
        host: str = "0.0.0.0",
        port: int = 8000,
        config_dir: Optional[str] = None,
    ):
        self.app = FastAPI(title="Support Agent Web Chat")
        self.web_channel = web_channel
        self.host = host
        self.port = port
        self.config_dir = Path(config_dir or os.environ.get("CONFIG_DIR", "./config"))
        self._users: Dict[str, str] = _load_users(self.config_dir)
        self._templates = Path(__file__).parent / "templates"
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/login")
        async def login_page():
            return FileResponse(self._templates / "login.html")

        @self.app.post("/login")
        async def login_submit(request: Request):
            form = await request.form()
            username = str(form.get("username", "")).strip()
            password = str(form.get("password", ""))
            if _verify_credentials(username, password, self._users):
                token = _create_session(username)
                response = RedirectResponse("/", status_code=302)
                response.set_cookie("session_token", token, httponly=True, samesite="strict")
                logger.info(f"User '{username}' logged in")
                return response
            logger.warning(f"Failed login attempt for username '{username}'")
            return RedirectResponse("/login?error=1", status_code=302)

        @self.app.get("/logout")
        async def logout(request: Request):
            token = request.cookies.get("session_token")
            _delete_session(token)
            response = RedirectResponse("/login", status_code=302)
            response.delete_cookie("session_token")
            return response

        @self.app.get("/")
        async def index(request: Request):
            token = request.cookies.get("session_token")
            if not _get_session_user(token):
                return RedirectResponse("/login", status_code=302)
            return FileResponse(self._templates / "chat.html")

        @self.app.get("/health")
        async def health():
            return {"status": "ok"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            token = _ws_cookie(websocket, "session_token")
            if not _get_session_user(token):
                await websocket.accept()
                await websocket.close(code=4001)
                return
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


def create_web_server(
    web_channel: "WebChannel",
    host: str = "0.0.0.0",
    port: int = 8000,
    config_dir: Optional[str] = None,
) -> WebServer:
    """Create web server instance.

    Args:
        web_channel: WebChannel instance
        host: Host to bind to
        port: Port to listen on
        config_dir: Path to config directory (defaults to CONFIG_DIR env var or ./config)

    Returns:
        WebServer instance
    """
    return WebServer(web_channel, host, port, config_dir)
