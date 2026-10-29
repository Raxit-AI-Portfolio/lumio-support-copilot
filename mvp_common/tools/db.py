"""SQLite store for tickets, orders and approvals, filled from the seed JSON files."""

import json
import sqlite3
from pathlib import Path

from mvp_common.core.config import DB_FILE, SEED_DIR, get_setting

SCHEMA = """
CREATE TABLE tenants (tenant_id TEXT, name TEXT, plan_tier TEXT, sla_hours INTEGER);
CREATE TABLE users (user_id TEXT, tenant_id TEXT, role TEXT, access_group TEXT, assigned_tenants TEXT);
CREATE TABLE tickets (ticket_id TEXT, tenant_id TEXT, requester_id TEXT, assignee_id TEXT, category TEXT,
  priority TEXT, status TEXT, summary TEXT, sla_due TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE ticket_messages (message_id TEXT, ticket_id TEXT, tenant_id TEXT, author_id TEXT, author_role TEXT,
  visibility TEXT, body TEXT, created_at TEXT);
CREATE TABLE orders (order_id TEXT, tenant_id TEXT, amount REAL, status TEXT, refundable_until TEXT);
CREATE TABLE approvals (approval_id TEXT, tenant_id TEXT, ticket_id TEXT, order_id TEXT, action TEXT, amount REAL,
  reason TEXT, action_hash TEXT, requested_by TEXT, decided_by TEXT, status TEXT, created_at TEXT,
  expires_at TEXT, decided_at TEXT);
CREATE TABLE credits (credit_id TEXT, tenant_id TEXT, order_id TEXT, amount REAL, approval_id TEXT, created_at TEXT);
"""

SEED_FILES = ["tenants", "users", "tickets", "ticket_messages", "orders"]


def connect(path: str = "") -> sqlite3.Connection:
    """Open the database. Default is mvp_common/data/lumio.db, or the file in LUMIO_DB. Use ":memory:" in tests."""
    conn = sqlite3.connect(path or get_setting("LUMIO_DB", str(DB_FILE)))
    conn.row_factory = sqlite3.Row
    return conn


def load_seed(conn: sqlite3.Connection) -> None:
    """Create all tables and fill them from mvp_common/data/seed."""
    conn.executescript(SCHEMA)
    for name in SEED_FILES:
        rows = json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for row in rows:
            if "assigned_tenants" in row:
                row["assigned_tenants"] = json.dumps(row["assigned_tenants"])
            marks = ",".join("?" for _ in row)
            conn.execute(f"INSERT INTO {name} ({','.join(row)}) VALUES ({marks})", list(row.values()))
    conn.commit()


def ensure_database() -> None:
    """Seed the database file if it does not exist yet (a fresh container starts without one)."""
    if Path(get_setting("LUMIO_DB", str(DB_FILE))).exists():
        return
    conn = connect()
    load_seed(conn)
    conn.close()


def reset_db() -> None:
    """Delete the database file and rebuild it from the seed."""
    DB_FILE.unlink(missing_ok=True)
    conn = connect()
    load_seed(conn)
    conn.close()
    print(f"seeded {DB_FILE.name}")


if __name__ == "__main__":
    reset_db()
