"""Stage 3: Information Extraction — structure data from scraped content.

Uses Claude to extract structured information (prices, names, tables, etc.)
from the raw browser results collected in Stage 2.
"""

from __future__ import annotations

import json

from app.agent.state import AgentState
from app.config import settings
from app.core.logging import logger
from app.services.claude_service import get_client

EXTRACTION_SYSTEM_PROMPT = """You are a data extraction specialist. Given raw text extracted from web pages,
pull out the key structured information the user is looking for.

**Instructions:**
1. Read the user's original task to understand what data they want.
2. Read the browser results — these contain scraped text from web pages.
3. Extract the relevant data into a clean JSON object.
4. Only include information that is actually present in the results.
5. If you can't find the requested information, set the value to null.
6. IMPORTANT: Output only valid JSON, no other text.

**Output format:**
```json
{
  "query": "what the user asked for",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "confidence": "high|medium|low",
  "notes": "optional clarification about the data"
}
```
"""


async def run(state: AgentState) -> AgentState:
    """Extract structured data from browser results via Claude."""
    logger.info("[Stage 3] Extracting structured information")

    browser_results = state.get("browser_results", [])
    user_task = state.get("user_task", "")

    if not browser_results:
        logger.info("[Stage 3] No browser results to extract from")
        state["stage_progress"] = "summarizing"
        state["extracted_data"] = {"query": user_task, "data": {}, "confidence": "low"}
        return state

    # Build context from browser results
    results_text = _format_browser_results(browser_results)

    try:
        client = get_client()
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            temperature=0.1,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"**User's task:** {user_task}\n\n"
                        f"**Browser results:**\n{results_text}\n\n"
                        f"Extract the requested information as JSON."
                    ),
                }
            ],
        )

        raw_text = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        extracted = _parse_json(raw_text)
        state["extracted_data"] = extracted
        logger.info("[Stage 3] Extraction complete, confidence=%s", extracted.get("confidence"))

    except Exception as exc:
        logger.error("[Stage 3] Extraction failed: %s", exc)
        state["extracted_data"] = {
            "query": user_task,
            "data": {},
            "confidence": "low",
            "error": str(exc),
        }

    state["stage_progress"] = "summarizing"
    return state


def _format_browser_results(results: list[dict]) -> str:
    """Format browser results into a readable text block for the LLM."""
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        status = r.get("status", "?")
        action = r.get("action", "?")
        text = r.get("text", "") or r.get("url", "") or ""
        error = r.get("error", "")
        line = f"[{i}] {action} ({status})"
        if text:
            line += f"\n    Content: {text[:500]}"
        if error:
            line += f"\n    Error: {error}"
        lines.append(line)
    return "\n".join(lines)


def _parse_json(raw: str) -> dict:
    """Parse JSON from LLM output, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse extraction JSON: %s", text[:200])
        return {"data": {}, "confidence": "low", "raw": text}
