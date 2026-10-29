"""Dummy sign-in: fixed tokens map to seed users. Stands in for the real IdP (see MVP.md)."""

import json
import sqlite3

TOKENS = {
    "token-customer": "u-acme-01",
    "token-agent": "u-agent-01",
    "token-lead": "u-lead-01",
    "token-lead2": "u-lead-06",
}


def identity_from_user_id(conn: sqlite3.Connection, user_id: str) -> dict:
    """Return the identity dict for a seed user, or raise PermissionError."""
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", [user_id]).fetchone()
    if row is None:
        raise PermissionError("unknown user")
    identity = dict(row)
    identity["assigned_tenants"] = json.loads(identity["assigned_tenants"])
    return identity


def identity_from_token(conn: sqlite3.Connection, token: str) -> dict:
    """Return the identity dict for a token, or raise PermissionError."""
    user_id = TOKENS.get(token)
    if user_id is None:
        raise PermissionError("invalid token")
    return identity_from_user_id(conn, user_id)
