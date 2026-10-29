# Lumio Support Copilot: MVP

Small demo of the agentic AI and GCP AI parts of the HLD. The HLD (`design/`) already shows the design skill. This folder shows the build skill. Nothing here changes the HLD.

## Rules (apply to `mvp/` only)

- **No layers.** Flat modules. One file per job. No ports, no fakes, no dependency injection.
- **No contracts.** This file is the plan. Questions go in `QUESTIONS.md`.
- **Stub by default.** Build for real only the items in "Real" below.
- **Few tests.** Only on Real logic. About 25 in total. None for stubs, wiring or glue.
- **Cycle per phase:** pick phase, add files, check and test, review.
- **Done** means the demo script (`README.md`, written in P6) runs.
- File budget: about 50 Python files in total.

## Real (built for real)

- ADK agents: coordinator, knowledge, ticket ops, resolution; per-role tool allow-list.
- RAG: Vertex AI embeddings, retrieval with `access_group` filter, citations, abstain gate.
- Tools: read tools with the tenant filter added by code, never by the model.
- Approval: propose, second person approves, exact action hash.
- Model Armor screening on input and tool results.
- Small golden-set eval with path and answer scoring.

## Stub or skip

- Tokens: fixed dummy tokens mapped to fixed identities. No IdP, JWKS, redeem service, handles.
- Rate limit, Firestore stores, Secret Manager, load balancer, Cloud Armor, CI pipelines, DR.

## Layout

```text
mvp/
  MVP.md  QUESTIONS.md  README.md
  core/      settings (config.py), dummy sign-in (identity.py)
  data/      seed json, KB markdown, ingestion script
  tools/     read tools, ticket write, approvals (one app)
  agent/     ADK app
  web/       one HTML page + thin gateway
  evals/     golden set, runner
  infra/     minimal Terraform or scripts (P6)
  scripts/   up, down, audit (cloud resources)
  tests/     all tests
```

## Phases

| Phase | Adds | Check |
|---|---|---|
| P1 Data and KB | Seed and KB copied from `data/`, ingestion script (chunk, embed, store) | Search returns the right chunk and respects `access_group` |
| P2 Tools | Read tools, create ticket, comment, propose and approve action | Tenant filter and second-person rule tests |
| P3 Agents | ADK agents wired to the tools, run locally | Four demo questions route and answer |
| P4 Gateway and web | Dummy auth, streaming chat page, approvals page | Demo flow works in the browser |
| P5 Guardrails and evals | Model Armor, citation and abstain, golden set | Eval run prints scores |
| P6 Deploy and README | Cloud Run and one Agent Engine deploy, demo script | Demo script runs on GCP |
