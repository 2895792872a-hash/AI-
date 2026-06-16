"""Memory system — persistent JSON storage for tasks, schedules, preferences.

Stored in E:\AI浏览器助手\memory.json (alongside browser_profile).
Never committed to git.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

MEMORY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "memory.json"
)

_lock = threading.Lock()

DEFAULT_MEMORY = {
    "preferences": {
        "favorite_sites": [],
        "search_defaults": {},
    },
    "task_history": [],
    "scheduled_tasks": [],
}


def _load() -> dict:
    """Load memory from disk."""
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_MEMORY)


def _save(data: dict) -> None:
    """Save memory to disk (thread-safe)."""
    with _lock:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ── Task History ──────────────────────────────────────────


def add_history(task: str, summary: str, success: bool) -> None:
    data = _load()
    data["task_history"].insert(0, {
        "task": task,
        "summary": summary[:500],
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 200 entries
    data["task_history"] = data["task_history"][:200]
    _save(data)


def get_history(limit: int = 50) -> list[dict]:
    return _load().get("task_history", [])[:limit]


# ── Scheduled Tasks ───────────────────────────────────────


def add_schedule(user_task: str, interval: str, enabled: bool = True) -> dict:
    """Add a scheduled task. interval: 'hourly' | 'daily' | 'weekly' | cron-like '*/30 * * * *'"""
    import uuid
    data = _load()
    task = {
        "id": str(uuid.uuid4())[:8],
        "user_task": user_task,
        "interval": interval,
        "enabled": enabled,
        "last_run": None,
        "last_result": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("scheduled_tasks", []).append(task)
    _save(data)
    return task


def get_schedules() -> list[dict]:
    return _load().get("scheduled_tasks", [])


def update_schedule(task_id: str, **kwargs) -> dict | None:
    data = _load()
    for t in data.get("scheduled_tasks", []):
        if t["id"] == task_id:
            t.update(kwargs)
            _save(data)
            return t
    return None


def delete_schedule(task_id: str) -> bool:
    data = _load()
    before = len(data.get("scheduled_tasks", []))
    data["scheduled_tasks"] = [t for t in data.get("scheduled_tasks", []) if t["id"] != task_id]
    _save(data)
    return len(data["scheduled_tasks"]) < before


def mark_schedule_run(task_id: str, result: str, success: bool) -> None:
    data = _load()
    for t in data.get("scheduled_tasks", []):
        if t["id"] == task_id:
            t["last_run"] = datetime.now(timezone.utc).isoformat()
            t["last_result"] = result[:2000]
            t["last_success"] = success
            # Append to history
            if "history" not in t:
                t["history"] = []
            t["history"].append({
                "time": t["last_run"],
                "result": result[:2000],
                "success": success,
            })
            # Keep last 20 runs
            if len(t["history"]) > 20:
                t["history"] = t["history"][-20:]
            _save(data)
            return


# ── Preferences ───────────────────────────────────────────


def get_prefs() -> dict:
    return _load().get("preferences", {})


def set_pref(key: str, value: Any) -> None:
    data = _load()
    data.setdefault("preferences", {})[key] = value
    _save(data)
