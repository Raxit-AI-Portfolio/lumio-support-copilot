"""Write tools: create a ticket, add a comment. The tenant and author always come from the identity."""

import sqlite3
from datetime import datetime, timezone

from mvp_common.tools.scope import ToolError, get_visible_ticket, require_role

PRIORITIES = ["P1", "P2", "P3", "P4"]


def utc_text(now: datetime | None = None) -> str:
    """Return the time as an ISO string in UTC."""
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def pick_requester(conn: sqlite3.Connection, identity: dict, customer_id: str) -> tuple[str, str]:
    """Return (tenant_id, requester_id) for a new ticket (BR-TKT-05)."""
    if identity["role"] == "customer":
        return identity["tenant_id"], identity["user_id"]
    row = conn.execute("SELECT tenant_id FROM users WHERE user_id = ? AND role = 'customer'", [customer_id]).fetchone()
    if row is None or row["tenant_id"] not in identity["assigned_tenants"]:
        raise ToolError("customer not found")
    return row["tenant_id"], customer_id


def create_ticket(
    conn: sqlite3.Connection,
    identity: dict,
    summary: str,
    category: str,
    priority: str = "P3",
    customer_id: str = "",
    now: datetime | None = None,
) -> dict:
    """Create a ticket for the caller, or for a customer in an assigned tenant if the caller is staff."""
    if priority not in PRIORITIES:
        raise ToolError("priority must be P1, P2, P3 or P4")
    tenant_id, requester_id = pick_requester(conn, identity, customer_id)
    numbers = [int(row["ticket_id"][2:]) for row in conn.execute("SELECT ticket_id FROM tickets")]
    ticket_id = f"T-{max(numbers) + 1}"
    stamp = utc_text(now)
    conn.execute(
        "INSERT INTO tickets (ticket_id, tenant_id, requester_id, category, priority, status, summary, created_at, "
        "updated_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
        [ticket_id, tenant_id, requester_id, category, priority, summary, stamp, stamp],
    )
    conn.commit()
    return {"ticket_id": ticket_id, "status": "open"}


def add_comment(
    conn: sqlite3.Connection,
    identity: dict,
    ticket_id: str,
    body: str,
    internal: bool = False,
    now: datetime | None = None,
) -> dict:
    """Add a public comment, or an internal note if the caller is staff (BR-TKT-04)."""
    ticket = get_visible_ticket(conn, identity, ticket_id)
    if internal:
        require_role(identity, ["agent", "lead"])
    numbers = [int(row["message_id"][2:]) for row in conn.execute("SELECT message_id FROM ticket_messages")]
    message_id = f"m-{max(numbers) + 1:04d}"
    visibility = "internal" if internal else "public"
    conn.execute(
        "INSERT INTO ticket_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            message_id,
            ticket_id,
            ticket["tenant_id"],
            identity["user_id"],
            identity["role"],
            visibility,
            body,
            utc_text(now),
        ],
    )
    conn.commit()
    return {"message_id": message_id}
