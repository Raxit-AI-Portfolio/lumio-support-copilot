# Questions

Each question has a default. If you do not answer, the default is used. Edit the "Answer" line to change it.

| # | Question | Default | Answer |
|---|---|---|---|
| 1 | Where do tickets and approvals live in P1 to P5? | SQLite file, zero cost. BigQuery added in P6 only if you want it shown. | |
| 2 | Where do KB vectors live in P1 to P5? | Local JSON file, cosine in plain Python. Vector Search 2.0 added in P6 if you want it shown. | |
| 3 | Which model ids? | Same as HLD: `gemini-3.5-flash-lite` and `gemini-embedding-001`. Checked against the project in P1. | |
| 4 | Which GCP project, region and login? | Application Default Credentials, project and region in `mvp_common/.env` (git-ignored). Needed from P1. | |
| 5 | Reuse code from `services/`? | No. Copy only `data/seed` and `data/kb`. Write the rest fresh and flat. | |
| 6 | Dummy tokens? | `token-customer`, `token-agent`, `token-lead` mapped to three seed users in a Python dict. | |
| 7 | Python env? | One `mvp/requirements.txt` and one venv for all of `mvp/`. | |
| 8 | MCP server? | Not in P3. Agents call plain Python tools (simpler, identity injected by code). A FastMCP wrapper of the read tools is an optional step P3b if you want MCP shown. | |
