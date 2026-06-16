"""Stage 1: Task Parsing — decompose user intent into browser action steps.

Uses Claude to convert a natural-language task (e.g. "Find the price of
iPhone 15 on Amazon") into an ordered list of BrowserStep dictionaries.
Each step passes through the security module before being accepted.
"""

from __future__ import annotations

import json

from app.agent.state import AgentState, BrowserStep
from app.agent.tools.security import validate_all_steps
from app.config import settings
from app.core.logging import logger
from app.services.claude_service import create_message

TASK_PARSING_SYSTEM_PROMPT = """You are a browser automation planner. Decompose the user's task into minimal browser steps.

**Actions:** navigate | type | click | scroll | extract | screenshot

**Output (JSON only):**
```json
{"steps": [{"step_id":1,"action":"navigate","url":"https://...","target_selector":null,"input_value":null,"description":"..."}]}
```

**CRITICAL RULES:**
1. MAX 4 STEPS. Be concise.
2. Search: navigate → type(Enter is auto-pressed, NO click needed) → extract
3. Shopping: navigate → type → extract results directly
4. type action: type FULL query at once. After typing, Enter is auto-pressed.
5. DO NOT add a separate "click search button" step — it's automatic.
6. Use generic selectors or null — Playwright has smart fallbacks.
7. ONLY output valid JSON, no markdown, no extra text."""


async def run(state: AgentState) -> AgentState:
    """Decompose user_task into validated BrowserStep list via Claude."""
    logger.info(
        "[Stage 1] Parsing task: '%s...' (retry=%d)",
        state["user_task"][:80],
        state.get("_task_retry_count", 0),
    )

    retry_count = state.get("_task_retry_count", 0)
    retry_hint = ""
    if retry_count > 0:
        retry_hint = (
            f"\n\n[RETRY ATTEMPT {retry_count}] "
            "Your previous output was empty or invalid. "
            "Make sure to output valid JSON with a 'steps' array."
        )

    try:
        response = await create_message(
            system=TASK_PARSING_SYSTEM_PROMPT,
            user_content=state["user_task"] + retry_hint,
            max_tokens=4096,
            temperature=0.1,
        )

        raw_text = "\n".join(
            block.text for block in response.content if block.type == "text"
        )

        # Try to extract JSON from the response
        steps = _parse_steps_json(raw_text)

        # Security validation
        validated = validate_all_steps(steps)

        # Enforce max steps
        if len(validated) > settings.max_steps_per_task:
            logger.warning(
                "Truncating steps from %d to %d", len(validated), settings.max_steps_per_task
            )
            validated = validated[: settings.max_steps_per_task]

        # If no valid steps were produced, record retry
        if not validated:
            logger.warning("[Stage 1] LLM returned no valid steps")
            retry = state.get("_task_retry_count", 0)
            if retry < 3:
                state["_task_retry_count"] = retry + 1
                state["parsed_steps"] = []
            else:
                state["error"] = "Task parsing failed: LLM could not produce valid steps"
            return state

        state["parsed_steps"] = validated
        state["stage_progress"] = "operating"

        logger.info("[Stage 1] Parsed %d valid steps", len(validated))
        return state

    except Exception as exc:
        logger.error("[Stage 1] Task parsing error: %s", exc)
        retry = state.get("_task_retry_count", 0)
        if retry < 3:
            state["_task_retry_count"] = retry + 1
            state["parsed_steps"] = []
        else:
            state["error"] = f"Task parsing failed: {exc}"
        return state


def _parse_steps_json(raw: str) -> list[BrowserStep]:
    """Extract and parse steps from Claude's JSON response.

    Handles cases where Claude wraps JSON in markdown code blocks.
    """
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening ```json ... ```
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        import re
        match = re.search(r'\{.*"steps"\s*:\s*\[.*\]\s*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            logger.warning("Could not parse JSON from: %s", text[:200])
            return []

    raw_steps = data.get("steps", []) if isinstance(data, dict) else []
    steps: list[BrowserStep] = []
    for i, s in enumerate(raw_steps):
        step = BrowserStep(
            step_id=s.get("step_id", i + 1),
            action=s.get("action", ""),
            target_selector=s.get("target_selector"),
            input_value=s.get("input_value"),
            url=s.get("url"),
            description=s.get("description", f"Step {i + 1}"),
            status="pending",
            result=None,
            error=None,
        )
        steps.append(step)

    return steps
