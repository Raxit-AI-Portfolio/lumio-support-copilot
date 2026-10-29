"""MCP server for the read tools (HLD 5.3.5). Read-only, named tools, no free SQL.

The caller sends a service secret and a user id. The server looks up that user's role and tenants itself,
so the model can never choose them. Run from the repo root: python -m mvp_common.tools.mcp_server
"""

import hmac

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from mvp_common.core.config import get_setting
from mvp_common.core.identity import identity_from_user_id
from mvp_common.tools import read_tools
from mvp_common.tools.db import connect
from mvp_common.tools.scope import ToolError

mcp = FastMCP("lumio-read-tools")


def caller_identity(conn) -> dict:
    """Return the identity of the calling user, or raise ToolError."""
    headers = get_http_headers()
    secret = get_setting("MCP_SHARED_SECRET", "demo-secret")
    if not hmac.compare_digest(headers.get("x-service-secret", ""), secret):
        raise ToolError("not allowed")
    try:
        return identity_from_user_id(conn, headers.get("x-lumio-user", ""))
    except PermissionError:
        raise ToolError("not allowed")


def get_ticket(ticket_id: str) -> dict:
    """Return one ticket with its messages."""
    conn = connect()
    try:
        return read_tools.get_ticket(conn, caller_identity(conn), ticket_id)
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def list_tickets(status: str = "") -> dict:
    """List the caller's tickets. Pass an empty status for all, or open, pending_customer, resolved, closed."""
    conn = connect()
    try:
        return {"tickets": read_tools.list_tickets(conn, caller_identity(conn), status)}
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def queue_summary() -> dict:
    """Lead only: ticket counts per status and the open tickets past their SLA."""
    conn = connect()
    try:
        return read_tools.queue_summary(conn, caller_identity(conn))
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


mcp.tool(get_ticket)
mcp.tool(list_tickets)
mcp.tool(queue_summary)


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
