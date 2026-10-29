"""Role checks and the one place that builds the ticket scope filter (BR-AUT-03, BR-TKT-01, BR-TKT-02)."""

import sqlite3


class ToolError(Exception):
    """A tool refused or failed. The message is safe to show the user."""


def require_role(identity: dict, allowed: list[str]) -> None:
    """Raise ToolError unless the caller has one of the allowed roles."""
    if identity["role"] not in allowed:
        raise ToolError("not allowed")


def ticket_filter(identity: dict) -> tuple[str, list]:
    """Return (sql, params) that limit tickets to what the caller may see. Tenant comes from the identity only."""
    if identity["role"] == "customer":
        return "tenant_id = ? AND requester_id = ?", [identity["tenant_id"], identity["user_id"]]
    tenants = identity["assigned_tenants"]
    marks = ",".join("?" for _ in tenants)
    return f"tenant_id IN ({marks})", list(tenants)


def get_visible_ticket(conn: sqlite3.Connection, identity: dict, ticket_id: str) -> dict:
    """Return one ticket the caller may see. Hidden and missing tickets give the same error."""
    where, params = ticket_filter(identity)
    row = conn.execute(f"SELECT * FROM tickets WHERE ticket_id = ? AND {where}", [ticket_id] + params).fetchone()
    if row is None:
        raise ToolError("ticket not found")
    return dict(row)
