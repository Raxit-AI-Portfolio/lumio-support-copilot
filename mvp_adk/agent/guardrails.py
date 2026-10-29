"""ADK hook for the guardrails: screen what a tool returns before the model reads it."""

import json

from mvp_common.guardrails import SCREENED_TOOLS, screen_text


def screen_tool_result(tool, args, tool_context, tool_response):
    """ADK after_tool_callback: replace a flagged result with an error, so the model never reads it."""
    if tool.name not in SCREENED_TOOLS:
        return None
    if screen_text(json.dumps(tool_response)):
        return None
    return {"error": "content blocked by the safety filter"}
