"""System status tool."""

import platform
import psutil
from datetime import datetime
from pydantic import BaseModel
from ..base import tool


class SystemStatusArgs(BaseModel):
    """Arguments for system status tool."""
    pass  # No arguments needed


@tool(
    name="get_system_status",
    description="Get current system status including CPU, memory, and disk usage",
    args_schema=SystemStatusArgs,
)
def get_system_status() -> dict:
    """Get system status information.

    Returns:
        Dict with system metrics
    """
    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "uptime": str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())),
    }
