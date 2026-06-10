"""Claude API service — Anthropic async client wrapper.

Provides a thin, typed layer over the Anthropic Python SDK for:
- Tool-use loops (Claude calls browser tools repeatedly until done)
- Structured JSON output parsing
- Connection pooling and retry via the SDK's built-in mechanisms
"""

from __future__ import annotations

import anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from app.config import settings
from app.core.logging import logger

# ── Module-level client singleton ────────────────────────────

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    """Return (or create) the async Anthropic client singleton."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=3,
        )
    return _client


# ── High-level helpers ───────────────────────────────────────


async def create_message(
    system: str,
    user_content: str,
    *,
    tools: list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> Message:
    """Send a message to Claude and return the full response.

    Args:
        system: System-level instruction prompt.
        user_content: The user message / task description.
        tools: Optional Anthropic tool definitions (for tool-use loops).
        max_tokens: Response token limit.
        temperature: Sampling temperature (lower = more deterministic).
    """
    client = get_client()
    kwargs: dict = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    if tools:
        kwargs["tools"] = tools

    logger.debug(
        "Calling Claude: model=%s, tools=%s, content_len=%d",
        settings.anthropic_model,
        bool(tools),
        len(user_content),
    )

    response = await client.messages.create(**kwargs)
    logger.debug("Claude response: stop_reason=%s", response.stop_reason)
    return response


async def get_text_response(
    system: str,
    user_content: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """Send a message and return only the text (no tool calls)."""
    response = await create_message(
        system=system,
        user_content=user_content,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text_blocks = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_blocks)


def extract_tool_use(response: Message) -> list[ToolUseBlock]:
    """Extract all tool_use blocks from a Claude response."""
    return [b for b in response.content if b.type == "tool_use"]


def extract_text(response: Message) -> str:
    """Extract all text blocks from a Claude response."""
    return "\n".join(b.text for b in response.content if b.type == "text")
