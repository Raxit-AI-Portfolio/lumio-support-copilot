"""Connect the ticket agent to the MCP read-tools server (used when MCP_URL is set)."""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_config

from mvp_common.core.config import get_setting
from mvp_lc.agent.tools import ALL_TOOLS

MCP_TOOLS = ["get_ticket", "list_tickets", "queue_summary"]
POOL = []


async def add_user_headers(request, handler):
    """Interceptor: add the service secret and the user id from the verified identity to each MCP call."""
    identity = get_config()["configurable"]["identity"]
    headers = {
        "x-service-secret": get_setting("MCP_SHARED_SECRET", "demo-secret"),
        "x-lumio-user": identity["user_id"],
    }
    return await handler(request.override(headers=headers))


async def load_mcp_tools(url: str) -> list:
    """The three read tools, served over MCP. The user id is added per call, so one set serves every user."""
    connection = {"transport": "streamable_http", "url": url, "timeout": 10}
    client = MultiServerMCPClient({"lumio": connection}, tool_interceptors=[add_user_headers])
    return [one for one in await client.get_tools() if one.name in MCP_TOOLS]


async def tool_pool() -> list:
    """All tools. The ticket read tools come from the MCP server if MCP_URL is set, otherwise they are local."""
    url = get_setting("MCP_URL")
    if not url:
        return ALL_TOOLS
    if not POOL:
        POOL.extend([one for one in ALL_TOOLS if one.name not in MCP_TOOLS] + await load_mcp_tools(url))
    return POOL
