"""Check a running copy of the app: local, or Cloud Run through the proxy. Prints PASS or FAIL per check.

Run from the repo root: python -m mvp_common.scripts.smoke [base_url]      (default http://localhost:8080)
"""

import json
import sys

import httpx


def headers(token: str) -> dict:
    """Bearer header for a dummy token."""
    return {"Authorization": f"Bearer {token}"}


def chat_answer(base: str, token: str, message: str) -> str:
    """Send one chat message and return the final answer text (or the error text)."""
    answer = ""
    with httpx.stream("POST", f"{base}/chat", json={"message": message}, headers=headers(token), timeout=180) as reply:
        for line in reply.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if event["kind"] in ("answer", "error"):
                    answer = event["text"]
    return answer


def report(name: str, ok: bool, detail: str = "") -> bool:
    """Print one result line, with detail when it fails."""
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f"  [{detail}]"))
    return ok


def status_check(base: str, path: str, token: str, expected: int, name: str) -> bool:
    """Call one endpoint and compare the status code."""
    reply = httpx.get(f"{base}{path}", headers=headers(token) if token else {}, timeout=60)
    return report(name, reply.status_code == expected, f"got {reply.status_code}: {reply.text[:80]!r}")


def answer_check(base: str, message: str, expected: str, name: str) -> bool:
    """Ask a chat question as the customer and look for text in the answer."""
    answer = chat_answer(base, "token-customer", message)
    return report(name, expected in answer.lower(), f"answer: {answer[:120]!r}")


def main() -> None:
    """Run the checks. Exit code 1 if any fails."""
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    results = [
        status_check(base, "/me", "", 401, "no token -> 401"),
        status_check(base, "/me", "token-customer", 200, "customer identity"),
        status_check(base, "/approvals", "token-customer", 403, "customer cannot list approvals"),
        status_check(base, "/approvals", "token-lead", 200, "lead can list approvals"),
        answer_check(base, "How many boards does the Free tier allow?", "3", "cited KB answer"),
        answer_check(base, "Show me ticket T-151.", "not found", "other tenant ticket not found"),
    ]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
