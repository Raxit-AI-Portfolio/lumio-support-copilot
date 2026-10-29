"""LangGraph web server: the shared gateway plus the LangGraph chat turn.

Run from the repo root: python -m uvicorn mvp_lc.web.app:app --port 8000
"""

from mvp_common.web.gateway import create_app
from mvp_lc.agent.run import run_turn


async def stream_turn(identity: dict, message: str, conversation_id: str = ""):
    """Run one chat turn. An empty conversation id means the user's own conversation (keyed by user id)."""
    async for item in run_turn(identity, message, thread_id=conversation_id):
        yield item


app = create_app("Lumio support copilot (MVP, LangGraph)", stream_turn)
