"""Vision service — sends screenshot + DOM text to Qwen VL for visual decisions."""

from __future__ import annotations

import json
import re
from typing import Any
from dashscope import MultiModalConversation

from app.config import settings
from app.core.logging import logger

VL_SYSTEM_PROMPT = """You are a browser agent. Look at the screenshot, decide the next action.

**Actions:**
- click: {"action":"click","role":"link","name":"Video Title"}
- type: {"action":"type","role":"textbox","name":"搜索","text":"keyword"}
- navigate: {"action":"navigate","url":"https://..."}
- scroll: {"action":"scroll","direction":"down"}

**CROSS-SITE TASKS:** If the user wants to compare multiple sites:
1. Visit site A → extract key info → briefly note findings
2. Navigate to site B → extract key info
3. Set done:true with COMPARISON of both sites

**RULES:**
1. SCREENSHOT IS GROUND TRUTH.
2. For comparison tasks: visit EACH site, note findings, then compare.
3. If stuck (3 same actions) — try completely different approach.
4. Single line JSON. No markdown.

Example:
{"thinking":"On GitHub Trending, top project is IPTV. Now need to visit books.toscrape.","done":false,"action":{"action":"navigate","url":"http://books.toscrape.com"}}
{"thinking":"GitHub has dev tools trending, books site has fiction. They serve completely different audiences.","done":true,"result":"GitHub Trending shows developer tools (iptv-org/iptv), books.toscrape shows Mystery novels. Different audiences and content types."}"""


def _parse_vl_json(raw: str) -> dict[str, Any]:
    """Robust JSON extraction from VL model responses.

    Tries multiple strategies in order:
    1. Direct parse after stripping markdown fences
    2. Extract JSON object by brace matching (ignoring braces inside strings)
    3. Extract JSON object by regex on common patterns
    """
    text = raw.strip()

    if not text:
        return _fallback("Empty response")

    # ── Strategy 1: strip markdown fences, try direct parse ──
    # Remove ```json ... ``` anywhere in the text
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', text)
    cleaned = re.sub(r'\n?```', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # ── Strategy 2: find JSON between first { and matching } ──
    # Use a simple state machine that ignores braces inside strings
    start = cleaned.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(cleaned)):
            c = cleaned[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start:i+1])
                    except json.JSONDecodeError:
                        break

    # ── Strategy 3: try to fix common JSON errors ──
    # Unescaped newlines in string values, trailing commas, etc.
    if start >= 0:
        json_candidate = cleaned[start:]
        # Remove trailing commas before closing } or ]
        json_candidate = re.sub(r',\s*([}\]])', r'\1', json_candidate)
        # Fix single quotes
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass

    # ── Strategy 4: extract thinking and action separately ──
    thinking_match = re.search(r'"thinking"\s*:\s*"([^"]*)"', text)
    action_match = re.search(r'"action"\s*:\s*\{([^}]+)\}', text)
    done_match = re.search(r'"done"\s*:\s*(true|false)', text)

    if thinking_match or action_match:
        result = {}
        result["thinking"] = thinking_match.group(1) if thinking_match else text[:200]
        result["done"] = done_match.group(1) == "true" if done_match else False
        if action_match:
            action_str = "{" + action_match.group(1) + "}"
            try:
                result["action"] = json.loads(action_str)
            except json.JSONDecodeError:
                result["action"] = {"action": "extract"}
        else:
            result["action"] = {"action": "extract"}
        logger.info("VL parsed via regex fallback: done=%s action=%s",
                     result.get("done"), result.get("action", {}).get("action"))
        return result

    return _fallback(text[:200])


def _fallback(thinking: str) -> dict[str, Any]:
    """Last resort fallback — not extract, but navigate away or report."""
    return {
        "thinking": thinking,
        "done": True,
        "result": "无法解析页面内容。页面可能加载失败或结构异常。",
        "action": {"action": "extract"},
    }


async def decide_next_action(
    screenshot_base64: str,
    page_text: str,
    user_task: str,
    step_history: list[str],
    stuck_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send screenshot to Qwen VL for coordinate-based action decisions.

    The VL model looks at the screenshot as pixels and returns (x,y) coordinates
    for where to click. No DOM injection needed.
    """

    history_text = "\n".join(step_history[-8:]) if step_history else "(first step)"

    stuck_warning = ""
    if stuck_info:
        stuck_warning = (
            f"\n\n**⚠️ STUCK DETECTION:** You have tried `{stuck_info.get('action')}` "
            f"{stuck_info.get('count')} times in a row with no progress. "
            f"The page is not changing. Your previous attempt FAILED. "
            f"You MUST try a COMPLETELY DIFFERENT approach now. "
            f"If there's an error, blocked account, or login wall — STOP and report it."
        )

    last_error = ""
    for h in reversed(step_history[-3:]):
        if "ERROR" in h or "failed" in h.lower() or "失败" in h:
            last_error = f"\n\n**LAST ERROR:** {h[-300:]}"
            break

    user_message = (
        f"**Task:** {user_task}\n\n"
        f"**Recent steps:**\n{history_text}"
        f"{stuck_warning}"
        f"{last_error}\n\n"
        f"**Page content:**\n{page_text[:4000]}"
    )

    messages = [{
        "role": "user",
        "content": [
            {"image": f"data:image/png;base64,{screenshot_base64}"},
            {"text": f"{VL_SYSTEM_PROMPT}\n\n{user_message}"},
        ],
    }]

    # ── Try up to 2 times with JSON format feedback ──
    for attempt in range(2):
        response = MultiModalConversation.call(
            model="qwen-vl-max",
            messages=messages,
            api_key=settings.vl_api_key or settings.llm_api_key,
        )

        raw = ""
        if response.output and response.output.choices:
            content = response.output.choices[0].message.content
            if isinstance(content, list):
                raw = "".join(b.get("text", "") for b in content if isinstance(b, dict))
            else:
                raw = str(content)

        logger.debug("VL raw response (attempt %d): %s", attempt + 1, raw[:300])

        decision = _parse_vl_json(raw)

        # Check if parsing was successful beyond fallback
        thinking = decision.get("thinking", "")
        action = decision.get("action", {})

        if action.get("action") != "extract" or decision.get("done"):
            return decision

        # First attempt failed — add correction feedback
        if attempt == 0:
            logger.warning("VL bad JSON on attempt 1, retrying with format correction")
            messages.append({
                "role": "assistant",
                "content": [{"text": raw}],
            })
            messages.append({
                "role": "user",
                "content": [{"text": (
                    "Your last response was not valid JSON. REPLY WITH A SINGLE LINE OF JSON ONLY. "
                    "No markdown, no backticks, no extra text. Example format:\n"
                    '{"thinking":"I see a search box","done":false,"action":{"action":"click","index":5}}'
                )}],
            })

    return decision


def detect_stuck(step_history: list[str], threshold: int = 3) -> dict[str, Any] | None:
    """Check if the VL agent is repeating the same action.

    Returns stuck_info dict if stuck, None otherwise.
    """
    if len(step_history) < threshold:
        return None

    recent = step_history[-threshold:]

    # Extract action type from recent history entries
    actions = []
    for entry in recent:
        # Format: "[N] action_type: thinking..."
        match = re.match(r'\[\d+\]\s*(\w+)\s*:', entry)
        if match:
            actions.append(match.group(1))

    if len(actions) >= threshold and len(set(actions)) == 1:
        same_action = actions[0]
        return {
            "action": same_action,
            "count": len(actions),
        }
    return None
