"""Read tools. Every query is scoped by the caller's identity, never by a model argument."""

import sqlite3
from datetime import datetime, timezone

from mvp_common.tools.scope import get_visible_ticket, require_role, ticket_filter

MAX_ROWS = 20


def get_ticket(conn: sqlite3.Connection, identity: dict, ticket_id: str) -> dict:
    """Return a ticket with its messages. Customers do not see internal notes (BR-TKT-04)."""
    ticket = get_visible_ticket(conn, identity, ticket_id)
    sql = "SELECT author_id, author_role, visibility, body, created_at FROM ticket_messages WHERE ticket_id = ?"
    if identity["role"] == "customer":
        sql += " AND visibility = 'public'"
    rows = conn.execute(sql + " ORDER BY created_at", [ticket_id]).fetchall()
    ticket["messages"] = [dict(row) for row in rows]
    return ticket


def list_tickets(conn: sqlite3.Connection, identity: dict, status: str = "") -> list[dict]:
    """List the caller's visible tickets, newest first, at most 20. Optional status filter."""
    where, params = ticket_filter(identity)
    sql = f"SELECT ticket_id, tenant_id, priority, status, summary, sla_due FROM tickets WHERE {where}"
    if status:
        sql += " AND status = ?"
        params.append(status)
    rows = conn.execute(sql + f" ORDER BY created_at DESC LIMIT {MAX_ROWS}", params).fetchall()
    return [dict(row) for row in rows]


def queue_summary(conn: sqlite3.Connection, identity: dict, now: datetime | None = None) -> dict:
    """Lead only (BR-ANL-01): ticket counts per status and open tickets past their SLA, in assigned tenants."""
    require_role(identity, ["lead"])
    now_text = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    where, params = ticket_filter(identity)
    counts = conn.execute(f"SELECT status, COUNT(*) AS n FROM tickets WHERE {where} GROUP BY status", params)
    breached = conn.execute(
        f"SELECT ticket_id FROM tickets WHERE {where} AND status IN ('open', 'pending_customer') AND sla_due < ? "
        f"ORDER BY sla_due LIMIT {MAX_ROWS}",
        params + [now_text],
    )
    return {
        "by_status": {row["status"]: row["n"] for row in counts},
        "sla_breached": [row["ticket_id"] for row in breached],
    }
