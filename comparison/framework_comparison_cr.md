# Framework comparison: Google ADK vs LangGraph (Cloud Run)

Report 2 of 2. Both demos were deployed to **Cloud Run** and the same 12-case golden set was run against each deployed
service. This report covers the same measures as the [local report](framework_comparison_local.md) (time, pass rate,
tool calls) and adds **tokens and an estimated cost**. Run date: 27 Oct 2026.

## Setup

| | Google ADK (`mvp_adk`) | LangGraph (`mvp_lc`) |
|---|---|---|
| Cloud Run service | `lumio-mvp` | `lumio-lc` |
| Image | `mvp_adk/Dockerfile`, Python 3.14, `google-adk` 2.10.0 | `mvp_lc/Dockerfile`, Python 3.14, `langgraph` 1.2.11, `langchain` 1.4.2 |
| Model | `gemini-3.5-flash-lite` on Vertex AI, global endpoint | the same |
| Tools | local functions, no MCP | local functions, no MCP |
| Settings (from the deploy script) | us-central1, 1 GiB, max 1 instance, IAM only | the same |

- Both services run the same code for tools, data, guardrails and the web gateway (`mvp_common/`). Only the agent layer
  differs. Model Armor and Vector Search were not created, so the knowledge search uses the local index in the image.
- The client is `python -m mvp_common.evals.http_eval <url>`. It sends each golden case to `/chat` as the case's user,
  with a new `conversation_id` per case, and reads the streamed events, including a final `usage` event.
- The services were reached through `gcloud run services proxy` on the test machine (ports 8083 and 8084). Each request
  therefore goes laptop, proxy, Cloud Run. The model calls themselves run inside Google Cloud.
- 3 runs per framework, one after another (ADK, LangGraph, ADK, ...). Time is wall-clock per case, measured by the client.
- Tokens come from the models' own usage counts: ADK through an `after_model_callback` on every agent, LangGraph
  through LangChain's usage handler. Both include the router or coordinator call and the agent that runs inside a tool.
- Tool calls exclude routing hand-offs.

## Results

### Pass rate

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| ADK | 12/12 | 11/12 | 11/12 |
| LangGraph | 12/12 | 11/12 | 11/12 |

No forbidden tool call in any of the 6 runs. The one failing case is **g10** (propose a refund) in runs 2 and 3, for
both frameworks, and it is a test-state effect, not a framework difference. The deployed services keep their database
between runs, so after run 1 a pending approval for the same order already exists. A direct check of g10 after the runs
showed both agents correctly refusing: ADK said "a pending approval already exists for this order and action", and
LangGraph said the same. The case expects an approval id in the answer, so it fails. Run 1 is the clean result.

### Time per case (seconds)

| | Run | Median | Slowest | Total for 12 cases |
|---|---|---|---|---|
| ADK | 1 | 2.4 | 4.3 | 31 |
| ADK | 2 | 2.4 | 4.4 | 31 |
| ADK | 3 | 2.3 | 8.2 | 38 |
| LangGraph | 1 | 2.4 | 8.5 | 37 |
| LangGraph | 2 | 2.3 | 4.2 | 28 |
| LangGraph | 3 | 2.4 | 4.5 | 29 |

Averaged over the 3 runs: ADK total 33 s and LangGraph total 31 s, and both have a median of about 2.4 s per case. On
Cloud Run **the two frameworks are about equal on time.**

### Tool calls (excluding routing)

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| ADK | 14 | 14 | 13 |
| LangGraph | 13 | 13 | 12 |

### Tokens

Per run of the 12 cases:

| | Run | Input tokens | Output tokens | Thinking tokens | Model calls |
|---|---|---|---|---|---|
| ADK | 1 | 22,669 | 941 | 0 | 37 |
| ADK | 2 | 22,512 | 938 | 0 | 37 |
| ADK | 3 | 21,791 | 931 | 0 | 36 |
| LangGraph | 1 | 10,548 | 816 | 0 | 36 |
| LangGraph | 2 | 10,776 | 848 | 0 | 35 |
| LangGraph | 3 | 10,261 | 779 | 0 | 34 |

Average per run: ADK 22,324 input and 937 output tokens; LangGraph 10,528 input and 814 output tokens.

- **ADK sent about 2.1 times more input tokens** for about the same number of model calls (about 37 against 35). That is
  roughly 600 input tokens per call for ADK and 300 for LangGraph.
- Output tokens are close (937 against 814).
- No thinking tokens were reported for either.
- The same pattern appeared in single local runs: ADK 22,672 input and 952 output; LangGraph 9,251 input and 805
  output. Token use does not depend on where the service runs.

Average per case over the 3 runs (seconds, input tokens, output tokens):

