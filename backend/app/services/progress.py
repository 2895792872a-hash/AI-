"""Progress callback registry — decouples agent nodes from API layer.

Nodes emit events via emit_progress(task_id, event_type, data).
The API layer registers an async handler via register_callback(task_id, handler).
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

ProgressHandler = Callable[[str, dict[str, Any]], Awaitable[None]]

_registry: dict[str, ProgressHandler] = {}


def register(task_id: str, handler: ProgressHandler) -> None:
    """Register a progress handler for a task."""
    _registry[task_id] = handler


def unregister(task_id: str) -> None:
    """Remove a task's progress handler."""
    _registry.pop(task_id, None)


async def emit(task_id: str, event_type: str, data: dict[str, Any]) -> None:
    """Emit a progress event to the registered handler, if any."""
    handler = _registry.get(task_id)
    if handler:
        try:
            await handler(event_type, data)
        except Exception:
            pass
