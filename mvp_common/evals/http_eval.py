"""Run the golden set against a running web app: local, or a Cloud Run service through the proxy. Works for both demos.

Run from the repo root: python -m mvp_common.evals.http_eval http://localhost:8081
Each case starts a fresh conversation (a new conversation_id), so cases do not share memory.
The service keeps its own database, so the cases are not seeded here.
"""

import asyncio
import json
import sys
import uuid

import httpx

from mvp_common.core.identity import TOKENS
from mvp_common.evals.scoring import agent_eval

TIMEOUT_SECONDS = 180
TOKEN_OF = {user_id: token for token, user_id in TOKENS.items()}


def read_events(lines: list[str]) -> tuple[list[str], str, dict]:
    """Turn the server-sent event lines of one reply into (statuses, answer, usage)."""
    statuses, answer, usage = [], "", {}
    for line in lines:
        if not line.startswith("data: "):
            continue
        event = json.loads(line.removeprefix("data: "))
        if event["kind"] == "status":
            statuses.append(event["text"])
        elif event["kind"] == "usage":
            usage = event["text"]
        else:
            answer = event["text"]
    return statuses, answer, usage


async def ask_service(client: httpx.AsyncClient, case: dict, run_id: str) -> tuple[list[str], str, dict]:
    """Send one golden case to /chat as the case's user and read the reply."""
    headers = {"Authorization": f"Bearer {TOKEN_OF[case['user']]}"}
    body = {"message": case["message"], "conversation_id": f"{run_id}-{case['id']}"}
    async with client.stream("POST", "/chat", json=body, headers=headers) as reply:
        reply.raise_for_status()
        return read_events([line async for line in reply.aiter_lines()])


async def main(base_url: str) -> bool:
    """Run every case against the service and print the same report as the local eval."""
    run_id = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_SECONDS) as client:

        async def run_case(case: dict) -> tuple[list[str], str, dict]:
            return await ask_service(client, case, run_id)

        return await agent_eval(run_case, seed=False)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m mvp_common.evals.http_eval <base_url>")
    print("EVAL PASS" if asyncio.run(main(sys.argv[1])) else "EVAL FAIL")
