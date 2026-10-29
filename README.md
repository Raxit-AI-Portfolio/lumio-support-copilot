# Lumio Support Copilot

An agentic AI support assistant for a multi-tenant SaaS, designed and built on Google Cloud.

> **Learning project: a framework comparison.** The same support use case is built twice, on Google ADK and on
> LangGraph, with shared tools, data and tests, so the two frameworks can be compared on capability and performance.
> Results: [Cloud Run, with tokens](comparison/framework_comparison_cr.md); local testing is in
> [comparison/framework_comparison_local.md](comparison/framework_comparison_local.md). It uses dummy sign-in and
> sample data and is not production software.

A customer asks a help question or checks a ticket. A support agent asks the assistant to propose a refund. A lead
approves it. Tenant isolation, roles and approvals are enforced in code, not in prompts.

## Skills

### 1. Solution design for a production-grade multi-agent AI system

[design/Lumio_Support_Copilot_HLD.md](design/Lumio_Support_Copilot_HLD.md) is the high-level design (draft v1.02). It
designs the system as if it were going to production on Google Cloud, with every requirement, rule and decision
numbered so it can be traced:

- **Scope and concept:** problem, solution, goals and success measures, design principles.
- **Requirements:** functional decomposition, workflows, roles and a permission matrix, business rules, and
  non-functional requirements with an IAM summary.
- **Architecture:** system, application and data architecture, and the agentic architecture (agent topology, RAG, MCP).
- **Architecture attributes:** scalability, resilience and disaster recovery, security, observability, trade-offs,
  deployment and CI/CD.
- **Quality and cost:** evaluation strategy (answer quality and the path an agent takes) and a cost estimate.
- **Diagrams:** in [design/diagrams/](design/diagrams/).

### 2. MVP implementation of the multi-agent system

A deliberately small, working build of the agentic parts of the design: real where it proves a skill, stubbed where it
does not. It is built twice, on [Google ADK](mvp_adk/README.md) and on [LangGraph](mvp_lc/README.md), over shared code in
`mvp_common/`.

- **Multi-agent system:** a coordinator routes each turn to a knowledge, ticket or resolution specialist, with a
  per-role tool allow-list and a call cap per turn (ADK `sub_agents`; LangGraph hand-built `StateGraph`).
- **RAG on Vertex AI:** `gemini-embedding-001` embeddings, `access_group` filter by role, citations checked against
  what was retrieved, and an abstain threshold calibrated by eval. Local index or Vertex AI Vector Search 2.0.
- **Tools and MCP:** tenant-scoped read and write tools; the read tools also served over MCP (FastMCP), with identity
  taken from a trusted header, never from the model.
- **Human approval of money actions:** propose, a different lead approves the exact action hash, expiry, runs once.
- **Guardrails:** Model Armor screening of input and tool results (fail closed).
- **Evals:** retrieval eval (hit@3 30/30) and a 12-case agent eval for routing, tools, forbidden calls and answers.
- **Deployment:** Vertex AI Agent Engine (deployed and tested once) and Cloud Run with IAM-only access, plus
  `up`, `down` and a read-only audit so nothing is left running.

### 3. Framework comparison: Google ADK vs LangGraph

The same use case, tools, data and 12-case golden set run on both frameworks, so they can be compared like for like.
Both were deployed to Cloud Run and tested there, the closest setup to production. Full report, with per-case numbers
and limits: [comparison/framework_comparison_cr.md](comparison/framework_comparison_cr.md).

**Results (Cloud Run, 27 Oct 2026, 3 runs per framework, `gemini-3.5-flash-lite` on Vertex AI):**

- **Quality:** both services passed every case that is not affected by test state, with no forbidden tool calls. Case
  g10 (propose a refund) failed in runs 2 and 3 for both, because the service keeps its database and a pending approval
  already existed; both agents correctly refused a duplicate.
- **Time:** equal. The median was about 2.4 s per case, and the 12 cases took about 33 s on ADK and 31 s on LangGraph.
- **Tokens:** this is where they differ most. ADK used about 22,300 input tokens per run against about 10,500 for
  LangGraph (2.1 times more), with similar output tokens (about 940 against 810).
