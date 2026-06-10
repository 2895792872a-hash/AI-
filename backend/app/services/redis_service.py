"""Redis service — async client wrapper for task state, checkpoints, and pub/sub.

Provides:
  - Task state CRUD (hash-based, with TTL)
  - Step result storage (per-step hashes)
  - Pub/Sub channels for SSE event streaming
  - Checkpoint persistence for LangGraph breakpoint recovery
"""

from __future__ import annotations

import json
import asyncio
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from app.config import settings
from app.core.logging import logger

# ── Client ───────────────────────────────────────────────────

_pool: aioredis.Redis | None = None

TASK_TTL_SECONDS = 86_400  # 24 hours
STEP_TTL_SECONDS = 86_400


async def get_redis() -> aioredis.Redis:
    """Return (or create) the async Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        # Verify connection
        await _pool.ping()
        logger.info("Redis connected: %s", settings.redis_url)
    return _pool


async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Redis connection closed")


# ── Key helpers ──────────────────────────────────────────────


def _task_key(task_id: str) -> str:
    return f"task:{task_id}:state"


def _step_key(task_id: str, step_id: int) -> str:
    return f"task:{task_id}:step:{step_id}"


def _channel(task_id: str) -> str:
    return f"task:{task_id}:events"


# ── Task State ───────────────────────────────────────────────


async def set_task_state(task_id: str, state: dict[str, Any]) -> None:
    """Store full task state as a Redis hash."""
    r = await get_redis()
    key = _task_key(task_id)
    flat = {k: json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            for k, v in state.items()}
    await r.hset(key, mapping=flat)
    await r.expire(key, TASK_TTL_SECONDS)


async def get_task_state(task_id: str) -> dict[str, Any] | None:
    """Retrieve task state from Redis."""
    r = await get_redis()
    key = _task_key(task_id)
    raw = await r.hgetall(key)
    if not raw:
        return None
    # Parse JSON fields
    parsed: dict[str, Any] = {}
    for k, v in raw.items():
        try:
            parsed[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            parsed[k] = v
    return parsed


async def update_task_field(task_id: str, field: str, value: Any) -> None:
    """Update a single field in the task state hash."""
    r = await get_redis()
    key = _task_key(task_id)
    raw = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    await r.hset(key, field, raw)


# ── Step Results ─────────────────────────────────────────────


async def set_step_result(task_id: str, step_id: int, result: dict[str, Any]) -> None:
    """Store a single step's result."""
    r = await get_redis()
    key = _step_key(task_id, step_id)
    flat = {k: json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            for k, v in result.items()}
    await r.hset(key, mapping=flat)
    await r.expire(key, STEP_TTL_SECONDS)


async def get_step_result(task_id: str, step_id: int) -> dict[str, Any] | None:
    """Retrieve a single step's result."""
    r = await get_redis()
    key = _step_key(task_id, step_id)
    raw = await r.hgetall(key)
    if not raw:
        return None
    parsed: dict[str, Any] = {}
    for k, v in raw.items():
        try:
            parsed[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            parsed[k] = v
    return parsed


# ── Pub/Sub for SSE ──────────────────────────────────────────


async def publish_event(task_id: str, event: dict[str, Any]) -> None:
    """Publish a progress event to the task's SSE channel."""
    r = await get_redis()
    channel = _channel(task_id)
    payload = json.dumps(event, ensure_ascii=False)
    await r.publish(channel, payload)


async def subscribe_events(task_id: str) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to real-time events for a task.

    Yields parsed event dicts. The caller must handle cleanup.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    channel = _channel(task_id)
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except json.JSONDecodeError:
                    logger.warning("Invalid SSE payload: %s", message.get("data", "")[:100])
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


# ── Health ───────────────────────────────────────────────────


async def health_check() -> bool:
    """Return True if Redis is reachable."""
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False
