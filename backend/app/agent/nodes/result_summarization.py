"""Stage 4: Result Summarization — natural language summary for the user.

Synthesizes browser results and extracted data into a clear,
human-readable summary of what was accomplished.
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.config import settings
from app.core.logging import logger
from app.services.claude_service import create_message

SUMMARIZATION_SYSTEM_PROMPT = """You are a helpful assistant that summarizes the results of an automated
browser task. Given the user's original request, the browser actions performed,
and any structured data extracted, write a clear and concise summary.

**Guidelines:**
1. Start with a one-line answer to the user's question.
2. Include the key findings / extracted data.
3. Mention if anything was not found or went wrong.
4. Keep it friendly and natural — like you're reporting back to the user.
5. Be concise — aim for 3-6 sentences unless the data is complex.

**Output format:** Just write the summary text, no JSON or formatting needed.
"""


async def run(state: AgentState) -> AgentState:
    """Generate a natural language summary of the task results."""
    logger.info("[Stage 4] Generating result summary")

    user_task = state.get("user_task", "")
    extracted = state.get("extracted_data", {})
    browser_results = state.get("browser_results", [])

    success_count = sum(1 for r in browser_results if r.get("status") == "completed")
    fail_count = len(browser_results) - success_count

    context_parts = [
        f"**User's original task:** {user_task}",
    ]

    if extracted and extracted.get("data"):
        import json
        context_parts.append(
            f"**Extracted data:**\n```json\n{json.dumps(extracted.get('data', {}), indent=2, ensure_ascii=False)}\n```"
        )
        context_parts.append(f"**Confidence:** {extracted.get('confidence', 'unknown')}")

    context_parts.append(
        f"**Execution summary:** {success_count} steps succeeded, {fail_count} steps failed."
    )

    if fail_count > 0:
        failures = [r for r in browser_results if r.get("status") == "failed"]
        context_parts.append(
            "**Failed steps:** " + ", ".join(
                f"{r.get('action')} ({r.get('error', 'unknown')[:80]})"
                for r in failures
            )
        )

    try:
        response = await create_message(
            system=SUMMARIZATION_SYSTEM_PROMPT,
            user_content="\n\n".join(context_parts),
            max_tokens=2048,
            temperature=0.3,
        )

        summary = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        state["final_summary"] = summary
        logger.info("[Stage 4] Summary generated (%d chars)", len(summary))

    except Exception as exc:
        logger.error("[Stage 4] Summarization failed: %s", exc)
        # Fallback summary without LLM
        parts = [f"Task completed: {user_task}"]
        if extracted and extracted.get("data"):
            import json
            parts.append(f"Data: {json.dumps(extracted['data'], ensure_ascii=False)}")
        parts.append(f"({success_count} steps succeeded, {fail_count} failed)")
        state["final_summary"] = "\n".join(parts)

    state["stage_progress"] = "done"
    return state
