"""Task API routes — create, query, and stream browser automation tasks."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.graph import get_graph
from app.agent.state import create_initial_state
from app.api.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskStatusResponse,
)
from app.config import settings
from app.core.logging import logger
from app.services.redis_service import (
    set_task_state,
    get_task_state,
    update_task_field,
    publish_event,
)
from app.services.sse_service import format_sse

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── POST /tasks ──────────────────────────────────────────────


@router.post("", response_model=TaskResponse, status_code=202)
async def create_task(request: TaskCreateRequest) -> TaskResponse:
    """Create a new browser automation task.

    The task is accepted immediately and executed asynchronously.
    Use GET /tasks/{task_id}/stream for real-time progress.
    """
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    # Persist initial state
    await set_task_state(task_id, {
        "user_task": request.user_task,
        "status": "parsing",
        "stage_progress": "parsing",
        "parsed_steps_count": 0,
        "completed_steps": 0,
        "failed_steps": 0,
        "created_at": now,
        "updated_at": now,
    })

    # Launch agent execution in background
    asyncio.create_task(_execute_agent(task_id, request.user_task))

    logger.info("Task %s created: '%s...'", task_id, request.user_task[:60])
    return TaskResponse(task_id=task_id, status="accepted", created_at=now)


# ── GET /tasks/{task_id} ─────────────────────────────────────


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str) -> TaskStatusResponse:
    """Get the current status of a task."""
    state = await get_task_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return TaskStatusResponse(
        task_id=task_id,
        user_task=state.get("user_task", ""),
        status=state.get("status", "unknown"),
        stage_progress=state.get("stage_progress", ""),
        parsed_steps_count=state.get("parsed_steps_count", 0),
        completed_steps=state.get("completed_steps", 0),
        failed_steps=state.get("failed_steps", 0),
        final_summary=state.get("final_summary"),
        extracted_data=state.get("extracted_data"),
        error=state.get("error"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


# ── GET /tasks/{task_id}/stream ──────────────────────────────


@router.get("/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE endpoint — streams real-time agent execution progress.

    Returns a text/event-stream with typed events:
      - stage_change  {stage, progress_pct, message}
      - step_start    {step_id, action, description}
      - step_complete {step_id, action, result_summary}
      - step_error    {step_id, action, error}
      - done          {summary, total_steps, success_count, fail_count}
      - error         {error, stage_failed}
    """

    async def event_generator():
        from app.services.redis_service import subscribe_events

        # Send initial connected event
        yield format_sse("connected", {"task_id": task_id})

        try:
            async for event in subscribe_events(task_id):
                event_type = event.get("type", "message")
                yield format_sse(event_type, event)

                if event_type in ("done", "error"):
                    break
        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled for task %s", task_id)
        except Exception as exc:
            logger.error("SSE stream error for task %s: %s", task_id, exc)
            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Internal agent execution ─────────────────────────────────


async def _execute_agent(task_id: str, user_task: str) -> None:
    """Run the LangGraph agent in the background, publishing progress via Redis."""

    # Progress callback: publishes each event to Redis pub/sub
    async def progress_callback(event_type: str, data: dict) -> None:
        data["type"] = event_type
        data["task_id"] = task_id
        await publish_event(task_id, data)

    try:
        graph = get_graph()
        initial_state = create_initial_state(user_task, task_id)

        # Inject progress callback into state
        initial_state["_progress_callback"] = progress_callback  # type: ignore[typeddict-unknown-key]

        config = {
            "configurable": {
                "thread_id": task_id,
            },
        }

        # Notify: stage parsing
        await progress_callback("stage_change", {
            "stage": "parsing",
            "progress_pct": 0,
            "message": "Analyzing your task...",
        })

        # Run the graph
        final_state = await graph.ainvoke(initial_state, config)

        # Count results
        total_steps = len(final_state.get("parsed_steps", []))
        browser_results = final_state.get("browser_results", [])
        success_count = sum(1 for r in browser_results if r.get("status") == "completed")
        fail_count = len(browser_results) - success_count

        # Persist final state
        now = datetime.now(timezone.utc).isoformat()
        await set_task_state(task_id, {
            "user_task": user_task,
            "status": final_state.get("stage_progress", "done"),
            "stage_progress": final_state.get("stage_progress", "done"),
            "parsed_steps_count": total_steps,
            "completed_steps": success_count,
            "failed_steps": fail_count,
            "final_summary": final_state.get("final_summary", ""),
            "extracted_data": final_state.get("extracted_data"),
            "error": final_state.get("error"),
            "updated_at": now,
        })

        # Notify done
        await progress_callback("done", {
            "summary": final_state.get("final_summary", ""),
            "total_steps": total_steps,
            "success_count": success_count,
            "fail_count": fail_count,
        })

        logger.info("Task %s completed: %d/%d steps succeeded", task_id, success_count, total_steps)

    except Exception as exc:
        logger.error("Task %s failed: %s", task_id, exc)
        await progress_callback("error", {
            "error": str(exc),
            "stage_failed": "unknown",
        })
        await update_task_field(task_id, "status", "error")
        await update_task_field(task_id, "error", str(exc))
