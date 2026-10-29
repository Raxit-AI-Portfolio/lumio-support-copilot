"""Connect the ticket agent to the MCP read-tools server (used when MCP_URL is set)."""

from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from mvp_common.core.config import get_setting


def mcp_headers(context) -> dict:
    """Headers for each MCP call: the service secret and the user id from the verified identity in state."""
    return {
        "x-service-secret": get_setting("MCP_SHARED_SECRET", "demo-secret"),
        "x-lumio-user": context.state["identity"]["user_id"],
    }


def make_mcp_toolset(url: str) -> McpToolset:
    """Return a toolset with get_ticket, list_tickets and queue_summary served over MCP."""
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=url, timeout=10),
        tool_filter=["get_ticket", "list_tickets", "queue_summary"],
        header_provider=mcp_headers,
    )
