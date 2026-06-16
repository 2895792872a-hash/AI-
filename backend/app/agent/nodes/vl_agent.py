"""Iterative Vision-Language Agent — screenshot → VL decides → act → loop.

Replaces the old "plan-all-then-blindly-execute" pipeline with:
  1. Screenshot current page
  2. Send to Qwen VL with page text
  3. VL decides single next action
  4. Execute action → go to 1
  5. Until VL says "done" or max steps reached
"""

from __future__ import annotations

import base64
import asyncio
from typing import Any

from app.agent.state import AgentState
from app.agent.tools.playwright_executor import managed_browser
from app.config import settings
from app.core.logging import logger
from app.services.vision_service import decide_next_action, detect_stuck
from app.services.progress import emit as emit_progress


MAX_VL_STEPS = 20  # Safety limit (raised for cross-site tasks)
TASK_TIMEOUT_SECONDS = 180  # 3 minute timeout per task


async def _get_current_url(browser, step_num: int) -> str:
    """Get current page URL without side effects."""
    try:
        result = await browser.execute_step({
            "step_id": step_num, "action": "get_url",
            "target_selector": None, "input_value": None, "url": None,
            "description": "", "status": "pending", "result": None, "error": None,
        })
        return result.get("url", "")
    except Exception:
        return ""


async def _safe_exec(browser, step: dict, task_id: str = "unknown") -> dict:
    """Execute a browser step with type-checked return value."""
    result = await browser.execute_step(step)
    if not isinstance(result, dict):
        logger.error("_safe_exec got non-dict (task=%s): type=%s val=%s", task_id, type(result), str(result)[:200])
        return {"status": "failed", "error": f"Unexpected return type: {type(result).__name__}"}
    if result.get("status") == "failed":
        logger.error("_safe_exec step failed (task=%s): action=%s error=%s",
                      task_id, step.get("action"), result.get("error", "")[:200])
    return result


async def _get_start_url(user_task: str) -> str | None:
    """Pre-flight: ask text LLM for the best starting URL."""
    # Known site mappings to avoid wrong URLs
    site_map = {
        "boss直聘": "https://www.zhipin.com",
        "boss": "https://www.zhipin.com",
        "zhipin": "https://www.zhipin.com",
        "猎聘": "https://www.liepin.com",
        "拉勾": "https://www.lagou.com",
        "淘宝": "https://www.taobao.com",
        "天猫": "https://www.tmall.com",
        "拼多多": "https://www.pinduoduo.com",
        "京东": "https://www.jd.com",
        "微博": "https://weibo.com",
        "小红书": "https://www.xiaohongshu.com",
        "抖音": "https://www.douyin.com",
    }
    task_lower = user_task.lower()
    for key, url in site_map.items():
        if key in task_lower:
            return url

    try:
        from app.services.claude_service import get_text_response
        url_hint = await get_text_response(
            system="Given a user's browser task, return the BEST starting URL. Reply ONLY with the URL, nothing else. For known sites, prefer direct pages (e.g. book.douban.com for Douban books, item.jd.com for JD products).",
            user_content=user_task,
            max_tokens=200,
            temperature=0,
        )
        url = url_hint.strip()
        if url.startswith("http"):
            return url
    except Exception:
        pass
    return None


