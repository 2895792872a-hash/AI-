"""LangGraph StateGraph — four-stage agent workflow.

Pipeline:
    START → task_parsing → browser_ops → info_extraction → result_summarization → END

Each stage is a node. Conditional edges handle retry logic and error routing.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes.task_parsing import run as task_parsing_node
from .nodes.browser_ops import run as browser_ops_node
from .nodes.info_extraction import run as info_extraction_node
from .nodes.result_summarization import run as result_summarization_node


# ── Conditional Routing ──────────────────────────────────────


def _after_parsing(state: AgentState) -> str:
    """Validate parsed steps; retry on failure, error if exhausted."""
    if state.get("error"):
        return "error_handler"

    steps = state.get("parsed_steps", [])
    if not steps:
        retry = state.get("_task_retry_count", 0)
        max_retries = 3
        if retry < max_retries:
            state["_task_retry_count"] = retry + 1
            return "task_parsing"  # retry
        state["error"] = f"Task parsing failed after {max_retries} attempts"
        return "error_handler"

    return "browser_ops"


def _after_browser(state: AgentState) -> str:
    """Check browser results; route to extraction or error."""
    if state.get("error"):
        return "error_handler"
    return "info_extraction"


# ── Graph Construction ───────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and compile the four-stage agent workflow graph."""

    workflow = StateGraph(AgentState)

    # ── Add Nodes ──────────────────────────────────────────
    workflow.add_node("task_parsing", task_parsing_node)
    workflow.add_node("browser_ops", browser_ops_node)
    workflow.add_node("info_extraction", info_extraction_node)
    workflow.add_node("result_summarization", result_summarization_node)
    workflow.add_node("error_handler", _error_handler)

    # ── Edges ──────────────────────────────────────────────
    workflow.set_entry_point("task_parsing")

    workflow.add_conditional_edges(
        "task_parsing",
        _after_parsing,
        {
            "browser_ops": "browser_ops",
            "task_parsing": "task_parsing",
            "error_handler": "error_handler",
        },
    )

    workflow.add_conditional_edges(
        "browser_ops",
        _after_browser,
        {
            "info_extraction": "info_extraction",
            "error_handler": "error_handler",
        },
    )

    workflow.add_edge("info_extraction", "result_summarization")
    workflow.add_edge("result_summarization", END)
    workflow.add_edge("error_handler", END)

    # ── Compile with Checkpointing ─────────────────────────
    memory = MemorySaver()
    compiled = workflow.compile(checkpointer=memory)

    return compiled


def _error_handler(state: AgentState) -> AgentState:
    """Terminal node for unrecoverable errors."""
    state["stage_progress"] = "error"
    if not state.get("error"):
        state["error"] = "An unknown error occurred."
    return state


# ── Singleton ────────────────────────────────────────────────

_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    """Return the compiled graph singleton."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