| Case | What it tests | ADK | LangGraph |
|---|---|---|---|
| g01 | help question (KB search) | 3.2 s, 1457 in, 64 out | 3.1 s, 619 in, 53 out |
| g02 | look up a ticket | 2.4 s, 2073 in, 73 out | 2.5 s, 1048 in, 58 out |
| g03 | list my tickets | 2.2 s, 1896 in, 73 out | 2.2 s, 871 in, 60 out |
| g04 | ticket not in my tenant | 2.3 s, 1843 in, 54 out | 2.4 s, 818 in, 47 out |
| g05 | policy question (KB search) | 3.9 s, 2510 in, 99 out | 4.4 s, 1268 in, 85 out |
| g06 | off-topic question | 1.1 s, 444 in, 36 out | 1.0 s, 233 in, 34 out |
| g07 | create a ticket | 2.3 s, 1860 in, 73 out | 2.2 s, 835 in, 61 out |
| g08 | prompt-injection attempt | 2.3 s, 1994 in, 83 out | 1.5 s, 480 in, 40 out |
| g09 | policy question as agent | 4.5 s, 1678 in, 90 out | 2.6 s, 800 in, 78 out |
| g10 | propose a refund | 4.4 s, 2847 in, 134 out | 2.5 s, 826 in, 117 out |
| g11 | agent asks for a lead-only report | 2.4 s, 1831 in, 52 out | 4.6 s, 1818 in, 87 out |
| g12 | lead asks for the queue summary | 2.3 s, 1891 in, 106 out | 2.3 s, 912 in, 95 out |

In runs 2 and 3, g10 took the "approval already exists" path, so its numbers are not a clean first-run measure.

### Estimated cost

Using $0.30 per million input tokens and $2.50 per million output tokens for `gemini-3.5-flash-lite` on Vertex AI.
**These prices are from third-party trackers, not from Google's pricing page, so treat the cost as an estimate:**
[Maxim calculator](https://www.getmaxim.ai/bifrost/llm-cost-calculator/provider/vertex_ai/model/gemini-3.5-flash-lite),
[AnotherWrapper](https://anotherwrapper.com/llm-pricing/gemini-3.5-flash-lite).

| | Per run of 12 cases | Per case | Per 1,000 conversations of this kind |
|---|---|---|---|
| ADK | about $0.0091 | about $0.00076 | about $0.76 |
| LangGraph | about $0.0052 | about $0.00043 | about $0.43 |

LangGraph was about 43 % cheaper in model cost per case in this set, almost entirely from its smaller prompts. The
golden cases are single-turn questions, so the figures say nothing about long conversations. Cloud Run, Cloud Build and
network costs are not included.

## Local vs cloud

Same 12 cases, average total time for the 12 cases:

| | Local ([local report](framework_comparison_local.md)) | Cloud Run (this report) |
|---|---|---|
| ADK | about 140 s | about 33 s |
| LangGraph | about 82 s | about 31 s |

- Both are much faster on Cloud Run, ADK about 4 times and LangGraph about 2.6 times. The model calls run in Google
  Cloud, close to Vertex AI, while the local runs went from a laptop over the internet.
- **The local advantage of LangGraph (about 40 % faster) did not carry over to Cloud Run.** On this test the
  framework's speed gap depended on where the code ran, so the local result should not be read as a general speed
  difference. I did not isolate the cause; the network distance from the laptop to Vertex AI is
  the likely main factor, but that is a guess.
- First request after deploy: `/personas` took 5.3 s on `lumio-mvp` and 0.9 s on `lumio-lc`. This is a single sample
  on a lightweight endpoint, so it is only a hint of start-up time, not a cold-start measurement.

## Findings

1. **Capability is equal on this set.** Both pass every case that is not affected by test state, with no forbidden tool
   calls, on the deployed services.
2. **Time is equal on Cloud Run** (median about 2.4 s per case for both), unlike the local run.
3. **Tokens are where the frameworks differ most.** ADK used about 2.1 times more input tokens per run, which makes
   LangGraph about 43 % cheaper per case at the quoted prices. The cause is not measured here; ADK's larger requests
   (for example the transfer tools and instructions it adds) are a plausible reason, but I did not test that.
4. **Run the same test in the deployment environment.** A local-only comparison would have overstated the time
   difference. Evals that run against a service with persistent state also need a reset between runs (g10 here).

## Limits of this report

- One project, one region, one model, one machine and proxy path, 3 runs per framework, 12 mostly single-turn cases.
- Times include the local proxy hop and LLM latency variation.
- Costs use unverified third-party prices and cover model tokens only.
- Not measured: a true cold start, concurrent load, long conversations and MCP on Cloud Run.
- The deployed services' settings are taken from the deploy script; I did not read them back from Cloud Run.

## Reproduce

Deploy both services (the owner runs these, they use gcloud), start a proxy for each, then run the eval from the repo root.

```bash
mvp_adk/.venv/Scripts/python -m mvp_adk.scripts.deploy
```

```bash
mvp_lc/.venv/Scripts/python -m mvp_lc.scripts.deploy
```

```bash
mvp_adk/.venv/Scripts/python -m mvp_common.evals.http_eval http://localhost:8083
```

```bash
mvp_lc/.venv/Scripts/python -m mvp_common.evals.http_eval http://localhost:8084
```

Restart or redeploy a service between runs if you want g10 to pass again.
