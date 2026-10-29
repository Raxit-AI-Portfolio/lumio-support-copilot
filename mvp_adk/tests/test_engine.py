from pathlib import Path

from mvp_adk.agent.engine import event_parts, stage_source


def test_staged_copy_has_the_agent_and_data_but_no_secrets_or_databases():
    root = stage_source()
    staged = root / "mvp_adk"
    names = {path.name for path in root.rglob("*")}
    assert (root / "mvp_common" / "core" / "config.py").exists()
    assert "agent_engine.py" in names
    assert "kb_index.json" in names
    assert ".env" not in names
    assert not any(name.endswith(".db") for name in names)
    assert "tests" not in names
    assert Path(staged / "engine_requirements.txt").exists()


def test_stream_line_gives_tool_calls_and_text():
    call_line = 'data: {"author": "knowledge_agent", "content": {"parts": [{"function_call": {"name": "kb_search"}}]}}'
    text_line = '{"author": "knowledge_agent", "content": {"parts": [{"text": "3 boards"}]}}'
    assert event_parts(call_line) == (["knowledge_agent -> kb_search"], "")
    assert event_parts(text_line) == ([], "3 boards")
    assert event_parts("") == ([], "")
