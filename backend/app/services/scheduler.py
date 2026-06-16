"""Background scheduler — checks for due tasks and runs the agent.

Lightweight polling loop. No external scheduler needed.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone

from app.services import memory
from app.core.logging import logger

_polling: bool = False
_thread: threading.Thread | None = None

INTERVAL_MAP = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}


def start():
    """Start the background scheduler thread."""
    global _polling, _thread
    if _polling:
        return
    _polling = True
    _thread = threading.Thread(target=_loop, daemon=True, name="scheduler")
    _thread.start()
    logger.info("Scheduler started")


def stop():
    global _polling
    _polling = False
    logger.info("Scheduler stopped")


def _loop():
    """Poll every 10 minutes for due or overdue tasks."""
    while _polling:
        try:
            tasks = memory.get_schedules()
            now = time.time()

            for task in tasks:
                if not task.get("enabled"):
                    continue

                interval_str = task.get("interval", "daily")
                seconds = INTERVAL_MAP.get(interval_str, 86400)

                last_run = task.get("last_run")
                if last_run:
                    try:
                        last_ts = datetime.fromisoformat(last_run).timestamp()
                    except Exception:
                        last_ts = 0
                else:
                    last_ts = 0

                # Run if due OR overdue
                if now - last_ts >= seconds:
                    logger.info("Scheduler: running task '%s...'", task["user_task"][:40])
                    _run_task(task)

        except Exception as e:
            logger.error("Scheduler error: %s", e)

        time.sleep(600)  # 10 minutes


def _run_task(task: dict):
    """Run a scheduled task in a new asyncio event loop."""
    user_task = task["user_task"]
    task_id = task["id"]

    async def _run():
        from app.agent.graph import get_graph
        from app.agent.state import create_initial_state

        graph = get_graph()
        state = create_initial_state(user_task, f"sched-{task_id}")

        try:
            result = await graph.ainvoke(state, {"configurable": {"thread_id": f"sched-{task_id}"}})
            summary = result.get("final_summary", "")[:300]
            error = result.get("error")
            success = error is None and len(summary) > 30
            # Only mark as run if actually succeeded — otherwise retry on next poll
            if success:
                memory.mark_schedule_run(task_id, summary, success)
            memory.add_history(user_task, summary, success)
            logger.info("Scheduler: task '%s' completed", user_task[:40])
        except Exception as e:
            # Don't update last_run on failure — allow immediate retry
            memory.add_history(user_task, str(e)[:300], False)
            logger.error("Scheduler: task '%s' failed: %s", user_task[:40], e)

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Scheduler run error: %s", e)
