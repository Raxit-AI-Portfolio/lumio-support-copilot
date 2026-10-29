# Lumio Support Copilot: LangGraph version

Same demo as [mvp_adk](../mvp_adk/README.md), built with LangGraph and LangChain. Design notes and the ADK comparison:
[MVP_LC.md](MVP_LC.md). Run everything from the repository root. Settings live in `mvp_common/.env`.

## Own virtual environment

`mvp_lc` has its own venv, because `langchain-mcp-adapters` needs `mcp<2` while `mvp_adk` and `fastmcp` need `mcp 2.x`.
`mvp_common` has no environment of its own; it runs inside the venv of whichever demo imports it.

```bash
python -m venv mvp_lc/.venv
```

```bash
mvp_lc/.venv/Scripts/python -m pip install -r mvp_lc/requirements.txt
```

Use `mvp_lc/.venv/Scripts/python` (Windows) or `mvp_lc/.venv/bin/python` in place of `python` in every command below.

## Run locally

```bash
python -m mvp_common.tools.db
python -m mvp_common.data.ingest
python -m uvicorn mvp_lc.web.app:app --port 8081
```

Open http://localhost:8081, pick a persona and chat. Or ask from the command line:

```bash
python -m mvp_lc.agent.run token-customer "How many boards does the Free tier allow?"
```

## Check

```bash
python -m pytest mvp_lc mvp_common -q
```

The MCP server test is skipped here (this venv has no `fastmcp`); it runs in the `mvp_adk` venv.

```bash
python -m mvp_lc.evals.run agent
```

```bash
python -m mvp_common.scripts.smoke http://localhost:8081
```

The same golden set can run against any running copy over HTTP, including a Cloud Run service through the proxy.
It prints time, tool calls and token counts:

```bash
python -m mvp_common.evals.http_eval http://localhost:8081
```

## Cloud Run (the owner runs this; it uses gcloud and Cloud Build)

```bash
python -m mvp_lc.scripts.deploy
```

Remove everything at the end (also deletes the `lumio-lc` service and runs the audit):

```bash
python -m mvp_common.scripts.down
```

## Optional: MCP read tools

The MCP server needs `fastmcp`, so start it from the `mvp_adk` venv, in a second terminal:

```bash
mvp_adk/.venv/Scripts/python -m mvp_common.tools.mcp_server
```

Then set `MCP_URL=http://127.0.0.1:8001/mcp` in `mvp_common/.env`. The ticket agent then reads tickets through MCP;
the user id travels in a header added from the verified identity. An empty `MCP_URL` uses the local functions.
