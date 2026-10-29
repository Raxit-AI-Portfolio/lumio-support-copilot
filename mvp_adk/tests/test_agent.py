from types import SimpleNamespace

from mvp_adk.agent import tools
from mvp_adk.agent.agents import make_coordinator
from mvp_adk.agent.guard import MAX_CALLS_PER_TURN, check_tool_call


def context(role):
    return SimpleNamespace(state={"identity": {"role": role, "user_id": "u-1", "assigned_tenants": []}})


def tool(name):
    return SimpleNamespace(name=name)


def test_customer_cannot_use_staff_tools_but_staff_can():
    assert check_tool_call(tool("propose_action"), {}, context("customer")) == {"error": "not allowed"}
    assert check_tool_call(tool("queue_summary"), {}, context("agent")) == {"error": "not allowed"}
    assert check_tool_call(tool("propose_action"), {}, context("agent")) is None
    assert check_tool_call(tool("queue_summary"), {}, context("lead")) is None


def test_tool_calls_per_turn_are_capped():
    ctx = context("customer")
    for _ in range(MAX_CALLS_PER_TURN):
        assert check_tool_call(tool("kb_search"), {}, ctx) is None
    assert "too many" in check_tool_call(tool("kb_search"), {}, ctx)["error"]


def test_low_score_hits_are_dropped_so_the_agent_abstains(monkeypatch):
    weak_hit = {"chunk_id": "a#1", "title": "A", "text": "text", "score": 0.2}
    monkeypatch.setattr(tools, "search_kb", lambda query, role, top_k: [weak_hit])
    ctx = context("customer")
    result = tools.kb_search("anything", ctx)
    assert result["hits"] == []
    assert ctx.state["temp:last_retrieved_ids"] == []


def test_coordinator_has_three_specialists_and_no_tools():
    coordinator = make_coordinator()
    names = [agent.name for agent in coordinator.sub_agents]
    assert names == ["knowledge_agent", "ticket_ops_agent", "resolution_agent"]
    assert not coordinator.tools


def test_specialists_hand_control_back_to_the_coordinator_every_turn():
    for agent in make_coordinator().sub_agents:
        assert agent.disallow_transfer_to_parent is True
        assert agent.disallow_transfer_to_peers is True


def test_model_calls_are_counted_in_the_turns_usage_record_only():
    from mvp_adk.agent.usage import count_model_call, start_turn

    meta = SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=None)
    assert count_model_call(None, SimpleNamespace(usage_metadata=meta)) is None
    usage = start_turn()
    count_model_call(None, SimpleNamespace(usage_metadata=meta))
    count_model_call(None, SimpleNamespace(usage_metadata=None))
    assert usage["input_tokens"] == 100 and usage["output_tokens"] == 20 and usage["model_calls"] == 1
