# Framework comparison: Google ADK vs LangGraph (local run)

Report 1 of 2. This one covers **time, pass rate and tool-call count** with both demos running on one local machine.
Report 2 (cloud run, adds token counts) is planned and is not written yet.

## The use case

Lumio Support Copilot: a multi-tenant support assistant with three roles (customer, agent, lead). A coordinator routes
each request to one of three specialists (knowledge, ticket operations, resolution). Tools enforce the tenant filter,
role checks and a two-person approval in code. Both demos use the same tools, data, guardrails, web gateway and the
same 12-case golden set (`mvp_common/evals/golden.json`). Only the agent layer differs.

| | Google ADK (`mvp_adk`) | LangGraph (`mvp_lc`) |
|---|---|---|
| Model | `gemini-3.5-flash-lite` on Vertex AI, global endpoint | the same |
| Coordinator | LLM agent with `sub_agents` and `transfer_to_agent` | hand-built `StateGraph`: router node with structured output, conditional edge |
| Specialists | `LlmAgent` | `langchain.agents.create_agent` |
| Library versions | `google-adk` 2.10.0 | `langgraph` 1.2.11, `langchain` 1.4.2, `langchain-google-genai` 4.4.0 |

## How it was measured

- `python -m mvp_adk.evals.run agent` and `python -m mvp_lc.evals.run agent`, each in its own venv, run from the repo root.
- 3 runs per framework, run one after another (ADK, LangGraph, ADK, ...) on the same machine and network, so they did not
  compete for CPU. Local tools, no MCP (`MCP_URL` empty).
- Each case runs on a fresh database and a fresh conversation. A case passes only if the expected agent and tools were
  used, no forbidden tool was called, and the answer contains or avoids the expected text.
- Time is wall-clock per case, measured around the whole turn. It includes the live model calls to Vertex AI and the
  embedding call for knowledge questions, so it includes network time.
- Tool calls exclude routing hand-offs (`transfer_to_agent` for ADK, the router choice for LangGraph).

## Results

### Pass rate

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| ADK | 12/12 | 12/12 | 12/12 |
| LangGraph | 12/12 | 12/12 | 12/12 |

No forbidden tool call in any of the 6 runs. Both demos pass the same golden set.

### Time per case (seconds)

| | Run | Median | Slowest | Total for 12 cases |
|---|---|---|---|---|
| ADK | 1 | 11.8 | 35.5 | 172 |
| ADK | 2 | 9.1 | 29.9 | 145 |
| ADK | 3 | 7.6 | 14.1 | 103 |
| LangGraph | 1 | 5.4 | 26.5 | 94 |
| LangGraph | 2 | 4.8 | 17.4 | 78 |
| LangGraph | 3 | 5.3 | 12.9 | 73 |

Averaged over the 3 runs: ADK total 140 s and LangGraph total 82 s, so LangGraph was about 40 % faster in this setup.
The average median per case was about 9.5 s for ADK and 5.2 s for LangGraph.

Average seconds per case (3 runs):

| Case | What it tests | ADK | LangGraph |
|---|---|---|---|
| g01 | help question (KB search) | 15.5 | 17.4 |
| g02 | look up a ticket | 16.1 | 5.4 |
| g03 | list my tickets | 11.0 | 2.8 |
| g04 | ticket not in my tenant | 8.8 | 2.9 |
| g05 | policy question (KB search) | 23.2 | 15.7 |
| g06 | off-topic question | 4.5 | 1.4 |
| g07 | create a ticket | 9.2 | 3.1 |
| g08 | prompt-injection attempt | 9.1 | 0.9 |
| g09 | policy question as agent | 14.5 | 12.8 |
| g10 | propose a refund | 10.2 | 5.2 |
| g11 | agent asks for a lead-only report | 9.3 | 5.3 |
| g12 | lead asks for the queue summary | 8.4 | 9.0 |

The first case of each run includes one-time start-up work for that process, so g01 is inflated in both.

### Tool calls (excluding routing)

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| ADK | 14 | 14 | 12 |
| LangGraph | 13 | 12 | 11 |

The counts are close, so the time difference does not come from LangGraph making far fewer tool calls.

### Code and environment size

| | ADK | LangGraph |
|---|---|---|
| Agent code (non-blank, non-comment lines in `agent/`) | 248 | 259 |
| Offline tests in the demo folder | 8 | 9 |
| Packages in the venv | 95 | 74 |
| Venv size | 224 MB | 172 MB |

Shared code (`mvp_common`, 24 tests) is the same for both. The line count of the agent layer is nearly equal.

## Capability comparison

| Capability | ADK | LangGraph |
|---|---|---|
| Multi-agent routing | Built in: `sub_agents` with `transfer_to_agent`. Less code, the routing path is less visible. | You build the graph. More explicit: the route is a typed choice and an edge you can read. |
| Identity kept out of the model | Session state, read as `tool_context.state` | Run config, read as `config["configurable"]`, hidden from the tool schema |
| Role allow-list and call cap | `before_tool_callback` | Per-role tool lists at build time plus a `ToolGuard` middleware at call time |
| Screening tool results | `after_tool_callback` | The same middleware |
| Agent as a tool | `AgentTool` | A small `@tool` wrapping the agent |
| MCP tools | `McpToolset` with a header provider | `langchain-mcp-adapters` with a tool interceptor. Both pass the 12-case set over MCP. |
| Conversation memory | Built-in session service | A checkpointer you choose. Thread id must be set with care: in the first LangGraph runs, cases shared one conversation per user and 1 case in 12 failed. |
| Streaming progress | ADK events | `astream` updates with subgraphs |
| Managed hosting | Agent Engine is supported out of the box (deployed once in this project) | Not built here |
| Dependency conflicts | `mcp` 2.x | Adapters need `mcp` below 2, so a separate venv is needed |

## Findings

1. **Both frameworks do the job.** Same golden set, 12/12 in every run, no forbidden calls.
2. **LangGraph was faster per turn here, about 40 % on total time.** One possible reason: ADK's coordinator makes a model call to decide the transfer and then runs the specialist inside the same framework loop, while the LangGraph router is one structured call. This is a hypothesis; I did not test it.
3. **The effort is similar.** Agent-layer code is about 250 lines for each. ADK needs fewer lines for routing. LangGraph needs more explicit code for the graph and guard but the flow is easier to read and test.
4. **The harness matters as much as the framework.** The shared-memory mistake cost LangGraph one failed case per run until fixed. Evals that share state hide or fake failures.

## Limits of this report

- One machine, one network, one region, one model. 3 runs per framework. LLM latency varies from run to run: ADK got faster across its runs (172, 145, 103 s), so more runs would help.
- Time includes network time to Vertex AI, so it is not a pure framework overhead measure.
- **Tokens and cost were not measured.** That is planned for the cloud report.
- Only 12 cases, mostly single-turn. Multi-turn conversations and load were not tested.
- Cold-start time of the process and cloud hosting were not measured.
- Results depend on these library versions and on prompts written for ADK first and adapted for LangGraph.

## Reproduce

Each command runs from the repo root. Set `MCP_URL` to empty so tools stay local.

```bash
mvp_adk/.venv/Scripts/python -m mvp_adk.evals.run agent
```

```bash
mvp_lc/.venv/Scripts/python -m mvp_lc.evals.run agent
```
