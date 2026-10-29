"""Checks around every tool call: role allow-list (BR-AUT-03), a call cap per turn (BR-CHT-04) and result screening."""

import json

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.config import get_config

from mvp_common.guardrails import ALLOWED_TOOLS, MAX_CALLS_PER_TURN, SCREENED_TOOLS, screen_text


def check_call(role: str, tool_name: str, turn: dict) -> str:
    """Return why the call is refused, or an empty string to allow it. Counts the call in turn."""
    if tool_name not in ALLOWED_TOOLS.get(role, []):
        return "not allowed"
    if turn["calls"] >= MAX_CALLS_PER_TURN:
        return "too many tool calls in this turn"
    turn["calls"] += 1
    return ""


def refuse(request, reason: str) -> ToolMessage:
    """A tool result that tells the model the call did not run."""
    call = request.tool_call
    return ToolMessage(content=json.dumps({"error": reason}), name=call["name"], tool_call_id=call["id"])


class ToolGuard(AgentMiddleware):
    """Wraps each tool call: check the call before it runs, screen the result before the model reads it."""

    async def awrap_tool_call(self, request, handler):
        configurable = get_config()["configurable"]
        reason = check_call(configurable["identity"]["role"], request.tool_call["name"], configurable["turn"])
        if reason:
            return refuse(request, reason)
        result = await handler(request)
        if request.tool_call["name"] in SCREENED_TOOLS and not screen_text(str(result.content)):
            return refuse(request, "content blocked by the safety filter")
        return result
