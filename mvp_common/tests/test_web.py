import pytest
from fastapi.testclient import TestClient

from mvp_common.core.identity import identity_from_token
from mvp_common.tools import db
from mvp_common.tools.approvals import propose_action
from mvp_common.web.gateway import create_app


async def fake_turn(identity, message, conversation_id=""):
    yield "answer", f"echo {identity['user_id']} {conversation_id}"
    yield "usage", {"input_tokens": 1}


client = TestClient(create_app("test", fake_turn))


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_FILE", path)
    monkeypatch.setattr("mvp_common.web.gateway.connect", lambda: db.connect(path))
    conn = db.connect(path)
    db.load_seed(conn)
    conn.close()
    return path


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def propose_as_agent(path):
    conn = db.connect(path)
    agent = identity_from_token(conn, "token-agent")
    result = propose_action(conn, agent, "T-150", "refund", "O-5006", 100.0, "double charge")
    conn.close()
    return result


def test_no_token_or_wrong_token_is_401():
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers=headers("token-nobody")).status_code == 401
    assert client.post("/chat", json={"message": "hi"}).status_code == 401


def test_only_leads_can_list_and_decide_approvals(temp_database):
    proposal = propose_as_agent(temp_database)
    assert client.get("/approvals", headers=headers("token-customer")).status_code == 403
    assert client.get("/approvals", headers=headers("token-agent")).status_code == 403
    listed = client.get("/approvals", headers=headers("token-lead")).json()["approvals"]
    assert [item["approval_id"] for item in listed] == [proposal["approval_id"]]
    body = {"decision": "approve", "action_hash": proposal["action_hash"]}
    path = f"/approvals/{proposal['approval_id']}/decide"
    assert client.post(path, json=body, headers=headers("token-customer")).status_code == 403
    done = client.post(path, json=body, headers=headers("token-lead"))
    assert done.json()["status"] == "executed"
    assert client.post(path, json=body, headers=headers("token-lead")).status_code == 403


def test_unknown_fields_are_rejected():
    reply = client.post("/chat", json={"message": "hi", "tenant_id": "t-other"}, headers=headers("token-customer"))
    assert reply.status_code == 422


def test_chat_streams_what_the_framework_yields_for_the_token_identity():
    reply = client.post("/chat", json={"message": "hi"}, headers=headers("token-customer"))
    assert reply.status_code == 200
    assert '"kind": "answer"' in reply.text


def test_chat_passes_the_conversation_id_and_the_usage_event_through():
    body = {"message": "hi", "conversation_id": "case-g01"}
    reply = client.post("/chat", json=body, headers=headers("token-customer"))
    assert "echo u-acme-01 case-g01" in reply.text
    assert '"kind": "usage"' in reply.text
    bad = client.post("/chat", json={"message": "hi", "conversation_id": "../x"}, headers=headers("token-customer"))
    assert bad.status_code == 422
