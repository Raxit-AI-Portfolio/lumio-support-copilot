# Lumio Support Copilot: MVP on LangGraph

The same demo as `mvp_adk`, with LangGraph and LangChain in place of Google ADK. Data, tools, guardrails, gateway,
web page, cloud scripts and the golden eval set are shared from `mvp_common/`.
## What differs from ADK

| Part | ADK (`mvp_adk`) | LangGraph (`mvp_lc`) |
|---|---|---|
| Model | `google.adk.models.Gemini` | `ChatGoogleGenerativeAI(vertexai=True, location="global")` |
| Specialist agent | `LlmAgent` | `langchain.agents.create_agent` (a small graph: model node, tool node) |
| Coordinator | `sub_agents` and `transfer_to_agent` | hand-built `StateGraph`: router node with structured output, conditional edge to a specialist |
| Agent as a tool | `AgentTool` | a `@tool` that calls the knowledge agent with the same run config |
| Identity in tools | `tool_context.state["identity"]` | `config["configurable"]["identity"]` (`RunnableConfig`, hidden from the model) |
| Role allow-list | `before_tool_callback` | per-role tool lists at build time, plus `ToolGuard` middleware at call time |
| Result screening | `after_tool_callback` | `ToolGuard` middleware |
| Memory | ADK session service | `InMemorySaver`, `thread_id` = user id |
| Streaming status | ADK events | `astream(stream_mode="updates", subgraphs=True)` |
| MCP read tools | `McpToolset` with `header_provider` | `MultiServerMCPClient` with a tool interceptor that adds the headers |
| Python environment | `mvp_adk/.venv`, `mcp 2.3.0` | `mvp_lc/.venv`, `mcp 1.30.0` (the adapters need `mcp<2`) |
| Deploy | Cloud Run and Agent Engine | Cloud Run only |

## Files

```text
mvp_lc/
  agent/tools.py    seven tools; identity from config, tenant filter stays in mvp_common/tools/scope.py
  agent/mcp_read_tools.py  MCP client for the three ticket read tools (used when MCP_URL is set)
  agent/guard.py    ToolGuard: role check, call cap, result screening
  agent/agents.py   model, prompts, specialists per role
  agent/graph.py    the router StateGraph
  agent/run.py      run_turn (same output shape as ADK), command line ask
  web/app.py        shared gateway plus run_turn
  evals/run.py      retrieval and agent evals (shared scoring)
  scripts/deploy.py Cloud Run service lumio-lc (owner runs it)
  tests/            offline tests for the real logic
```

## Not built

- Agent Engine deploy for LangGraph.
