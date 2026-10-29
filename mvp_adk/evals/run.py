"""Two small evals. Both call Vertex AI (cents of cost), so run them on request.

python -m mvp_adk.evals.run retrieval   KB search quality and the abstain threshold (embeddings only)
python -m mvp_adk.evals.run agent       routing, tools, forbidden calls and answers over golden.json (live model)
"""

import asyncio
import sys

from mvp_adk.agent.run import make_runner, run_turn, set_vertex_env, start_session
from mvp_common.core.identity import identity_from_user_id
from mvp_common.evals.scoring import agent_eval, retrieval_eval
from mvp_common.tools.db import connect


async def run_case(case: dict) -> tuple[list[str], str, dict]:
    """Run one golden case. Returns (statuses, answer, usage)."""
    conn = connect()
    identity = identity_from_user_id(conn, case["user"])
    conn.close()
    runner = make_runner()
    session_id = await start_session(runner, identity)
    statuses = []
    answer = ""
    usage = {}
    async for kind, text in run_turn(runner, identity["user_id"], session_id, case["message"]):
        if kind == "status":
            statuses.append(text)
        elif kind == "usage":
            usage = text
        else:
            answer = text
    return statuses, answer, usage


def main() -> None:
    """Run the chosen eval and print one verdict line."""
    set_vertex_env()
    if sys.argv[1:] == ["retrieval"]:
        ok = retrieval_eval()
    elif sys.argv[1:] == ["agent"]:
        ok = asyncio.run(agent_eval(run_case))
    else:
        sys.exit("usage: python -m mvp_adk.evals.run retrieval|agent")
    print("EVAL PASS" if ok else "EVAL FAIL")


if __name__ == "__main__":
    main()
