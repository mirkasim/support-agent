"""SSH server access tool with configuration support."""

import asyncio
import os
from pathlib import Path
from pydantic import BaseModel, Field
import asyncssh
from ..base import tool


# Global configuration - will be set during tool registration
SSH_CONFIG = {
    "username": "admin",
    "key_file": None,
    "timeout": 30,
}


def configure_ssh_tool(config: dict):
    """Configure SSH tool with settings from YAML.

    Args:
        config: Dictionary with ssh_username, ssh_key_file, timeout
    """
    global SSH_CONFIG

    SSH_CONFIG["username"] = config.get("ssh_username", "admin")
    SSH_CONFIG["ssh_jump_host"] = config.get("ssh_jump_host", None)

    # Expand ~ in key file path
    key_file = config.get("ssh_key_file")
    if key_file:
        SSH_CONFIG["key_file"] = str(Path(key_file).expanduser())

    SSH_CONFIG["timeout"] = config.get("timeout", 30)

    print(f"\n{'='*60}")
    print(f"SSH Tool Configuration:")
    print(f"  - Default username: {SSH_CONFIG['username']}")
    print(f"  - Key file: {SSH_CONFIG['key_file']}")
    print(f"  - Timeout: {SSH_CONFIG['timeout']}s")
    print(f"{'='*60}\n")


class SSHCommandArgs(BaseModel):
    """Arguments for SSH command execution."""

    server: str = Field(description="Server hostname or IP address")
    command: str = Field(description="Command to execute", default="uptime")


@tool(
    name="execute_ssh_command",
    description="Execute a command on a remote server via SSH. Uses configured SSH key and username from settings.yaml.",
    args_schema=SSHCommandArgs,
)
async def execute_ssh_command(
    server: str,
    command: str = "uptime",
) -> dict:
    """Execute SSH command on remote server.

    Args:
        server: Server hostname/IP
        command: Command to execute

    Returns:
        Dict with command output and exit code
    """
    # Use configured defaults
    username = SSH_CONFIG["username"]
    key_file = SSH_CONFIG["key_file"]
    timeout = SSH_CONFIG["timeout"]

    if server == 'jump_server' or server == 'ssh_jump_host' or server == 'ssh_jump_server' \
       or server == 'jump.server' or server == 'jump' or server == 'jump-server':
        server = SSH_CONFIG["ssh_jump_host"]

    print(f"\nSSH Connection Details:")
    print(f"  - Server: {server}")
    print(f"  - Username: {username}")
    print(f"  - Key file: {key_file}")
    print(f"  - Command: {command}")
    print()

    try:
        # Prepare connection options
        connect_kwargs = {
            "username": username,
            "known_hosts": None,  # In production, configure proper known_hosts
            "connect_timeout": timeout,
        }

        # Add client keys if key file is configured
        if key_file and os.path.exists(key_file):
            connect_kwargs["client_keys"] = [key_file]
        else:
            if key_file:
                print(f"WARNING: Key file not found: {key_file}")

        # Connect and execute command
        async with asyncssh.connect(server, **connect_kwargs) as conn:
            result = await conn.run(command, check=False, timeout=timeout)

            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else None

            print(f"✓ SSH command completed (exit code: {result.exit_status})\n")

            return {
                "server": server,
                "command": command,
                "username": username,
                "output": output,
                "error": error,
                "exit_code": result.exit_status,
            }

    except asyncssh.PermissionDenied as e:
        error_msg = f"Permission denied. Check SSH key permissions and username."
        print(f"✗ SSH ERROR: {error_msg}\n")
        return {
            "server": server,
            "command": command,
            "username": username,
            "output": None,
            "error": error_msg,
            "exit_code": -1,
        }

    except asyncssh.Error as e:
        error_msg = f"SSH error: {str(e)}"
        print(f"✗ SSH ERROR: {error_msg}\n")
        return {
            "server": server,
            "command": command,
            "username": username,
            "output": None,
            "error": error_msg,
            "exit_code": -1,
        }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"✗ SSH ERROR: {error_msg}\n")
        return {
            "server": server,
            "command": command,
            "username": username,
            "output": None,
            "error": error_msg,
            "exit_code": -1,
        }
