"""Checks that run before every tool call: role allow-list (BR-AUT-03) and a call cap per turn (BR-CHT-04)."""

from mvp_common.guardrails import ALLOWED_TOOLS, MAX_CALLS_PER_TURN


def check_tool_call(tool, args, tool_context):
    """ADK before_tool_callback. Return a dict to block the call, or None to allow it."""
    role = tool_context.state["identity"]["role"]
    if tool.name not in ALLOWED_TOOLS.get(role, []):
        return {"error": "not allowed"}
    calls = tool_context.state.get("temp:tool_calls", 0)
    if calls >= MAX_CALLS_PER_TURN:
        return {"error": "too many tool calls in this turn"}
    tool_context.state["temp:tool_calls"] = calls + 1
    return None