async def run(state: AgentState) -> AgentState:
    """Run the VL-guided iterative browser agent."""
    user_task = state["user_task"]
    task_id = state.get("task_id", "unknown")
    step_history: list[str] = []
    all_extracts: list[str] = []

    # Pre-flight: figure out starting URL
    start_url = await _get_start_url(user_task)
    if start_url:
        step_history.append(f"[0] Pre-flight: start at {start_url}")
        logger.info("VL pre-flight URL: %s", start_url)

    await emit_progress(task_id, "stage_change", {
        "stage": "operating", "message": "启动视觉 Agent...",
    })

    async with managed_browser() as browser:
        # Navigate to starting URL first
        if start_url:
            await _safe_exec(browser, {
                "step_id": 0, "action": "navigate", "url": start_url,
                "target_selector": None, "input_value": None,
                "description": f"Open {start_url}", "status": "pending",
                "result": None, "error": None,
            })
            await asyncio.sleep(1.5)
        for step_num in range(1, MAX_VL_STEPS + 1):
            await emit_progress(task_id, "stage_change", {
                "stage": "operating",
                "message": f"视觉分析第 {step_num} 步...",
            })

            # Check cancellation
            from app.api.tasks import is_cancelled
            if is_cancelled(task_id):
                logger.info("Task %s cancelled by user", task_id)
                break

            # Check off-track: 5+ same page extracts with no progress
            if len(step_history) >= 5:
                recent = step_history[-5:]
                same_page = all("extract" in h or "same page" in h.lower() for h in recent)
                if same_page and all_extracts and len(set(a[:100] for a in all_extracts[-5:])) <= 2:
                    logger.info("Task appears stuck on same page, auto-terminating")
                    break

            try:
                # 1. Take screenshot (viewport-only for speed)
                ss_result = await _safe_exec(browser, {
                    "step_id": step_num, "action": "screenshot",
                    "target_selector": None, "input_value": "viewport", "url": None,
                    "description": "screenshot for VL", "status": "pending",
                    "result": None, "error": None,
                })
                screenshot_b64 = ss_result.get("image_base64", "")
                # Emit to frontend live viewport (viewport-size, much smaller than full-page)
                await emit_progress(task_id, "screenshot_update", {
                    "image_base64": screenshot_b64,
                    "url": ss_result.get("url", ""),
                })

                # 2. Extract page text for VL context
                extract_result = await _safe_exec(browser, {
                    "step_id": step_num, "action": "extract",
                    "target_selector": None, "input_value": None, "url": None,
                    "description": "extract for VL", "status": "pending",
                    "result": None, "error": None,
                })
                page_text = extract_result.get("text", "")
                # Accumulate unique page content (now PAGE CONTENT is first, before INTERACTIVE ELEMENTS)
                if "=== INTERACTIVE ELEMENTS ===" in page_text:
                    page_content = page_text.split("=== INTERACTIVE ELEMENTS ===")[0].replace("=== PAGE CONTENT ===\n", "")
                else:
                    page_content = page_text
                if page_content not in all_extracts:
                    all_extracts.append(page_content[:3000])
                logger.info("VL Step %d extract: %d chars, preview: %s",
                            step_num, len(page_text), page_text[:150])

                # 3. Detect if VL is stuck repeating the same action
                stuck = detect_stuck(step_history)

                await emit_progress(task_id, "step_start", {
                    "step_id": step_num, "action": "vl_think",
                    "description": "VL 分析截图中...",
                })

                decision = await decide_next_action(
                    screenshot_base64=screenshot_b64,
                    page_text=page_text,
                    user_task=user_task,
                    step_history=step_history,
                    stuck_info=stuck,
                )

                thinking = decision.get("thinking", "")[:200]
                is_done = decision.get("done", False)
                action = decision.get("action", {})
                page_has = decision.get("page_has", "")

                logger.info("VL Step %d: %s | done=%s | action=%s | role=%s name=%s",
                            step_num, thinking, is_done, action.get("action"),
                            action.get("role", "-"), action.get("name", "-"))

                await emit_progress(task_id, "step_complete", {
                    "step_id": step_num, "action": "vl_think",
                    "result_summary": f"🤔 {thinking}",
                })

                step_history.append(f"[{step_num}] {action.get('action')}: {thinking}")
                if page_has:
                    all_extracts.append(page_has)

                # 4. Check if done
                if is_done:
                    result_text = decision.get("result", "") or thinking
                    state["stage_progress"] = "done"
                    state["final_summary"] = result_text
                    state["extracted_data"] = {"raw": result_text}

                    await emit_progress(task_id, "done", {
                        "summary": result_text,
                        "total_steps": step_num,
                        "success_count": step_num,
                        "fail_count": 0,
                        "data": state["extracted_data"],
                    })
                    return state

                # 5. Execute the action
                action_type = action.get("action", "extract")
                url_before = await _get_current_url(browser, step_num) if action_type in ("click", "navigate") else ""

                if action_type == "navigate":
                    url = action.get("url", "")
                    if url:
                        await _safe_exec(browser, {
                            "step_id": step_num, "action": "navigate", "url": url,
                            "target_selector": None, "input_value": None,
                            "description": f"VL: {thinking}", "status": "pending",
                            "result": None, "error": None,
                        })
                        await asyncio.sleep(1.5)

                elif action_type == "click":
                    role = action.get("role", "")
                    name = action.get("name", "")
                    await _safe_exec(browser, {
                        "step_id": step_num, "action": "accessibility_click",
                        "role": role, "name": name,
                        "url": None, "target_selector": None, "input_value": None,
                        "description": f"Click {role} '{name}'", "status": "pending",
                        "result": None, "error": None,
                    })
                    await emit_progress(task_id, "step_complete", {
                        "step_id": step_num, "action": "click",
                        "result_summary": f"👆 点击 {role} '{name}'",
                    })

                elif action_type == "hover":
                    role = action.get("role", "")
                    name = action.get("name", "")
                    await _safe_exec(browser, {
                        "step_id": step_num, "action": "accessibility_click",
                        "role": role, "name": name,
                        "url": None, "target_selector": None, "input_value": None,
                        "description": f"Hover {role} '{name}'", "status": "pending",
                        "result": None, "error": None,
                    })
                    await emit_progress(task_id, "step_complete", {
                        "step_id": step_num, "action": "hover",
                        "result_summary": f"🖱️ 悬停 {role} '{name}'",
                    })

                elif action_type == "type":
                    text = action.get("text", "")
                    await _safe_exec(browser, {
                        "step_id": step_num, "action": "type",
                        "target_selector": None, "input_value": text,
                        "url": None,
                        "description": "搜索",  # hint for find_input
                        "status": "pending", "result": None, "error": None,
                    })
                    await emit_progress(task_id, "step_complete", {
                        "step_id": step_num, "action": "type",
                        "result_summary": f"⌨️ 输入: {text[:50]}",
                    })

                elif action_type == "scroll":
                    direction = action.get("direction", "down")
                    await _safe_exec(browser, {
                        "step_id": step_num, "action": "scroll",
                        "input_value": direction, "url": None,
                        "target_selector": None, "description": f"VL: {thinking}",
                        "status": "pending", "result": None, "error": None,
                    })

                # Check if URL actually changed after action
                if url_before:
                    for _ in range(10):
                        await asyncio.sleep(0.5)
                        new_url = await _get_current_url(browser, step_num)
                        if new_url and new_url != url_before:
                            logger.info("Navigated: %s → %s", url_before[:50], new_url[:50])
                            break
                    else:
                        logger.info("URL stayed: %s", url_before[:50])
                elif action_type == "type":
                    import random as _random
                    await asyncio.sleep(_random.uniform(1.5, 3.5))
                else:
                    await asyncio.sleep(1.5)

            except Exception as e:
                import traceback
                logger.error("VL step %d error: %s\n%s", step_num, e, traceback.format_exc())
                step_history.append(f"[{step_num}] ERROR: {e}")
                # If browser worker died, break out early
                if "not running" in str(e) or "BrokenPipe" in str(type(e).__name__):
                    break
                await emit_progress(task_id, "step_error", {
                    "step_id": step_num, "action": "vl_step",
                    "error": str(e)[:100],
                })

    # Max steps reached — return best available data
    best_data = "\n".join(all_extracts[-5:]) if all_extracts else ""
    state["stage_progress"] = "done"
    state["final_summary"] = best_data[:2000] if best_data else f"执行了 {MAX_VL_STEPS} 步，未能获取有效数据。"
    state["extracted_data"] = {"steps": MAX_VL_STEPS, "findings": all_extracts}
    await emit_progress(task_id, "done", {
        "summary": state["final_summary"],
        "total_steps": MAX_VL_STEPS,
        "success_count": MAX_VL_STEPS,
        "fail_count": 0,
    })
    return state


