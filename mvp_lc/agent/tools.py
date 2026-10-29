"""Tools the agents can call. Each one reads the identity from the run config, never from a model argument.

The `config: RunnableConfig` parameter is injected by LangChain and is not part of the schema the model sees.
"""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from mvp_common.data.search import KB_MIN_SCORE, search_kb
from mvp_common.tools import approvals, read_tools, write_tools
from mvp_common.tools.db import connect
from mvp_common.tools.scope import ToolError

HIT_TEXT_LIMIT = 700


def run_db(config: RunnableConfig, call) -> dict:
    """Open the database, run call(conn, identity) and turn a ToolError into an error result."""
    conn = connect()
    try:
        return call(conn, config["configurable"]["identity"])
    except ToolError as error:
        return {"error": str(error)}
    finally:
        conn.close()


@tool
def kb_search(query: str, config: RunnableConfig) -> dict:
    """Search the help articles. Returns hits with chunk_id, title and text, best first."""
    role = config["configurable"]["identity"]["role"]
    hits = [hit for hit in search_kb(query, role, top_k=4) if hit["score"] >= KB_MIN_SCORE]
    config["configurable"]["turn"]["retrieved"].extend(hit["chunk_id"] for hit in hits)
    if not hits:
        return {"hits": [], "note": "nothing relevant found"}
    return {
        "hits": [{"chunk_id": h["chunk_id"], "title": h["title"], "text": h["text"][:HIT_TEXT_LIMIT]} for h in hits]
    }


@tool
def get_ticket(ticket_id: str, config: RunnableConfig) -> dict:
    """Return one ticket with its messages."""
    return run_db(config, lambda conn, who: read_tools.get_ticket(conn, who, ticket_id))


@tool
def list_tickets(status: str, config: RunnableConfig) -> dict:
    """List the caller's tickets. Pass an empty status for all, or open, pending_customer, resolved, closed."""
    return run_db(config, lambda conn, who: {"tickets": read_tools.list_tickets(conn, who, status)})


@tool
def queue_summary(config: RunnableConfig) -> dict:
    """Lead only: ticket counts per status and the open tickets past their SLA."""
    return run_db(config, read_tools.queue_summary)


@tool
def create_ticket(summary: str, category: str, priority: str, config: RunnableConfig) -> dict:
    """Create a ticket for the caller. Priority is P1 (most urgent) to P4."""
    return run_db(config, lambda conn, who: write_tools.create_ticket(conn, who, summary, category, priority))


@tool
def add_comment(ticket_id: str, body: str, internal: bool, config: RunnableConfig) -> dict:
    """Add a comment to a ticket. internal=True makes a staff-only note."""
    return run_db(config, lambda conn, who: write_tools.add_comment(conn, who, ticket_id, body, internal))


@tool
def propose_action(
    ticket_id: str, action: str, order_id: str, amount: float, reason: str, config: RunnableConfig
) -> dict:
    """Staff only: propose a refund or credit. A lead must approve it. Nothing is executed here."""
    return run_db(
        config, lambda conn, who: approvals.propose_action(conn, who, ticket_id, action, order_id, amount, reason)
    )


ALL_TOOLS = [kb_search, get_ticket, list_tickets, queue_summary, create_ticket, add_comment, propose_action]
