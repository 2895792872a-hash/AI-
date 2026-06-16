"""Stage 3: Information Extraction — structure data from scraped content.

Uses Claude to extract structured information (prices, names, tables, etc.)
from the raw browser results collected in Stage 2.
"""

from __future__ import annotations

import json

from app.agent.state import AgentState
from app.config import settings
from app.core.logging import logger
from app.services.claude_service import create_message

EXTRACTION_SYSTEM_PROMPT = """You are a data extraction specialist. Extract the EXACT information the user wants from web page text.

**How to extract:**
1. Scan the browser results carefully — look for numbers, temperatures, prices, names, dates
2. Pick out the specific data the user asked for
3. If the data appears in multiple places, use the most prominent/certain one
4. For weather: extract temperature, conditions, humidity, wind if visible
5. For search results: extract the top few items with titles and snippets

**Output (JSON only, no markdown):**
```json
{
  "query": "what was asked",
  "data": {"key":"extracted value"},
  "confidence": "high|medium|low",
  "notes": "brief note if data was partial or unclear"
}
```

**IMPORTANT:**
- Extract ONLY what you SEE in the text. Do NOT invent data.
- If you truly cannot find the information, set data:{} and confidence:"low"
- For weather: look for patterns like "XX°C", "晴/雨/多云", temperature numbers
- Output ONLY the JSON object, no markdown, no extra text."""


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
        response = await create_message(
            system=EXTRACTION_SYSTEM_PROMPT,
            user_content=(
                f"**User's task:** {user_task}\n\n"
                f"**Browser results:**\n{results_text}\n\n"
                f"Extract the requested information as JSON."
            ),
            max_tokens=4096,
            temperature=0.1,
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
