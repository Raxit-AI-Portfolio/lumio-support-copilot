import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage

from mvp_common.guardrails import MAX_CALLS_PER_TURN
from mvp_lc.agent import tools
from mvp_lc.agent.agents import tools_for
from mvp_lc.agent.graph import State, next_node
from mvp_lc.agent.guard import ToolGuard, check_call
from mvp_lc.agent.mcp_read_tools import add_user_headers, tool_pool
from mvp_lc.agent.run import statuses_in


def names(role, wanted):
    return sorted(one.name for one in tools_for(role, wanted))


def test_each_role_only_gets_its_own_tools():
    every = [one.name for one in tools.ALL_TOOLS]
    assert "propose_action" not in names("customer", every)
    assert "queue_summary" not in names("customer", every)
    assert "propose_action" in names("agent", every)
    assert "queue_summary" not in names("agent", every)
    assert {"propose_action", "queue_summary"} <= set(names("lead", every))


def test_the_model_never_sees_identity_or_tenant_arguments():
    for one in tools.ALL_TOOLS:
        assert not {"config", "identity", "tenant_id", "role", "user_id"} & set(one.tool_call_schema.model_fields)


def test_guard_refuses_a_tool_outside_the_role_and_caps_calls_per_turn():
    turn = {"calls": 0, "retrieved": []}
    assert check_call("customer", "propose_action", turn) == "not allowed"
    assert turn["calls"] == 0
    for _ in range(MAX_CALLS_PER_TURN):
        assert check_call("agent", "get_ticket", turn) == ""
    assert check_call("agent", "get_ticket", turn) == "too many tool calls in this turn"


def test_guard_screens_a_flagged_result_before_the_model_reads_it(monkeypatch):
    config = {"configurable": {"identity": {"role": "agent"}, "turn": {"calls": 0}}}
    monkeypatch.setattr("mvp_lc.agent.guard.get_config", lambda: config)
    monkeypatch.setattr("mvp_lc.agent.guard.screen_text", lambda text: False)
    request = SimpleNamespace(tool_call={"name": "kb_search", "id": "1", "args": {}})

    async def handler(req):
        return ToolMessage(content="bad text", name="kb_search", tool_call_id="1")

    result = asyncio.run(ToolGuard().awrap_tool_call(request, handler))
    assert "blocked by the safety filter" in result.content


def test_low_score_hits_are_dropped_so_the_agent_abstains(monkeypatch):
    weak = {"chunk_id": "c#1", "title": "t", "text": "x", "score": 0.3}
    monkeypatch.setattr(tools, "search_kb", lambda query, role, top_k: [weak])
    turn = {"calls": 0, "retrieved": []}
    config = {"configurable": {"identity": {"role": "customer"}, "turn": turn}}
    result = tools.kb_search.func("weather", config)
    assert result["hits"] == [] and turn["retrieved"] == []


def test_status_lines_show_the_route_tool_calls_and_blocked_calls():
    assert statuses_in((), {"router": {"route": "knowledge_agent"}}) == ["coordinator -> route_to_knowledge_agent"]
    call = AIMessage("", tool_calls=[{"name": "kb_search", "args": {}, "id": "1"}])
    assert statuses_in(("knowledge_agent:1",), {"model": {"messages": [call]}}) == ["knowledge_agent -> kb_search"]
    assert statuses_in((), {"knowledge_agent": {"messages": [call]}}) == []
    blocked = ToolMessage('{"error": "not allowed"}', name="queue_summary", tool_call_id="2")
    out = statuses_in(("ticket_ops_agent:1",), {"tools": {"messages": [blocked]}})
    assert out == ["ticket_ops_agent !! queue_summary blocked by role check"]


def test_router_ends_the_turn_when_it_asked_a_question():
    assert next_node(State(messages=[], route="")) == "__end__"
    assert next_node(State(messages=[], route="resolution_agent")) == "resolution_agent"


def test_mcp_calls_carry_the_user_id_from_the_verified_identity(monkeypatch):
    config = {"configurable": {"identity": {"user_id": "u-lead-01"}}}
    monkeypatch.setattr("mvp_lc.agent.mcp_read_tools.get_config", lambda: config)
    request = SimpleNamespace(override=lambda headers: headers)

    async def handler(headers):
        return headers

    headers = asyncio.run(add_user_headers(request, handler))
    assert headers["x-lumio-user"] == "u-lead-01"
    assert "x-service-secret" in headers


def test_without_mcp_url_the_read_tools_stay_local(monkeypatch):
    monkeypatch.setattr("mvp_lc.agent.mcp_read_tools.get_setting", lambda name, default="": "")
    assert asyncio.run(tool_pool()) is tools.ALL_TOOLS


def test_usage_of_sums_models_and_splits_thinking_from_output():
    from mvp_lc.agent.run import CountingUsage, usage_of

    counter = CountingUsage()
    counter.calls = 3
    counter.usage_metadata = {
        "gemini": {"input_tokens": 300, "output_tokens": 50, "output_token_details": {"reasoning": 20}},
    }
    assert usage_of(counter) == {"model_calls": 3, "input_tokens": 300, "output_tokens": 30, "thinking_tokens": 20}
