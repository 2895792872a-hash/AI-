"""Chat session & message storage — simple file-based persistence."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

CHAT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chat_data")
os.makedirs(CHAT_DIR, exist_ok=True)
SESSIONS_FILE = os.path.join(CHAT_DIR, "sessions.json")
MESSAGES_DIR = os.path.join(CHAT_DIR, "messages")
os.makedirs(MESSAGES_DIR, exist_ok=True)


def _load_sessions() -> list[dict]:
    if not os.path.exists(SESSIONS_FILE):
        return []
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_sessions(sessions: list[dict]) -> None:
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


def list_sessions() -> list[dict]:
    sessions = _load_sessions()
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def create_session(title: str = "") -> dict:
    session = {
        "id": str(uuid.uuid4())[:8],
        "title": title or "新对话",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    sessions = _load_sessions()
    sessions.append(session)
    _save_sessions(sessions)
    return session


def delete_session(session_id: str) -> bool:
    sessions = _load_sessions()
    sessions = [s for s in sessions if s["id"] != session_id]
    _save_sessions(sessions)
    msg_file = os.path.join(MESSAGES_DIR, f"{session_id}.json")
    if os.path.exists(msg_file):
        os.remove(msg_file)
    return True


def get_messages(session_id: str) -> list[dict]:
    msg_file = os.path.join(MESSAGES_DIR, f"{session_id}.json")
    if not os.path.exists(msg_file):
        return []
    with open(msg_file, "r", encoding="utf-8") as f:
        return json.load(f)


def add_message(session_id: str, role: str, content: str, data: dict = None) -> dict:
    msg = {
        "id": str(uuid.uuid4())[:8],
        "role": role,
        "content": content,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    msg_file = os.path.join(MESSAGES_DIR, f"{session_id}.json")
    messages = []
    if os.path.exists(msg_file):
        with open(msg_file, "r", encoding="utf-8") as f:
            messages = json.load(f)
    messages.append(msg)
    with open(msg_file, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    # Update session timestamp
    sessions = _load_sessions()
    for s in sessions:
        if s["id"] == session_id:
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            # Auto-title from first user message
            if s["title"] == "新对话" and role == "user":
                s["title"] = content[:30]
            break
    _save_sessions(sessions)

    return msg


def update_session_title(session_id: str, title: str) -> None:
    sessions = _load_sessions()
    for s in sessions:
        if s["id"] == session_id:
            s["title"] = title
            break
    _save_sessions(sessions)
