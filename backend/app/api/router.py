"""API router aggregation — mounts all sub-routers."""

from fastapi import APIRouter, HTTPException

from app.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tasks_router)


@api_router.get("/health")
async def health_check():
    """Liveness/readiness check."""
    return {"status": "ok", "service": "ai-browser-assistant"}


# ── Schedule endpoints ─────────────────────────────────────


@api_router.post("/schedules")
async def create_schedule(request: dict):
    from app.services.memory import add_schedule
    task = add_schedule(request["user_task"], request.get("interval", "daily"))
    return {"status": "ok", "task": task}


@api_router.get("/schedules")
async def list_schedules():
    from app.services.memory import get_schedules
    return {"schedules": get_schedules()}


@api_router.delete("/schedules/{task_id}")
async def remove_schedule(task_id: str):
    from app.services.memory import delete_schedule
    ok = delete_schedule(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"status": "deleted"}


@api_router.get("/history")
async def list_history(limit: int = 20):
    from app.services.memory import get_history
    return {"history": get_history(limit)}


# ── Chat endpoints ─────────────────────────────────────────


@api_router.get("/chat/sessions")
async def list_chat_sessions():
    from app.services.chat_service import list_sessions
    return {"sessions": list_sessions()}


@api_router.post("/chat/sessions")
async def create_chat_session(request: dict):
    from app.services.chat_service import create_session
    return create_session(request.get("title", ""))


@api_router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    from app.services.chat_service import delete_session
    ok = delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404)
    return {"status": "deleted"}


@api_router.get("/chat/sessions/{session_id}/messages")
async def get_chat_messages(session_id: str):
    from app.services.chat_service import get_messages
    return {"messages": get_messages(session_id)}


@api_router.post("/chat/sessions/{session_id}/messages")
async def send_chat_message(session_id: str, request: dict):
    from app.services.chat_service import add_message, get_messages
    from app.services.claude_service import get_text_response
    import asyncio

    user_msg_text = request.get("content", "")
    if not user_msg_text:
        raise HTTPException(status_code=400, detail="Empty message")

    # Save user message
    add_message(session_id, "user", user_msg_text)

    # ── Intent detection: chat or browser task? ──
    is_browser = _needs_browser(user_msg_text)

    if is_browser:
        import uuid
        browser_task_id = str(uuid.uuid4())[:8]
        status_msg = add_message(session_id, "assistant",
            "正在操作浏览器，请稍候…",
            {"status": "browser_started", "task": user_msg_text, "task_id": browser_task_id})
        asyncio.create_task(_run_browser_for_chat(session_id, user_msg_text, browser_task_id))
        return status_msg

    # ── Normal chat — call LLM ──
    history = get_messages(session_id)
    context = "\n".join(
        f"{'用户' if m['role']=='user' else '助手'}: {m['content']}"
        for m in history[-10:]
    )

    try:
        reply = await get_text_response(
            system="你是一个AI浏览器助手。可以回答问题、提供建议、解释概念。回答简洁友好。",
            user_content=f"对话历史:\n{context}\n\n用户最新消息: {user_msg_text}\n\n请回复用户。",
            max_tokens=800,
            temperature=0.7,
        )
    except Exception:
        reply = "抱歉，我暂时无法回复。请稍后再试。"

    ai_msg = add_message(session_id, "assistant", reply)
    return ai_msg


def _needs_browser(user_task: str) -> bool:
    """Quick check: does this task need browser automation?"""
    browser_keywords = [
        "打开", "搜索", "帮我", "列出", "查找", "找到", "点进", "点进去",
        "看看", "浏览", "查看", "进入", "翻到", "下一页", "价格", "对比",
        "查一下", "查", "显示", "告诉", "搜", "豆瓣", "b站", "github",
        "open", "search", "go to", "find", "list", "click", "browse",
        "http://", "https://", ".com", ".cn",
    ]
    task_lower = user_task.lower()
    score = sum(1 for kw in browser_keywords if kw.lower() in task_lower)

    if len(user_task) < 6:
        return False
    if score >= 1:
        return True
    if any(u in user_task for u in ["http://", "https://", ".com/", ".cn/"]):
        return True
    return False


async def _run_browser_for_chat(session_id: str, user_task: str, task_id: str):
    """Run VL agent and save result as chat message."""
    from app.services.chat_service import add_message
    from app.agent.graph import get_graph
    from app.agent.state import create_initial_state
    from app.services.progress import register
    from app.api.tasks import _emit_event

    # Register progress handler so SSE events reach the frontend
    register(task_id, lambda event_type, data: _emit_event(task_id, {"type": event_type, **data}))

    def _classify_error(text: str) -> str:
        """Give user-friendly error with actionable suggestion."""
        t = text.lower()
        if "timeout" in t or "connection" in t or "timed_out" in t:
            return f"{text[:200]}｜💡 建议：检查网络连接，或确认目标网站是否可访问"
        if "blocked" in t or "denied" in t or "频繁" in t or "限制" in t:
            return f"{text[:200]}｜💡 建议：网站开启了反爬保护，可尝试降低访问频率或手动登录"
        if "login" in t or "登录" in t:
            return f"{text[:200]}｜💡 建议：该网站需要登录，请先手动登录后再试"
        if "not found" in t or "404" in t or "不存在" in t:
            return f"{text[:200]}｜💡 建议：目标页面不存在，检查网址是否正确"
        if "未找到" in text or "提取" in text:
            return f"{text[:200]}｜💡 建议：页面可能为空或数据加载失败，可尝试重试"
        return f"{text[:200]}"

    summary = "任务完成，但未能提取到有效数据。"
    try:
        graph = get_graph()
        state = create_initial_state(user_task, task_id)
        result = await graph.ainvoke(state, {"configurable": {"thread_id": task_id}})
        summary = result.get("final_summary", summary)
        error = result.get("error")
        if error:
            summary = _classify_error(error[:300])
    except Exception as e:
        summary = _classify_error(str(e)[:300])
    finally:
        add_message(session_id, "assistant", summary,
                    {"status": "browser_done", "task": user_task, "task_id": task_id})
