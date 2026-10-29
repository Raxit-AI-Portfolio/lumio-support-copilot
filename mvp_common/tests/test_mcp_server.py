import pytest

pytest.importorskip("fastmcp")  # the LangGraph venv has no fastmcp: its mcp version conflicts with the adapters

from mvp_common.tools import mcp_server  # noqa: E402
from mvp_common.tools.db import connect, load_seed  # noqa: E402
from mvp_common.tools.scope import ToolError  # noqa: E402


@pytest.fixture
def conn():
    connection = connect(":memory:")
    load_seed(connection)
    return connection


def send_headers(monkeypatch, headers):
    monkeypatch.setattr(mcp_server, "get_http_headers", lambda: headers)


def test_mcp_server_takes_identity_from_trusted_headers_only(conn, monkeypatch):
    send_headers(monkeypatch, {"x-service-secret": "demo-secret", "x-lumio-user": "u-lead-01"})
    assert mcp_server.caller_identity(conn)["role"] == "lead"
    for bad in [
        {"x-service-secret": "wrong", "x-lumio-user": "u-lead-01"},
        {"x-service-secret": "demo-secret", "x-lumio-user": "u-nobody"},
        {},
    ]:
        send_headers(monkeypatch, bad)
        with pytest.raises(ToolError, match="not allowed"):
            mcp_server.caller_identity(conn)
