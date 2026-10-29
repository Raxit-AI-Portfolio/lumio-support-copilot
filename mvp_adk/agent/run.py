"""Ask the coordinator one question from the command line.

Run from the repo root: python -m mvp_adk.agent.run token-customer "How many boards does the Free tier allow?"
"""

import asyncio
import os
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from mvp_adk.agent.agents import make_coordinator
from mvp_adk.agent.usage import start_turn
from mvp_common.core.config import get_setting
from mvp_common.core.identity import identity_from_token
from mvp_common.guardrails import clean_citations, screen_text
from mvp_common.tools.db import connect

APP_NAME = "lumio_mvp"


def set_vertex_env() -> None:
    """Point ADK at Vertex AI using the settings in mvp_common/.env."""
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
    os.environ["GOOGLE_CLOUD_PROJECT"] = get_setting("GOOGLE_CLOUD_PROJECT")
    os.environ["GOOGLE_CLOUD_LOCATION"] = get_setting("MODEL_LOCATION", "global")


def make_runner() -> InMemoryRunner:
    """Build the runner with the coordinator."""
    return InMemoryRunner(agent=make_coordinator(), app_name=APP_NAME)


async def start_session(runner: InMemoryRunner, identity: dict) -> str:
    """Create a session that holds the identity in state. Returns the session id."""
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=identity["user_id"], state={"identity": identity}
    )
    return session.id


def hit_ids_in(event) -> list[str]:
    """Return the chunk ids that kb_search returned in this event."""
    ids = []
    for response in event.get_function_responses():
        if response.name == "kb_search":
            ids.extend(hit["chunk_id"] for hit in (response.response or {}).get("hits", []))
    return ids


async def run_turn(runner: InMemoryRunner, user_id: str, session_id: str, question: str):
    """Run one turn. Yields ("status", text) per tool call, ("answer", text), then ("usage", tokens).

    Yields ("error", text) instead if the message is blocked.
    """
    if not screen_text(question):
        yield "error", "Your message was blocked by the safety filter."
        return
    message = types.Content(role="user", parts=[types.Part(text=question)])
    usage = start_turn()
    retrieved_ids = []
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        for call in event.get_function_calls():
            yield "status", f"{event.author} -> {call.name}"
        for response in event.get_function_responses():
            if (response.response or {}).get("error") == "not allowed":
                yield "status", f"{event.author} !! {response.name} blocked by role check"
        retrieved_ids.extend(hit_ids_in(event))
        if event.error_code or event.error_message:
            yield "error", f"model error {event.error_code}: {event.error_message}"
        if event.is_final_response() and event.content and event.content.parts:
            answer, removed = clean_citations(event.content.parts[0].text or "", retrieved_ids)
            if removed:
                yield "status", f"removed unverified sources: {', '.join(removed)}"
            yield "answer", answer
    yield "usage", usage


async def ask(token: str, question: str) -> str:
    """Run one turn as the user behind the token. Prints each tool call and returns the final answer."""
    conn = connect()
    identity = identity_from_token(conn, token)
    conn.close()
    runner = make_runner()
    session_id = await start_session(runner, identity)
    answer = ""
    async for kind, text in run_turn(runner, identity["user_id"], session_id, question):
        if kind == "status":
            print(f"  [{text}]")
        elif kind != "usage":
            answer = text  # an "error" event also lands here, so a blocked message is printed
    return answer


def main() -> None:
    """Read the token and question from the command line."""
    set_vertex_env()
    print(asyncio.run(ask(sys.argv[1], sys.argv[2])))


if __name__ == "__main__":
    main()
