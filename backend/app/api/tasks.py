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
from app.services.sse_service import format_sse

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ── In-memory event store (fallback when Redis is unavailable) ──

_task_events: dict[str, asyncio.Queue] = {}
_task_states: dict[str, dict] = {}
_redis_available: bool | None = None  # None = haven't checked yet


def _get_event_queue(task_id: str) -> asyncio.Queue:
    """Get or create an in-memory event queue for a task."""
    if task_id not in _task_events:
        _task_events[task_id] = asyncio.Queue()
    return _task_events[task_id]


async def _check_redis() -> bool:
    """Quick check if Redis is available. Caches result."""
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    try:
        from app.services.redis_service import get_redis
        r = await get_redis()
        await r.ping()
        _redis_available = True
    except Exception:
        _redis_available = False
    return _redis_available


# ── Safe helpers (Redis with fallback) ───────────────────────


async def _save_state(task_id: str, state: dict) -> None:
    _task_states[task_id] = state.copy()


async def _load_state(task_id: str) -> dict | None:
    return _task_states.get(task_id)


async def _emit_event(task_id: str, event: dict) -> None:
    q = _get_event_queue(task_id)
    await q.put(event)


# ── POST /tasks ──────────────────────────────────────────────


# ── Cancellation ──
_cancelled_tasks: set = set()


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    _cancelled_tasks.add(task_id)
    return {"status": "cancelled", "task_id": task_id}


def is_cancelled(task_id: str) -> bool:
    return task_id in _cancelled_tasks


@router.post("", response_model=TaskResponse, status_code=202)
async def create_task(request: TaskCreateRequest) -> TaskResponse:
    """Create a new browser automation task."""
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    # Persist initial state (best-effort)
    await _save_state(task_id, {
        "user_task": request.user_task,
        "status": "parsing",
        "stage_progress": "parsing",
        "parsed_steps_count": 0,
        "completed_steps": 0,
        "failed_steps": 0,
        "created_at": now,
        "updated_at": now,
    })

    # Unified: LLM either answers directly or says it needs browser
    is_chat, chat_answer = await _check_intent(request.user_task)
    if is_chat:
        logger.info("Task %s → direct answer", task_id)
        asyncio.create_task(_answer_directly(task_id, request.user_task, chat_answer))
        return TaskResponse(task_id=task_id, status="accepted", created_at=now)

    # Launch agent execution in background
    asyncio.create_task(_execute_agent(task_id, request.user_task))

    logger.info("Task %s created: '%s...'", task_id, request.user_task[:60])
    return TaskResponse(task_id=task_id, status="accepted", created_at=now)


# ── GET /tasks/{task_id} ─────────────────────────────────────


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str) -> TaskStatusResponse:
    """Get the current status of a task."""
    state = await _load_state(task_id)
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
    """SSE endpoint — streams real-time agent execution progress."""

    async def event_generator():
        # Send initial connected event
        yield format_sse("connected", {"task_id": task_id})

        q = _get_event_queue(task_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield format_sse("error", {"error": "Task timed out"})
                    break

                event_type = event.get("type", "message")
                yield format_sse(event_type, event)

                if event_type in ("done", "error"):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("SSE stream error: %s", exc)
            yield format_sse("error", {"error": str(exc)})
        finally:
            # Cleanup
            _task_events.pop(task_id, None)

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


async def _check_intent(user_task: str) -> tuple[bool, str]:
    """Returns (is_chat, answer_or_browser_task). One LLM call for both."""
    try:
        from app.services.claude_service import get_text_response
        answer = await get_text_response(
            system="""You are an assistant that can answer questions OR delegate to a web browser.

Reply in ONE of two ways:

CHAT: If you can answer from your knowledge → "CHAT: [your answer]"
BROWSER: If you genuinely need a website → "BROWSER: [task for the browser agent]"

Use BROWSER only when: the task asks to visit a specific site, search live web data, check personal accounts, or access current information you don't have. All conversations, questions about yourself, complaints, feature requests, "how does X work" → CHAT.""",
            user_content=user_task,
            max_tokens=600,
            temperature=0,
        )
        text = answer.strip()
        if text.startswith("BROWSER:"):
            return False, text.replace("BROWSER:", "", 1).strip()
        chat_text = text.removeprefix("CHAT:").strip()
        return True, chat_text
    except Exception:
        return True, "抱歉，出错了，请重试。"


async def _answer_directly(task_id: str, user_task: str, answer_text: str = "") -> None:
    """Push a direct chat answer to the frontend."""
    try:
        from app.services import memory

        async def emit(etype: str, data: dict):
            data.update(type=etype, task_id=task_id)
            q = _get_event_queue(task_id)
            await q.put(data)

        await emit("done", {"summary": answer_text, "total_steps": 0, "success_count": 0, "fail_count": 0})
        memory.add_history(user_task, answer_text, success=True)
    except Exception as e:
        logger.error("Direct answer push failed: %s", e)


async def _save_to_memory(user_task: str, final_state: dict) -> None:
    """Record task result to memory after execution."""
    try:
        from app.services.memory import add_history
        error = final_state.get("error")
        summary = final_state.get("final_summary", "")
        add_history(user_task, summary, success=error is None)
    except Exception:
        pass


async def _execute_agent(task_id: str, user_task: str) -> None:
    """Run the LangGraph agent in the background, publishing progress."""

    async def progress_callback(event_type: str, data: dict) -> None:
        data["type"] = event_type
        data["task_id"] = task_id
        await _emit_event(task_id, data)

    try:
        # Register progress callback for nodes to emit events
        from app.services.progress import register, unregister
        register(task_id, progress_callback)

        graph = get_graph()
        initial_state = create_initial_state(user_task, task_id)
        config = {"configurable": {"thread_id": task_id}}

        await progress_callback("stage_change", {
            "stage": "parsing", "progress_pct": 0,
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
        await _save_state(task_id, {
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

        await progress_callback("done", {
            "summary": final_state.get("final_summary", ""),
            "total_steps": total_steps,
            "success_count": success_count,
            "fail_count": fail_count,
        })

        await _save_to_memory(user_task, final_state)
        logger.info("Task %s completed: %d/%d steps", task_id, success_count, total_steps)

    except Exception as exc:
        logger.error("Task %s failed: %s", task_id, exc)
        import traceback
        traceback.print_exc()
        await progress_callback("error", {
            "error": str(exc),
            "stage_failed": "unknown",
        })
    finally:
        from app.services.progress import unregister
        unregister(task_id)
