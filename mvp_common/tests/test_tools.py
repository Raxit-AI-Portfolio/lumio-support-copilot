from datetime import date, datetime, timedelta, timezone

import pytest

from mvp_common.core.identity import identity_from_token
from mvp_common.tools.approvals import approve_action, propose_action
from mvp_common.tools.db import connect, ensure_database, load_seed
from mvp_common.tools.read_tools import get_ticket, queue_summary
from mvp_common.tools.scope import ToolError
from mvp_common.tools.write_tools import add_comment, create_ticket

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 25)
ACME_TICKET = "T-150"
ACME_ORDER = "O-5006"


@pytest.fixture
def conn():
    connection = connect(":memory:")
    load_seed(connection)
    return connection


def who(conn, token):
    return identity_from_token(conn, token)


def propose_refund(conn, amount=100.0):
    agent = who(conn, "token-agent")
    return propose_action(conn, agent, ACME_TICKET, "refund", ACME_ORDER, amount, "double charge", NOW, TODAY)


def test_customer_cannot_read_a_ticket_of_another_tenant_and_error_matches_missing(conn):
    customer = who(conn, "token-customer")
    other = conn.execute("SELECT ticket_id FROM tickets WHERE tenant_id != 't-acme'").fetchone()["ticket_id"]
    with pytest.raises(ToolError, match="ticket not found"):
        get_ticket(conn, customer, other)
    with pytest.raises(ToolError, match="ticket not found"):
        get_ticket(conn, customer, "T-99999")


def test_internal_note_is_hidden_from_customer_but_not_from_staff(conn):
    add_comment(conn, who(conn, "token-agent"), ACME_TICKET, "secret note", internal=True, now=NOW)
    seen_by_customer = get_ticket(conn, who(conn, "token-customer"), ACME_TICKET)["messages"]
    seen_by_agent = get_ticket(conn, who(conn, "token-agent"), ACME_TICKET)["messages"]
    assert "secret note" not in [m["body"] for m in seen_by_customer]
    assert "secret note" in [m["body"] for m in seen_by_agent]
    with pytest.raises(ToolError, match="not allowed"):
        add_comment(conn, who(conn, "token-customer"), ACME_TICKET, "x", internal=True)


def test_analytics_are_for_leads_only(conn):
    with pytest.raises(ToolError, match="not allowed"):
        queue_summary(conn, who(conn, "token-agent"), NOW)
    assert queue_summary(conn, who(conn, "token-lead"), NOW)["by_status"]


def test_ticket_is_created_in_the_callers_tenant_and_staff_stay_in_assigned_tenants(conn):
    created = create_ticket(conn, who(conn, "token-customer"), "Login fails", "access", now=NOW)
    row = conn.execute("SELECT tenant_id, requester_id FROM tickets WHERE ticket_id = ?", [created["ticket_id"]])
    assert tuple(row.fetchone()) == ("t-acme", "u-acme-01")
    with pytest.raises(ToolError, match="customer not found"):
        create_ticket(conn, who(conn, "token-agent"), "x", "access", customer_id="u-delta-01", now=NOW)


def test_refund_rules_amount_cap_and_one_pending_per_order(conn):
    agent = who(conn, "token-agent")
    with pytest.raises(ToolError, match="above the order amount"):
        propose_action(conn, agent, ACME_TICKET, "refund", ACME_ORDER, 9999.0, "x", NOW, TODAY)
    propose_refund(conn)
    with pytest.raises(ToolError, match="pending approval already exists"):
        propose_refund(conn)


def test_proposer_cannot_approve_and_second_lead_approves_exactly_once(conn):
    lead = who(conn, "token-lead")
    proposal = propose_action(conn, lead, ACME_TICKET, "refund", ACME_ORDER, 100.0, "double charge", NOW, TODAY)
    with pytest.raises(ToolError, match="own proposal"):
        approve_action(conn, lead, proposal["approval_id"], proposal["action_hash"], NOW, TODAY)
    second_lead = who(conn, "token-lead2")
    done = approve_action(conn, second_lead, proposal["approval_id"], proposal["action_hash"], NOW, TODAY)
    assert done["status"] == "executed"
    assert conn.execute("SELECT status FROM orders WHERE order_id = ?", [ACME_ORDER]).fetchone()[0] == "refunded"
    with pytest.raises(ToolError, match="already executed"):
        approve_action(conn, second_lead, proposal["approval_id"], proposal["action_hash"], NOW, TODAY)


def test_whole_number_amount_from_the_model_still_matches_its_hash(conn):
    proposal = propose_action(conn, who(conn, "token-agent"), ACME_TICKET, "refund", ACME_ORDER, 100, "x", NOW, TODAY)
    done = approve_action(conn, who(conn, "token-lead"), proposal["approval_id"], proposal["action_hash"], NOW, TODAY)
    assert done["status"] == "executed"


def test_wrong_hash_and_expired_approval_are_refused(conn):
    proposal = propose_refund(conn)
    lead = who(conn, "token-lead")
    with pytest.raises(ToolError, match="hash does not match"):
        approve_action(conn, lead, proposal["approval_id"], "0" * 64, NOW, TODAY)
    late = NOW + timedelta(hours=25)
    with pytest.raises(ToolError, match="expired"):
        approve_action(conn, lead, proposal["approval_id"], proposal["action_hash"], late, TODAY)


def test_ensure_database_seeds_a_missing_file_once(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    monkeypatch.setenv("LUMIO_DB", str(path))
    ensure_database()
    first = path.stat().st_mtime_ns
    ensure_database()
    assert path.stat().st_mtime_ns == first
    assert connect().execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 60
