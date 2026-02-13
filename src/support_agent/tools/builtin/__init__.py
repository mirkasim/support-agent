"""Built-in tools for server and system operations."""

from .system_status import get_system_status
from .server_ssh import execute_ssh_command, configure_ssh_tool
from .database import execute_database_query, configure_database_tool
from .remote_server import execute_remote_server_command

__all__ = [
    "get_system_status",
    "execute_ssh_command",
    "configure_ssh_tool",
    "execute_database_query",
    "configure_database_tool",
    "execute_remote_server_command",
]


def register_builtin_tools(registry, settings=None):
    """Register all built-in tools.

    Args:
        registry: ToolRegistry instance
        settings: Settings instance (optional, for configuration)
    """
    from .system_status import get_system_status
    from .server_ssh import execute_ssh_command
    from .database import execute_database_query
    from .remote_server import execute_remote_server_command

    # Configure tools if settings provided
    if settings:
        yaml_config = settings.load_yaml_config()

        # Configure SSH tool
        ssh_config = yaml_config.get("tools", {}).get("server_ssh", {})
        if ssh_config.get("enabled", True):
            configure_ssh_tool(ssh_config)

        # Configure Database tool
        db_config = yaml_config.get("tools", {}).get("database", {})
        if db_config.get("enabled", True):
            configure_database_tool(db_config)

    registry.register(get_system_status)
    registry.register(execute_ssh_command)
    registry.register(execute_database_query)
    registry.register(execute_remote_server_command)

    print(f"Registered {len(registry)} built-in tools")
