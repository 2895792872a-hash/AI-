"""Stage 2: Browser Operations — execute steps via Playwright.

Iterates through parsed_steps, executes each via BrowserSession
with per-step retry, collects results, and emits progress events.
"""

from __future__ import annotations

import asyncio


from app.agent.state import AgentState, BrowserStep
from app.agent.tools.playwright_executor import managed_browser
from app.agent.tools.security import check_blacklist
from app.config import settings
from app.core.logging import logger
from app.services.progress import emit as emit_progress


async def run(state: AgentState) -> AgentState:
    """Execute parsed browser steps with retry logic."""
    steps = state.get("parsed_steps", [])
    logger.info("[Stage 2] Executing %d browser steps", len(steps))

    if not steps:
        state["stage_progress"] = "extracting"
        return state

    task_id = state.get("task_id", "unknown")

    async with managed_browser() as browser:
        for i, step in enumerate(steps):
            state["current_step_index"] = i

            # Re-validate security before execution
            ok, err = check_blacklist(step)
            if not ok:
                logger.warning("[Stage 2] Skipping step %d: %s", step.get("step_id"), err)
                step["status"] = "failed"
                step["error"] = err
                state["browser_results"].append({
                    "step_id": step.get("step_id"),
                    "action": step.get("action"),
                    "status": "failed",
                    "error": err,
                })
                await emit_progress(task_id, "step_error", {
                    "step_id": step.get("step_id"),
                    "action": step.get("action"),
                    "error": err,
                })
                continue

            # Emit step_start
            step["status"] = "in_progress"
            await emit_progress(task_id, "step_start", {
                "step_id": step.get("step_id"),
                "action": step.get("action"),
                "description": step.get("description", ""),
            })

            # Execute with per-step retry
            max_retries = settings.browser_max_retries_per_step
            result = None

            for attempt in range(1 + max_retries):
                try:
                    result = await browser.execute_step(step)
                    if result.get("status") == "completed":
                        break
                except Exception as exc:
                    logger.warning(
                        "Step %d attempt %d/%d failed: %s",
                        step.get("step_id"), attempt + 1, 1 + max_retries, exc,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(1.5)
                    else:
                        result = {
                            "step_id": step.get("step_id"),
                            "action": step.get("action"),
                            "status": "failed",
                            "error": str(exc),
                        }

            # Record result
            result = result or {"step_id": step.get("step_id"), "status": "unknown"}
            state["browser_results"].append(result)

            # Emit step_complete or step_error
            if result.get("status") == "completed":
                await emit_progress(task_id, "step_complete", {
                    "step_id": result.get("step_id"),
                    "action": result.get("action"),
                    "result_summary": str(result.get("text", result.get("url", "")))[:200],
                })
            else:
                await emit_progress(task_id, "step_error", {
                    "step_id": result.get("step_id"),
                    "action": result.get("action"),
                    "error": result.get("error", "Unknown error"),
                })

            # Small delay between steps to be polite to websites
            await asyncio.sleep(0.5)

    # Summarize results
    success = sum(1 for r in state["browser_results"] if r.get("status") == "completed")
    fail = len(state["browser_results"]) - success
    logger.info("[Stage 2] Done: %d success, %d failed", success, fail)

    state["stage_progress"] = "extracting"
    return state



