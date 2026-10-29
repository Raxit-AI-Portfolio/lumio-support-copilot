"""Token usage of one chat turn, in the same shape for both frameworks."""


def new_usage() -> dict:
    """An empty usage record."""
    return {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}


def add_usage(usage: dict, input_tokens: int, output_tokens: int, thinking_tokens: int = 0) -> None:
    """Add the tokens of one model call. Thinking tokens are billed as output but counted apart."""
    usage["model_calls"] += 1
    usage["input_tokens"] += input_tokens or 0
    usage["output_tokens"] += output_tokens or 0
    usage["thinking_tokens"] += thinking_tokens or 0
