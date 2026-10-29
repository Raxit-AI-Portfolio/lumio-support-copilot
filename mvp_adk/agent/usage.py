"""Count the tokens of every model call in a turn, including agents that run inside another agent's tool."""

from contextvars import ContextVar

from mvp_common.usage import add_usage, new_usage

CURRENT: ContextVar[dict | None] = ContextVar("turn_usage", default=None)


def start_turn() -> dict:
    """Begin counting for this turn. Returns the record that fills up as model calls finish."""
    usage = new_usage()
    CURRENT.set(usage)
    return usage


def count_model_call(callback_context, llm_response):
    """ADK after_model_callback: add this call's tokens to the turn's record. Never changes the response."""
    usage = CURRENT.get()
    meta = getattr(llm_response, "usage_metadata", None)
    if usage is not None and meta is not None:
        add_usage(usage, meta.prompt_token_count, meta.candidates_token_count, meta.thoughts_token_count)
    return None
