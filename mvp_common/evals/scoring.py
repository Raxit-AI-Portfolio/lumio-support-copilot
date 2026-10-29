"""Eval scoring shared by both frameworks: the retrieval eval, the case checker and the golden-set loop."""

import json
import os
import statistics
import tempfile
import time
from pathlib import Path

from mvp_common.data.embeddings import make_client
from mvp_common.data.search import KB_MIN_SCORE, search_kb
from mvp_common.tools.db import connect, load_seed
from mvp_common.usage import new_usage

EVALS_DIR = Path(__file__).parent
MIN_HIT_AT_3 = 0.9
MAX_WRONG_ABSTAIN = 3
MIN_PASS_RATE = 0.85
ROUTING = ("route_to", "transfer_to_agent")  # hand-offs, not tool calls


def best_threshold(in_scores: list[float], out_scores: list[float]) -> str:
    """Try thresholds from 0.50 to 0.90 and describe the one with the fewest mistakes (ties: the higher one)."""
    best = (999, 0.0, 0, 0)
    for step in range(50, 91):
        threshold = step / 100
        wrongly_answered = sum(1 for score in out_scores if score >= threshold)
        wrongly_abstained = sum(1 for score in in_scores if score < threshold)
        if wrongly_answered + wrongly_abstained <= best[0]:
            best = (wrongly_answered + wrongly_abstained, threshold, wrongly_answered, wrongly_abstained)
    return f"{best[1]} (wrongly answered {best[2]}, wrongly abstained {best[3]})"


def retrieval_eval() -> bool:
    """Check that the right doc is in the top 3 and that off-topic questions score below the threshold."""
    questions = json.loads((EVALS_DIR / "kb_questions.json").read_text(encoding="utf-8"))
    client = make_client()
    hits = 0
    in_scores = []
    for item in questions["in_library"]:
        role = "customer" if item["asker_role"] == "customer" else "agent"
        top = search_kb(item["question"], role, top_k=3, client=client)
        in_scores.append(top[0]["score"])
        if item["expected_doc_id"] in [hit["doc_id"] for hit in top]:
            hits += 1
    out_scores = [
        search_kb(item["question"], "customer", top_k=1, client=client)[0]["score"]
        for item in questions["out_of_library"]
    ]
    wrongly_answered = sum(1 for score in out_scores if score >= KB_MIN_SCORE)
    wrongly_abstained = sum(1 for score in in_scores if score < KB_MIN_SCORE)
    hit_rate = hits / len(in_scores)
    print(f"hit@3 {hit_rate:.2f} ({hits}/{len(in_scores)})")
    print(f"in-library top score: lowest {min(in_scores):.2f}; off-topic top score: highest {max(out_scores):.2f}")
    print(f"threshold {KB_MIN_SCORE}: wrongly answered {wrongly_answered}/10, wrongly abstained {wrongly_abstained}/30")
    print(f"best threshold: {best_threshold(in_scores, out_scores)}")
    return hit_rate >= MIN_HIT_AT_3 and wrongly_answered == 0 and wrongly_abstained <= MAX_WRONG_ABSTAIN


def problems_in(case: dict, statuses: list[str], answer: str) -> list[str]:
    """Return what is wrong with one case result. An empty list means it passed."""
    calls = [line.split(" -> ") for line in statuses if " -> " in line]
    agents = [agent for agent, _ in calls]
    blocked = [line.split(" !! ")[1].split(" ")[0] for line in statuses if " !! " in line]
    tools = [tool for _, tool in calls if tool not in blocked]
    problems = []
    if case.get("expected_agent") and case["expected_agent"] not in agents:
        problems.append(f"agent {case['expected_agent']} not used")
    problems.extend(f"tool {tool} not called" for tool in case["expected_tools"] if tool not in tools)
    problems.extend(f"FORBIDDEN tool {tool} called" for tool in case["forbidden_tools"] if tool in tools)
    problems.extend(
        f"answer lacks '{text}'" for text in case.get("answer_contains", []) if text.lower() not in answer.lower()
    )
    problems.extend(
        f"answer has '{text}'" for text in case.get("answer_not_contains", []) if text.lower() in answer.lower()
    )
    return problems


async def agent_eval(run_case, seed: bool = True) -> bool:
    """Run every golden case. run_case(case) returns (statuses, answer, usage).

    With seed=True the cases run against a throwaway local database. A deployed service has its own: use seed=False.
    """
    if seed:
        os.environ["LUMIO_DB"] = str(Path(tempfile.mkdtemp()) / "eval.db")
        conn = connect()
        load_seed(conn)
        conn.close()
    cases = json.loads((EVALS_DIR / "golden.json").read_text(encoding="utf-8"))
    passed = 0
    forbidden = 0
    seconds = []
    tool_calls = 0
    tokens = new_usage()
    for case in cases:
        started = time.perf_counter()
        statuses, answer, usage = await run_case(case)
        seconds.append(time.perf_counter() - started)
        tool_calls += sum(1 for line in statuses if " -> " in line and not line.split(" -> ")[1].startswith(ROUTING))
        for name in tokens:
            tokens[name] += usage.get(name, 0)
        problems = problems_in(case, statuses, answer)
        passed += 0 if problems else 1
        forbidden += sum(1 for problem in problems if problem.startswith("FORBIDDEN"))
        out = usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)
        used = f"{usage.get('input_tokens', 0)} in, {out} out"
        print(f"{case['id']} {'PASS' if not problems else 'FAIL ' + '; '.join(problems)} ({seconds[-1]:.1f}s, {used})")
        if problems:
            print(f"    calls: {statuses}\n    answer: {answer[:150]!r}")
    print(f"passed {passed}/{len(cases)}, forbidden tool calls {forbidden}")
    median, slowest, total = statistics.median(seconds), max(seconds), sum(seconds)
    print(f"latency per case: median {median:.1f}s, slowest {slowest:.1f}s, total {total:.0f}s")
    print(f"tool calls (excluding routing): {tool_calls}")
    print(
        f"tokens: input {tokens['input_tokens']}, output {tokens['output_tokens']}, "
        f"thinking {tokens['thinking_tokens']}, model calls {tokens['model_calls']}"
    )
    return passed / len(cases) >= MIN_PASS_RATE and forbidden == 0
