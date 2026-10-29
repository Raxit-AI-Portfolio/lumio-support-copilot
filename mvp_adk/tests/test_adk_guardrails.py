from types import SimpleNamespace

from mvp_adk.agent import guardrails
from mvp_adk.agent.guardrails import screen_tool_result


def test_flagged_tool_result_is_replaced_before_the_model_sees_it(monkeypatch):
    monkeypatch.setattr(guardrails, "screen_text", lambda text: False)
    blocked = screen_tool_result(SimpleNamespace(name="kb_search"), {}, None, {"hits": ["bad"]})
    assert blocked == {"error": "content blocked by the safety filter"}
    assert screen_tool_result(SimpleNamespace(name="queue_summary"), {}, None, {"x": 1}) is None
