"""Agent state schema for the LangGraph workflow.

The AgentState is the shared data structure that flows through all four
stages of the pipeline. Each node reads from and writes to this state.
"""

from typing import Any, Optional
from typing_extensions import TypedDict, Annotated
from operator import add


class BrowserStep(TypedDict):
    """A single atomic browser action decomposed by the task parser."""

    step_id: int
    action: str  # navigate | click | type | scroll | extract | screenshot
    target_selector: Optional[str]
    input_value: Optional[str]
    url: Optional[str]
    description: str
    status: str  # pending | in_progress | completed | failed
    result: Optional[str]
    error: Optional[str]


class AgentState(TypedDict):
    """Shared state flowing through the four-stage agent pipeline."""

    # ── Conversation ──────────────────────────────────────────
    messages: Annotated[list[dict[str, Any]], add]

    # ── User Input ────────────────────────────────────────────
    user_task: str

    # ── Stage 1 Output ────────────────────────────────────────
    parsed_steps: list[BrowserStep]
    _task_retry_count: int  # internal retry counter for stage 1

    # ── Stage 2 Output ────────────────────────────────────────
    browser_results: Annotated[list[dict[str, Any]], add]
    current_step_index: int

    # ── Stage 3 Output ────────────────────────────────────────
    extracted_data: Optional[dict[str, Any]]

    # ── Stage 4 Output ────────────────────────────────────────
    final_summary: Optional[str]

    # ── Meta ──────────────────────────────────────────────────
    task_id: str
    stage_progress: str  # parsing | operating | extracting | summarizing | done | error
    error: Optional[str]


def create_initial_state(user_task: str, task_id: str) -> AgentState:
    """Return a fresh AgentState for a new task."""
    return AgentState(
        messages=[],
        user_task=user_task,
        parsed_steps=[],
        _task_retry_count=0,
        browser_results=[],
        current_step_index=0,
        extracted_data=None,
        final_summary=None,
        task_id=task_id,
        stage_progress="parsing",
        error=None,
    )