async def _verify_and_extract(browser, user_task: str, task_id: str, all_extracts: list = None) -> dict:
    """Combine accumulated page content + final extract → format with text LLM."""
    await emit_progress(task_id, "stage_change", {
        "stage": "extracting", "message": "汇总数据中...",
    })

    # 1. Final extract from current page
    ext = await _safe_exec(browser, {
        "step_id": 999, "action": "extract", "target_selector": None,
        "input_value": None, "url": None, "description": "final extract",
        "status": "pending", "result": None, "error": None,
    })

    # 2. Combine: accumulated data from all steps + final page
    accumulated = (all_extracts or []) + [ext.get("text", "")]
    # Deduplicate by content hash, not prefix (different pages may have same section headers)
    import hashlib
    seen = set()
    unique = []
    for chunk in accumulated:
        key = hashlib.md5(chunk.encode()).hexdigest()[:16]
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    raw_text = "\n\n=== NEXT PAGE ===\n\n".join(unique)

    # 3. Send to text LLM for formatting
    from app.services.claude_service import get_text_response

    formatted = await get_text_response(
        system="""You are a data FORMATTER only — NOT a knowledge base. You have NO knowledge of your own.

**IRON RULES:**
1. You can ONLY use text that appears verbatim in the SOURCE TEXT below.
2. If you don't see it, write "[未找到]" — NEVER guess, NEVER invent.
3. Cite the exact source text snippet for EVERY claim.
4. The summary MUST only rephrase data that was found above. Add nothing new.

**Output:**
```
## 提取的数据
- 数据: 实际值 (来源: "原文片段...")
## 总结
[仅基于以上数据的客观重述，不添加任何外部知识]
```""",
        user_content=f"**用户任务:** {user_task}\n\n**页面原始文本:**\n{raw_text[:6000]}\n\n请提取并格式化相关数据，严格只使用以上文本中的内容。",
        max_tokens=1500,
        temperature=0.0,
    )

    return {
        "raw": raw_text[:3000],
        "formatted": formatted,
    }
