"""Database query tool with SSH tunnel support."""

import asyncio
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import asyncssh
import aiomysql
from ..base import tool


# Global configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "username": "root",
    "password": "",
    "connection_timeout": 30,
    "max_rows": 100,
    "use_ssh_tunnel": False,
    "ssh_jump_host": None,
    "ssh_username": None,
    "ssh_key_file": None,
}


def configure_database_tool(config: dict):
    """Configure database tool with settings from YAML.

    Args:
        config: Dictionary with database configuration
    """
    global DB_CONFIG

    DB_CONFIG["host"] = config.get("host", "localhost")
    DB_CONFIG["port"] = config.get("port", 3306)
    DB_CONFIG["username"] = config.get("username", "root")
    DB_CONFIG["password"] = config.get("password", "")
    DB_CONFIG["connection_timeout"] = config.get("connection_timeout", 30)
    DB_CONFIG["max_rows"] = config.get("max_rows", 100)

    # SSH tunnel configuration
    DB_CONFIG["use_ssh_tunnel"] = config.get("use_ssh_tunnel", False)
    DB_CONFIG["ssh_jump_host"] = config.get("ssh_jump_host")
    DB_CONFIG["ssh_username"] = config.get("ssh_username", "ubuntu")

    # Expand ~ in SSH key file path
    ssh_key = config.get("ssh_key_file")
    if ssh_key:
        DB_CONFIG["ssh_key_file"] = str(Path(ssh_key).expanduser())

    print(f"\n{'='*60}")
    print(f"Database Tool Configuration:")
    print(f"  - Database Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  - Username: {DB_CONFIG['username']}")
    print(f"  - Max Rows: {DB_CONFIG['max_rows']}")
    print(f"  - Connection Timeout: {DB_CONFIG['connection_timeout']}s")
    if DB_CONFIG["use_ssh_tunnel"]:
        print(f"  - SSH Tunnel: {DB_CONFIG['ssh_jump_host']} (as {DB_CONFIG['ssh_username']})")
        print(f"  - SSH Key: {DB_CONFIG['ssh_key_file']}")
    print(f"{'='*60}\n")


class DatabaseQueryArgs(BaseModel):
    """Arguments for database query execution."""

    database: str = Field(description="Database name to query")
    query: str = Field(description="SQL SELECT query to execute")


@tool(
    name="execute_database_query",
    description="Execute a SELECT query on MySQL database. Only SELECT queries are allowed. Access via SSH tunnel through management server.",
    args_schema=DatabaseQueryArgs,
)
async def execute_database_query(
    database: str,
    query: str,
) -> dict:
    """Execute SQL query on MySQL database.

    Args:
        database: Database name to connect to
        query: SQL SELECT query to execute

    Returns:
        Dict with query results or error
    """
    # Use configured settings
    host = DB_CONFIG["host"]
    port = DB_CONFIG["port"]
    username = DB_CONFIG["username"]
    password = DB_CONFIG["password"]
    timeout = DB_CONFIG["connection_timeout"]
    max_rows = DB_CONFIG["max_rows"]
    use_tunnel = DB_CONFIG["use_ssh_tunnel"]

    print(f"\nDatabase Query Details:")
    print(f"  - Database: {database}")
    print(f"  - Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"  - Max Rows: {max_rows}")
    print()

    # Security check: Only allow SELECT queries
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT") and not query_upper.startswith("DESCRIBE") and not query_upper.startswith("SHOW TABLES"):
        error_msg = "Only SELECT, DESCRIBE, and SHOW TABLES queries are allowed for security reasons"
        print(f"✗ REJECTED: {error_msg}\n")
        return {
            "success": False,
            "error": error_msg,
            "rows": [],
            "row_count": 0,
        }

    # Check for dangerous keywords
    dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER", "TRUNCATE", "REPLACE"]
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            error_msg = f"Query contains forbidden keyword: {keyword}"
            print(f"✗ REJECTED: {error_msg}\n")
            return {
                "success": False,
                "error": error_msg,
                "rows": [],
                "row_count": 0,
            }

    ssh_conn = None
    tunnel_port = None

    try:
        # Setup SSH tunnel if configured
        if use_tunnel:
            print(f"Setting up SSH tunnel to {host} via {DB_CONFIG['ssh_jump_host']}...")

            # Connect to jump host
            ssh_conn = await asyncssh.connect(
                DB_CONFIG["ssh_jump_host"],
                username=DB_CONFIG["ssh_username"],
                client_keys=[DB_CONFIG["ssh_key_file"]] if DB_CONFIG["ssh_key_file"] else None,
                known_hosts=None,
            )

            # Create tunnel: local random port -> db.server:3306
            tunnel_port = 13306  # Use a fixed local port for simplicity
            listener = await ssh_conn.forward_local_port(
                '127.0.0.1', tunnel_port,  # Local endpoint
                host, port  # Remote endpoint (db.server:3306)
            )

            print(f"✓ SSH tunnel established: localhost:{tunnel_port} -> {host}:{port}")

            # Connect through tunnel
            connection_host = '127.0.0.1'
            connection_port = tunnel_port
        else:
            # Direct connection
            connection_host = host
            connection_port = port

        # Connect to MySQL
        print(f"Connecting to MySQL at {connection_host}:{connection_port}...")

        conn = await aiomysql.connect(
            host=connection_host,
            port=connection_port,
            user=username,
            password=password,
            db=database,
            connect_timeout=timeout,
        )

        try:
            # Execute query
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query)

                # Fetch results with limit
                rows = await cursor.fetchmany(max_rows + 1)

                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]

                # Convert to list of dicts (aiomysql DictCursor already does this)
                results = [dict(row) for row in rows]

                print(f"✓ Query executed successfully")
                print(f"  - Returned {len(results)} rows{' (truncated)' if truncated else ''}\n")

                return {
                    "success": True,
                    "database": database,
                    "rows": results,
                    "row_count": len(results),
                    "truncated": truncated,
                    "max_rows": max_rows,
                }

        finally:
            conn.close()

    except aiomysql.Error as e:
        error_msg = f"MySQL error: {str(e)}"
        print(f"✗ DATABASE ERROR: {error_msg}\n")
        return {
            "success": False,
            "database": database,
            "error": error_msg,
            "rows": [],
            "row_count": 0,
        }

    except asyncssh.Error as e:
        error_msg = f"SSH tunnel error: {str(e)}"
        print(f"✗ SSH ERROR: {error_msg}\n")
        return {
            "success": False,
            "database": database,
            "error": error_msg,
            "rows": [],
            "row_count": 0,
        }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"✗ ERROR: {error_msg}\n")
        return {
            "success": False,
            "database": database,
            "error": error_msg,
            "rows": [],
            "row_count": 0,
        }

    finally:
        # Cleanup SSH tunnel
        if ssh_conn:
            ssh_conn.close()
            await ssh_conn.wait_closed()
            print(f"✓ SSH tunnel closed\n")
