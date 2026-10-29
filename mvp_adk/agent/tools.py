"""Tools the agents can call. Each one reads the identity from session state, never from a model argument."""

from google.adk.tools import ToolContext

from mvp_common.data.search import KB_MIN_SCORE, search_kb
from mvp_common.tools import approvals, read_tools, write_tools
from mvp_common.tools.db import connect
from mvp_common.tools.scope import ToolError

HIT_TEXT_LIMIT = 700


def kb_search(query: str, tool_context: ToolContext) -> dict:
    """Search the help articles. Returns hits with chunk_id, title and text, best first."""
    role = tool_context.state["identity"]["role"]
    hits = [hit for hit in search_kb(query, role, top_k=4) if hit["score"] >= KB_MIN_SCORE]
    tool_context.state["temp:last_retrieved_ids"] = [hit["chunk_id"] for hit in hits]
    if not hits:
        return {"hits": [], "note": "nothing relevant found"}
    return {
        "hits": [{"chunk_id": h["chunk_id"], "title": h["title"], "text": h["text"][:HIT_TEXT_LIMIT]} for h in hits]
    }


def get_ticket(ticket_id: str, tool_context: ToolContext) -> dict:
    """Return one ticket with its messages."""
    conn = connect()
    try:
        return read_tools.get_ticket(conn, tool_context.state["identity"], ticket_id)
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def list_tickets(status: str, tool_context: ToolContext) -> dict:
    """List the caller's tickets. Pass an empty status for all, or open, pending_customer, resolved, closed."""
    conn = connect()
    try:
        return {"tickets": read_tools.list_tickets(conn, tool_context.state["identity"], status)}
    finally:
        conn.close()


def queue_summary(tool_context: ToolContext) -> dict:
    """Lead only: ticket counts per status and the open tickets past their SLA."""
    conn = connect()
    try:
        return read_tools.queue_summary(conn, tool_context.state["identity"])
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def create_ticket(summary: str, category: str, priority: str, tool_context: ToolContext) -> dict:
    """Create a ticket for the caller. Priority is P1 (most urgent) to P4."""
    conn = connect()
    try:
        return write_tools.create_ticket(conn, tool_context.state["identity"], summary, category, priority)
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def add_comment(ticket_id: str, body: str, internal: bool, tool_context: ToolContext) -> dict:
    """Add a comment to a ticket. internal=True makes a staff-only note."""
    conn = connect()
    try:
        return write_tools.add_comment(conn, tool_context.state["identity"], ticket_id, body, internal)
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


def propose_action(
    ticket_id: str, action: str, order_id: str, amount: float, reason: str, tool_context: ToolContext
) -> dict:
    """Staff only: propose a refund or credit. A lead must approve it. Nothing is executed here."""
    conn = connect()
    try:
        identity = tool_context.state["identity"]
        return approvals.propose_action(conn, identity, ticket_id, action, order_id, amount, reason)
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()
