"""Propose, approve and reject refunds and credits (BR-RSL-01 to BR-RSL-05, BR-RSL-07)."""

import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

from mvp_common.tools.scope import ToolError, get_visible_ticket, require_role
from mvp_common.tools.write_tools import utc_text

ACTIONS = ["refund", "credit"]
APPROVAL_HOURS = 24


def make_action_hash(action: str, ticket_id: str, order_id: str, amount: float) -> str:
    """Hash the exact action, so the approver confirms what was proposed."""
    fields = {"action": action, "ticket_id": ticket_id, "order_id": order_id, "amount": round(float(amount), 2)}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def refund_problem(order: dict, amount: float, today: date) -> str:
    """Return why a refund is not allowed (BR-RSL-01), or an empty string."""
    if order["status"] != "paid":
        return "order is not paid"
    if order["refundable_until"] < today.isoformat():
        return "refund window has passed"
    if amount > order["amount"]:
        return "amount is above the order amount"
    return ""


def get_order(conn: sqlite3.Connection, tenant_id: str, order_id: str) -> dict:
    """Return an order of the given tenant."""
    row = conn.execute("SELECT * FROM orders WHERE order_id = ? AND tenant_id = ?", [order_id, tenant_id]).fetchone()
    if row is None:
        raise ToolError("order not found")
    return dict(row)


def check_proposal(conn: sqlite3.Connection, ticket: dict, action: str, order_id: str, amount: float, today: date):
    """Raise ToolError if the proposal breaks a rule."""
    if action not in ACTIONS:
        raise ToolError("action must be refund or credit")
    if amount <= 0:
        raise ToolError("amount must be above zero")
    order = get_order(conn, ticket["tenant_id"], order_id)
    if action == "refund":
        problem = refund_problem(order, amount, today)
        if problem:
            raise ToolError(problem)
    pending = conn.execute(
        "SELECT 1 FROM approvals WHERE order_id = ? AND action = ? AND status = 'pending'", [order_id, action]
    ).fetchone()
    if pending:
        raise ToolError("a pending approval already exists for this order and action")


def propose_action(
    conn: sqlite3.Connection,
    identity: dict,
    ticket_id: str,
    action: str,
    order_id: str,
    amount: float,
    reason: str,
    now: datetime | None = None,
    today: date | None = None,
) -> dict:
    """Staff propose a refund or credit. It waits for a lead. Nothing executes here."""
    require_role(identity, ["agent", "lead"])
    ticket = get_visible_ticket(conn, identity, ticket_id)
    now = now or datetime.now(timezone.utc)
    check_proposal(conn, ticket, action, order_id, amount, today or now.date())
    numbers = [int(row["approval_id"][2:]) for row in conn.execute("SELECT approval_id FROM approvals")]
    approval_id = f"A-{max(numbers + [0]) + 1}"
    action_hash = make_action_hash(action, ticket_id, order_id, amount)
    expires_at = utc_text(now + timedelta(hours=APPROVAL_HOURS))
    conn.execute(
        "INSERT INTO approvals (approval_id, tenant_id, ticket_id, order_id, action, amount, reason, action_hash, "
        "requested_by, status, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
        [
            approval_id,
            ticket["tenant_id"],
            ticket_id,
            order_id,
            action,
            amount,
            reason,
            action_hash,
            identity["user_id"],
            utc_text(now),
            expires_at,
        ],
    )
    conn.commit()
    return {"approval_id": approval_id, "action_hash": action_hash, "status": "pending"}


def load_pending(conn: sqlite3.Connection, identity: dict, approval_id: str) -> dict:
    """Return a pending approval in the lead's assigned tenants."""
    row = conn.execute("SELECT * FROM approvals WHERE approval_id = ?", [approval_id]).fetchone()
    if row is None or row["tenant_id"] not in identity["assigned_tenants"]:
        raise ToolError("approval not found")
    if row["status"] != "pending":
        raise ToolError(f"approval is already {row['status']}")
    return dict(row)


def set_status(conn: sqlite3.Connection, approval_id: str, status: str, user_id: str, now: datetime) -> None:
    """Close a pending approval. Only a pending row can change, so a retry cannot run twice (BR-RSL-05)."""
    cursor = conn.execute(
        "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ? WHERE approval_id = ? AND status = 'pending'",
        [status, user_id, utc_text(now), approval_id],
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise ToolError("approval is already decided")


def check_can_decide(conn: sqlite3.Connection, identity: dict, approval: dict, now: datetime) -> None:
    """Raise ToolError if this lead may not decide now (BR-RSL-03, BR-RSL-04)."""
    if approval["requested_by"] == identity["user_id"]:
        raise ToolError("you cannot decide your own proposal")
    if utc_text(now) > approval["expires_at"]:
        set_status(conn, approval["approval_id"], "expired", identity["user_id"], now)
        raise ToolError("approval has expired")


def execute_action(conn: sqlite3.Connection, approval: dict, now: datetime, today: date) -> str:
    """Do the approved action. Returns "executed" or "failed" (BR-RSL-07 re-check)."""
    order = get_order(conn, approval["tenant_id"], approval["order_id"])
    if approval["action"] == "refund":
        if refund_problem(order, approval["amount"], today):
            return "failed"
        conn.execute("UPDATE orders SET status = 'refunded' WHERE order_id = ?", [order["order_id"]])
        return "executed"
    credit = [f"C-{approval['approval_id']}", approval["tenant_id"], order["order_id"], approval["amount"]]
    conn.execute("INSERT INTO credits VALUES (?, ?, ?, ?, ?, ?)", credit + [approval["approval_id"], utc_text(now)])
    return "executed"


def approve_action(
    conn: sqlite3.Connection,
    identity: dict,
    approval_id: str,
    action_hash: str,
    now: datetime | None = None,
    today: date | None = None,
) -> dict:
    """A lead (not the proposer) approves the exact action by its hash. The action runs once."""
    require_role(identity, ["lead"])
    now = now or datetime.now(timezone.utc)
    approval = load_pending(conn, identity, approval_id)
    check_can_decide(conn, identity, approval, now)
    stored = make_action_hash(approval["action"], approval["ticket_id"], approval["order_id"], approval["amount"])
    if not (action_hash == approval["action_hash"] == stored):
        raise ToolError("action hash does not match")
    status = execute_action(conn, approval, now, today or now.date())
    set_status(conn, approval_id, status, identity["user_id"], now)
    return {"approval_id": approval_id, "status": status}


def reject_action(conn: sqlite3.Connection, identity: dict, approval_id: str, now: datetime | None = None) -> dict:
    """A lead (not the proposer) rejects a pending action."""
    require_role(identity, ["lead"])
    now = now or datetime.now(timezone.utc)
    approval = load_pending(conn, identity, approval_id)
    check_can_decide(conn, identity, approval, now)
    set_status(conn, approval_id, "rejected", identity["user_id"], now)
    return {"approval_id": approval_id, "status": "rejected"}


def list_approvals(conn: sqlite3.Connection, identity: dict) -> list[dict]:
    """A lead lists pending approvals in assigned tenants, oldest first, at most 20."""
    require_role(identity, ["lead"])
    marks = ",".join("?" for _ in identity["assigned_tenants"])
    rows = conn.execute(
        "SELECT approval_id, tenant_id, ticket_id, order_id, action, amount, reason, action_hash, requested_by, "
        f"expires_at FROM approvals WHERE status = 'pending' AND tenant_id IN ({marks}) ORDER BY created_at LIMIT 20",
        list(identity["assigned_tenants"]),
    )
    return [dict(row) for row in rows]
