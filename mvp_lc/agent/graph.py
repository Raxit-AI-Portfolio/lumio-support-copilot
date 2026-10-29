"""The coordinator: a hand-built LangGraph StateGraph that routes each request to one specialist.

START -> router -> (knowledge_agent | ticket_ops_agent | resolution_agent) -> END, or router -> END with a question.
The router has no tools and never answers a request itself.
"""

from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel

from mvp_lc.agent.agents import SAFETY, make_model, make_specialists
from mvp_lc.agent.tools import ALL_TOOLS

ROUTER_PROMPT = (
    "You are the front desk of Lumio support. Pick one specialist for the request and do not answer it yourself. "
    "Help or policy questions go to knowledge_agent. Ticket lookups, new tickets, comments and queue numbers go to "
    "ticket_ops_agent. Drafting a reply or proposing a refund or credit goes to resolution_agent. "
    "If the request is unclear, or no specialist fits, choose clarify and put one short question in clarify_question. "
    + SAFETY
)


class Route(BaseModel):
    """The router's decision."""

    route: Literal["knowledge_agent", "ticket_ops_agent", "resolution_agent", "clarify"]
    clarify_question: str = ""


class State(MessagesState):
    route: str


def make_router():
    """The router node: one model call with structured output. A clarify answer ends the turn with a question."""
    model = make_model().with_structured_output(Route)

    async def router(state: State) -> dict:
        decision = await model.ainvoke([SystemMessage(ROUTER_PROMPT), *state["messages"]])
        if decision.route == "clarify":
            return {"messages": [AIMessage(decision.clarify_question or "Could you tell me a bit more?")], "route": ""}
        return {"route": decision.route}

    return router


def next_node(state: State) -> Literal["knowledge_agent", "ticket_ops_agent", "resolution_agent", "__end__"]:
    """The edge after the router: the chosen specialist, or the end when the router asked a question."""
    return state["route"] or END


def build_graph(role: str, checkpointer=None, pool: list = ALL_TOOLS):
    """Compile the coordinator graph for one role. The checkpointer keeps the conversation per thread id."""
    graph = StateGraph(State)
    graph.add_node("router", make_router())
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", next_node)
    for name, specialist in make_specialists(role, pool).items():
        graph.add_node(name, specialist)
        graph.add_edge(name, END)
    return graph.compile(checkpointer=checkpointer)