- **Estimated cost:** at $0.30 per million input and $2.50 per million output tokens (third-party prices, not checked
  against Google), about $0.00076 per case for ADK and $0.00043 for LangGraph, roughly 43 % less.
- **Code and setup:** the agent layer is about 250 lines in each. LangGraph needs its own virtual environment because
  its MCP adapter requires `mcp` below 2.
- **Limits:** 3 runs, 12 mostly single-turn cases, one region, and the cost uses unverified prices.

Local testing was also performed, with both demos on one machine; see
[comparison/framework_comparison_local.md](comparison/framework_comparison_local.md).

## 🧰 Tech Stack

**Agent frameworks**
<br/>
![Google ADK](https://img.shields.io/badge/Google%20ADK-4A7BC0?style=flat-square&logo=google&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-645AA1?style=flat-square)
![FastMCP](https://img.shields.io/badge/FastMCP-645AA1?style=flat-square)

**GenAI / RAG**
<br/>
![Gemini](https://img.shields.io/badge/Gemini-7A6A90?style=flat-square&logo=googlegemini&logoColor=white)
![Vertex AI](https://img.shields.io/badge/Vertex%20AI-4A7BC0?style=flat-square&logo=googlecloud&logoColor=white)
![Embeddings](https://img.shields.io/badge/gemini--embedding--001-7A6A90?style=flat-square)
![Vector Search](https://img.shields.io/badge/Vertex%20Vector%20Search-4A7BC0?style=flat-square&logo=googlecloud&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-645AA1?style=flat-square)
![Model Armor](https://img.shields.io/badge/Model%20Armor-B75341?style=flat-square&logo=googlecloud&logoColor=white)

**Cloud & Deployment**
<br/>
![Google Cloud](https://img.shields.io/badge/Google%20Cloud-4A7BC0?style=flat-square&logo=googlecloud&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Cloud%20Run-4A7BC0?style=flat-square&logo=googlecloud&logoColor=white)
![Agent Engine](https://img.shields.io/badge/Vertex%20Agent%20Engine-4A7BC0?style=flat-square&logo=googlecloud&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-387FB5?style=flat-square&logo=docker&logoColor=white)

**Backend & Data**
<br/>
![Python 3.14](https://img.shields.io/badge/Python%203.14-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-227F76?style=flat-square&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-B2365F?style=flat-square&logo=pydantic&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3B7BA8?style=flat-square&logo=sqlite&logoColor=white)

**Quality & Safety**
<br/>
![pytest](https://img.shields.io/badge/pytest-2C7A9C?style=flat-square&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-5A4FA0?style=flat-square&logo=ruff&logoColor=white)
![Evals](https://img.shields.io/badge/Golden%20set%20evals-2E2E2E?style=flat-square)
![Human approval](https://img.shields.io/badge/Human%20approval-2E8D5A?style=flat-square)
![Tenant isolation](https://img.shields.io/badge/Tenant%20isolation-2E8D5A?style=flat-square)

## Quick start

Run everything from the repository root. Full setup, demo script and cloud commands: [mvp_adk/README.md](mvp_adk/README.md).

Each demo has its own virtual environment (`mvp_common` has none and runs in either). Example for the ADK demo; for
LangGraph use `mvp_lc` and see [mvp_lc/README.md](mvp_lc/README.md):

```bash
python -m venv mvp_adk/.venv
mvp_adk/.venv/Scripts/python -m pip install -r mvp_adk/requirements.txt
python -m mvp_common.tools.db
python -m mvp_common.data.ingest
python -m uvicorn mvp_adk.web.app:app --port 8000
```

Offline tests:

```bash
mvp_adk/.venv/Scripts/python -m pytest mvp_adk mvp_common -q
mvp_lc/.venv/Scripts/python -m pytest mvp_lc mvp_common -q
```

## Stack

Python 3.14, Google ADK, LangGraph and LangChain, Gemini (`gemini-3.5-flash-lite`), Vertex AI embeddings and Vector Search, Model Armor,
FastMCP, FastAPI, SQLite (stand-in for BigQuery), Agent Engine, Cloud Run.

Mock data only. Sign-in uses fixed dummy tokens; the real identity design is in the HLD.
