"""ADK web server: the shared gateway plus the ADK chat turn.

Run from the repo root: python -m uvicorn mvp_adk.web.app:app --port 8000
"""

from mvp_adk.agent.run import make_runner, run_turn, set_vertex_env, start_session
from mvp_common.web.gateway import create_app

sessions = {}


async def stream_turn(identity: dict, message: str, conversation_id: str = ""):
    """Run one chat turn in the caller's ADK session (created on the first message of a conversation)."""
    set_vertex_env()
    user_id = identity["user_id"]
    key = (user_id, conversation_id)
    if key not in sessions:
        runner = make_runner()
        sessions[key] = (runner, await start_session(runner, identity))
    runner, session_id = sessions[key]
    async for item in run_turn(runner, user_id, session_id, message):
        yield item


app = create_app("Lumio support copilot (MVP, ADK)", stream_turn)
