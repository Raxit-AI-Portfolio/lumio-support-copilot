"""Deploy, ask and delete the coordinator on Vertex AI Agent Engine. A one-time proof; it bills while it exists.

Run from the repo root:
  python -m mvp_adk.agent.engine create
  python -m mvp_adk.agent.engine ask token-customer "How many boards does the Free tier allow?"
  python -m mvp_adk.agent.engine delete
"""

import json
import os
import sys
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession

from mvp_common.core.config import get_setting
from mvp_common.core.identity import identity_from_token
from mvp_common.scripts import cloud_run
from mvp_common.tools.db import connect

ADK_DIR = Path(__file__).parent.parent
RESOURCE_FILE = ADK_DIR / "engine_resource.txt"
STRING = {"type": "string"}
OBJECT = {"type": "object"}
CLASS_METHODS = [
    {
        "name": "async_create_session",
        "api_mode": "async",
        "parameters": {"type": "object", "properties": {"user_id": STRING, "state": OBJECT}, "required": ["user_id"]},
    },
    {
        "name": "async_stream_query",
        "api_mode": "async_stream",
        "parameters": {
            "type": "object",
            "properties": {"user_id": STRING, "session_id": STRING, "message": STRING},
            "required": ["user_id", "session_id", "message"],
        },
    },
]


def stage_source() -> Path:
    """Copy mvp_adk/ and mvp_common/ to a temp folder without secrets, databases or tests. The deploy tars this copy."""
    return cloud_run.stage(ADK_DIR)


def build_config() -> dict:
    """The deploy settings. Env values are names and addresses, never secrets."""
    return {
        "display_name": "lumio-mvp",
        "source_packages": ["mvp_adk", "mvp_common"],
        "entrypoint_module": "mvp_adk.agent.agent_engine",
        "entrypoint_object": "agent_engine",
        "requirements_file": "mvp_adk/engine_requirements.txt",
        "class_methods": CLASS_METHODS,
        "agent_framework": "google-adk",
        "env_vars": {
            "MODEL": get_setting("MODEL", "gemini-3.5-flash-lite"),
            "MODEL_LOCATION": get_setting("MODEL_LOCATION", "global"),
            "EMBED_LOCATION": get_setting("EMBED_LOCATION", "us-central1"),
        },
        "max_instances": 1,
    }


def make_sdk_client():
    """The Vertex AI SDK client (installed with google-cloud-aiplatform[agent_engines])."""
    import vertexai

    return vertexai.Client(
        project=get_setting("GOOGLE_CLOUD_PROJECT"), location=get_setting("ENGINE_REGION", "us-central1")
    )


def create() -> None:
    """Deploy and remember the resource name."""
    os.chdir(stage_source())
    engine = make_sdk_client().agent_engines.create(config=build_config())
    RESOURCE_FILE.write_text(engine.api_resource.name, encoding="utf-8")
    print(f"created {engine.api_resource.name}")


def delete() -> None:
    """Delete the engine and forget it."""
    if not RESOURCE_FILE.exists():
        print("nothing to delete")
        return
    make_sdk_client().agent_engines.delete(name=RESOURCE_FILE.read_text(encoding="utf-8").strip(), force=True)
    RESOURCE_FILE.unlink()
    print("deleted")


def event_parts(line: str) -> tuple[list[str], str]:
    """Read one streamed event line. Returns (tool names called, text if any)."""
    line = line.removeprefix("data: ").strip()
    if not line.startswith("{"):
        return [], ""
    event = json.loads(line)
    calls = []
    text = ""
    for part in (event.get("content") or {}).get("parts", []):
        call = part.get("function_call") or part.get("functionCall")
        if call:
            calls.append(f"{event.get('author')} -> {call.get('name')}")
        elif part.get("text"):
            text = part["text"]
    return calls, text


def ask(token: str, question: str) -> None:
    """Start a session with the identity in state, send one question and print the tool calls and the answer."""
    resource = RESOURCE_FILE.read_text(encoding="utf-8").strip()
    location = resource.split("/")[3]
    base = f"https://{location}-aiplatform.googleapis.com/v1/{resource}"
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    session = AuthorizedSession(credentials)
    conn = connect()
    identity = identity_from_token(conn, token)
    conn.close()
    created = session.post(
        f"{base}:query",
        json={
            "class_method": "async_create_session",
            "input": {"user_id": identity["user_id"], "state": {"identity": identity}},
        },
        timeout=120,
    )
    created.raise_for_status()
    session_id = created.json()["output"]["id"]
    body = {
        "class_method": "async_stream_query",
        "input": {"user_id": identity["user_id"], "session_id": session_id, "message": question},
    }
    answer = ""
    with session.post(f"{base}:streamQuery?alt=sse", json=body, stream=True, timeout=300) as reply:
        reply.raise_for_status()
        for line in reply.iter_lines(decode_unicode=True):
            calls, text = event_parts(line or "")
            for call in calls:
                print(f"  [{call}]")
            answer = text or answer
    print(answer)


if __name__ == "__main__":
    if sys.argv[1:2] == ["create"]:
        create()
    elif sys.argv[1:2] == ["ask"] and len(sys.argv) == 4:
        ask(sys.argv[2], sys.argv[3])
    elif sys.argv[1:] == ["delete"]:
        delete()
    else:
        sys.exit('usage: python -m mvp_adk.agent.engine create | ask <token> "<question>" | delete')
