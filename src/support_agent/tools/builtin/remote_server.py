"""Remote server access tool that handles jump server automatically."""

import json
import asyncssh
from pathlib import Path
from pydantic import BaseModel, Field
from ..base import tool
from .server_ssh import SSH_CONFIG


class RemoteServerCommandArgs(BaseModel):
    """Arguments for remote server command execution."""

    server_name: str = Field(description="Server name")
    command: str = Field(description="Command to execute on the remote server")


@tool(
    name="execute_remote_server_command",
    description="Execute a command on a remote server by name. Automatically looks up the server in servers.json and connects through jump server. Use this instead of execute_ssh_command for servers that are not directly accessible.",
    args_schema=RemoteServerCommandArgs,
)
async def execute_remote_server_command(
    server_name: str,
    command: str,
) -> dict:
    """Execute command on remote server by name (handles jump server automatically).

    Args:
        server_name: Server name from servers.json 
        command: Command to execute on the remote server

    Returns:
        Dict with command output and exit code
    """
    print(f"\nRemote Server Command:")
    print(f"  - Server Name: {server_name}")
    print(f"  - Command: {command}")
    print()

    try:
        # Step 1: Read servers.json from jump server
        print(f"Step 1: Looking up server '{server_name}' in servers.json...")

        # SSH to jump server and read servers.json
        async with asyncssh.connect(
            SSH_CONFIG["ssh_jump_host"],
            username=SSH_CONFIG["username"],
            client_keys=[SSH_CONFIG["key_file"]] if SSH_CONFIG["key_file"] else None,
            known_hosts=None,
        ) as conn:
            result = await conn.run("cat ~/servers.json")
            servers_output = result.stdout

        if result.exit_status != 0:
            error_msg = f"Failed to read servers.json: {result.stderr}"
            print(f"✗ ERROR: {error_msg}\n")
            return {
                "success": False,
                "server_name": server_name,
                "error": error_msg,
                "output": None,
            }

        # Parse servers.json
        try:
            servers_data = json.loads(servers_output)
            cert_path = servers_data.get("cert_path", "/home/ubuntu/certs")
            servers_list = servers_data.get("servers", [])
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse servers.json: {str(e)}"
            print(f"✗ ERROR: {error_msg}\n")
            return {
                "success": False,
                "server_name": server_name,
                "error": error_msg,
                "output": None,
            }

        # Step 2: Find matching server (case-insensitive)
        server_entry = None
        server_name_lower = server_name.lower()

        for server in servers_list:
            if server.get("name", "").lower() == server_name_lower:
                server_entry = server
                break

        if not server_entry:
            # List available servers for error message
            available = [s.get("name") for s in servers_list]
            error_msg = f"Server '{server_name}' not found. Available servers: {', '.join(available)}"
            print(f"✗ ERROR: {error_msg}\n")
            return {
                "success": False,
                "server_name": server_name,
                "error": error_msg,
                "output": None,
                "available_servers": available,
            }

        # Extract SSH command and replace CERT_PATH
        ssh_command = server_entry.get("command", "")
        ssh_command = ssh_command.replace("${CERT_PATH}", cert_path)

        print(f"✓ Found server: {server_entry.get('name')}")
        print(f"  SSH command: {ssh_command}")
        print()

        # Step 3: Execute command on remote server through jump server
        print(f"Step 2: Executing command on {server_name}...")

        full_command = f'{ssh_command} "{command}"'

        # SSH to jump server and execute command on remote server
        async with asyncssh.connect(
            SSH_CONFIG["ssh_jump_host"],
            username=SSH_CONFIG["username"],
            client_keys=[SSH_CONFIG["key_file"]] if SSH_CONFIG["key_file"] else None,
            known_hosts=None,
        ) as conn:
            remote_result = await conn.run(full_command, check=False)

        if remote_result.exit_status == 0:
            print(f"✓ Command executed successfully\n")
            return {
                "success": True,
                "server_name": server_name,
                "output": remote_result.stdout.strip() if remote_result.stdout else "",
                "error": remote_result.stderr.strip() if remote_result.stderr else None,
                "exit_code": remote_result.exit_status,
            }
        else:
            print(f"✗ Command failed with exit code {remote_result.exit_status}\n")
            return {
                "success": False,
                "server_name": server_name,
                "output": remote_result.stdout.strip() if remote_result.stdout else "",
                "error": remote_result.stderr.strip() if remote_result.stderr else "Command execution failed",
                "exit_code": remote_result.exit_status,
            }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"✗ ERROR: {error_msg}\n")
        return {
            "success": False,
            "server_name": server_name,
            "error": error_msg,
            "output": None,
        }
