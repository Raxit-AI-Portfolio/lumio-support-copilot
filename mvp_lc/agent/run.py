"""Ask the coordinator one question from the command line.

Run from the repo root: python -m mvp_lc.agent.run token-customer "How many boards does the Free tier allow?"
"""

import asyncio
import sys

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from mvp_common.core.identity import identity_from_token
from mvp_common.guardrails import clean_citations, screen_text
from mvp_common.tools.db import connect
from mvp_common.usage import add_usage, new_usage
from mvp_lc.agent.graph import build_graph
from mvp_lc.agent.mcp_read_tools import tool_pool


class CountingUsage(UsageMetadataCallbackHandler):
    """The LangChain usage handler, plus a count of model calls."""

    calls = 0

    def on_llm_end(self, response, **kwargs):
        self.calls += 1
        return super().on_llm_end(response, **kwargs)


CHECKPOINTER = InMemorySaver()
GRAPHS = {}


async def get_graph(role: str):
    """One compiled graph per role, created on first use. All of them share the conversation memory."""
    if role not in GRAPHS:
        GRAPHS[role] = build_graph(role, CHECKPOINTER, await tool_pool())
    return GRAPHS[role]


def agent_name(namespace: tuple) -> str:
    """The agent a streamed update came from: the first part of the subgraph path, or the coordinator."""
    return namespace[0].split(":")[0] if namespace else "coordinator"


def statuses_in(namespace: tuple, update: dict) -> list[str]:
    """Status lines for one streamed update: tool calls, blocked calls and the router's choice."""
    lines = []
    for node, data in update.items():
        if node == "router" and data.get("route"):
            lines.append(f"coordinator -> route_to_{data['route']}")
        if not namespace:
            continue  # the top level repeats a specialist's messages once it finishes
        for message in (data or {}).get("messages", []):
            for call in getattr(message, "tool_calls", None) or []:
                lines.append(f"{agent_name(namespace)} -> {call['name']}")
            if getattr(message, "type", "") == "tool" and "not allowed" in str(message.content):
                lines.append(f"{agent_name(namespace)} !! {message.name} blocked by role check")
    return lines


async def run_turn(identity: dict, message: str, thread_id: str = ""):
    """Run one turn in a conversation (default: the user's own).

    Yields ("status", text) per tool call, ("answer", text), then ("usage", tokens).
    Yields ("error", text) instead if the message is blocked.
    """
    if not screen_text(message):
        yield "error", "Your message was blocked by the safety filter."
        return
    graph = await get_graph(identity["role"])
    turn = {"calls": 0, "retrieved": []}
    counter = CountingUsage()
    config = {
        "configurable": {"thread_id": thread_id or identity["user_id"], "identity": identity, "turn": turn},
        "callbacks": [counter],
    }
    stream = graph.astream({"messages": [HumanMessage(message)]}, config, stream_mode="updates", subgraphs=True)
    async for namespace, update in stream:
        for line in statuses_in(namespace, update):
            yield "status", line
    last = (await graph.aget_state(config)).values["messages"][-1]
    answer, removed = clean_citations(last.text, turn["retrieved"])
    if removed:
        yield "status", f"removed unverified sources: {', '.join(removed)}"
    yield "answer", answer
    yield "usage", usage_of(counter)


def usage_of(counter: CountingUsage) -> dict:
    """The tokens of every model call in the turn (router, specialists and the agent inside a tool), summed."""
    usage = new_usage()
    for model_usage in counter.usage_metadata.values():
        thinking = (model_usage.get("output_token_details") or {}).get("reasoning", 0)
        add_usage(usage, model_usage["input_tokens"], model_usage["output_tokens"] - thinking, thinking)
    usage["model_calls"] = counter.calls
    return usage


async def ask(token: str, question: str) -> str:
    """Run one turn as the user behind the token. Prints each tool call and returns the final answer."""
    conn = connect()
    identity = identity_from_token(conn, token)
    conn.close()
    answer = ""
    async for kind, text in run_turn(identity, question):
        if kind == "status":
            print(f"  [{text}]")
        elif kind != "usage":
            answer = text  # an "error" event also lands here, so a blocked message is printed
    return answer


def main() -> None:
    """Read the token and question from the command line."""
    print(asyncio.run(ask(sys.argv[1], sys.argv[2])))


if __name__ == "__main__":
    main()
