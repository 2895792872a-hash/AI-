"""LangGraph StateGraph — two-stage VL-driven agent.

Pipeline:
    START → vl_agent (loop: see→decide→act→repeat) → result_summary → END

The vl_agent internally loops: take screenshot, send to Qwen VL, execute action,
repeat until VL says "done" or max steps reached.

VL agent handles its own verification and final summary. Result summary node
acts as fallback if VL agent didn't complete.
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes.vl_agent import run as vl_agent_node
from .nodes.result_summarization import run as result_summary_node


def _should_summarize(state: AgentState) -> str:
    """Skip result_summary if VL agent already completed with data."""
    if state.get("stage_progress") == "done" and state.get("final_summary"):
        return "end"
    return "summarize"


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("vl_agent", vl_agent_node)
    workflow.add_node("result_summary", result_summary_node)

    workflow.set_entry_point("vl_agent")
    workflow.add_conditional_edges(
        "vl_agent",
        _should_summarize,
        {"end": END, "summarize": "result_summary"},
    )
    workflow.add_edge("result_summary", END)

    return workflow.compile()


_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
