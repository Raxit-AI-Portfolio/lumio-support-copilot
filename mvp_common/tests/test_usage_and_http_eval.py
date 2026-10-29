from mvp_common.evals.http_eval import read_events
from mvp_common.usage import add_usage, new_usage


def test_usage_adds_up_calls_and_counts_thinking_apart():
    usage = new_usage()
    add_usage(usage, 100, 20, 5)
    add_usage(usage, 50, None, None)
    assert usage == {"model_calls": 2, "input_tokens": 150, "output_tokens": 20, "thinking_tokens": 5}


def test_event_lines_become_statuses_answer_and_usage():
    lines = [
        'data: {"kind": "status", "text": "a -> kb_search"}',
        "",
        'data: {"kind": "answer", "text": "3 boards"}',
        'data: {"kind": "usage", "text": {"input_tokens": 9}}',
    ]
    assert read_events(lines) == (["a -> kb_search"], "3 boards", {"input_tokens": 9})
