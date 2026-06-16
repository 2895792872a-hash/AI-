"""LLM service — unified interface for Qwen (OpenAI-compatible) and Anthropic.

Uses OpenAI SDK under the hood. Qwen's API is fully OpenAI-compatible.
Provides the same external interface so nodes don't need to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.core.logging import logger

# ── Response types (mimic Anthropic format for compatibility) ──


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class Message:
    content: list[TextBlock | ToolUseBlock]
    stop_reason: str = "end_turn"

    @classmethod
    def from_openai(cls, response) -> Message:
        """Convert OpenAI response to our unified Message format."""
        choice = response.choices[0]
        msg = choice.message

        content_blocks = []

        # Text content
        if msg.content:
            content_blocks.append(TextBlock(text=msg.content))

        # Tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                import json
                args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                content_blocks.append(ToolUseBlock(
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                ))

        # Map finish reason
        reason = choice.finish_reason or "end_turn"
        if reason == "stop":
            reason = "end_turn"
        elif reason == "tool_calls":
            reason = "tool_use"

        return cls(content=content_blocks, stop_reason=reason)


# ── Client singleton ──────────────────────────────────────────

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return (or create) the async OpenAI-compatible client singleton."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            max_retries=3,
            timeout=120.0,
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
    """Send a message to the LLM and return a unified Message response.

    Works with Qwen, OpenAI, or any OpenAI-compatible API.
    """
    client = get_client()

    # Build messages list with system prompt
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    kwargs: dict = {
        "model": settings.llm_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    # Convert Anthropic-format tools to OpenAI format
    if tools:
        kwargs["tools"] = [_to_openai_tool(t) for t in tools]
        if tools:
            kwargs["tool_choice"] = "auto"

    logger.debug(
        "Calling LLM: model=%s, tools=%s, content_len=%d",
        settings.llm_model,
        bool(tools),
        len(user_content),
    )

    response = await client.chat.completions.create(**kwargs)
    msg = Message.from_openai(response)
    logger.debug("LLM response: stop_reason=%s, blocks=%d", msg.stop_reason, len(msg.content))
    return msg


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
    """Extract all tool_use blocks from a response."""
    return [b for b in response.content if b.type == "tool_use"]


def extract_text(response: Message) -> str:
    """Extract all text blocks from a response."""
    return "\n".join(b.text for b in response.content if b.type == "text")


# ── Tool format conversion ───────────────────────────────────


def _to_openai_tool(anthropic_tool: dict) -> dict:
    """Convert an Anthropic-format tool definition to OpenAI format."""
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool.get("description", ""),
            "parameters": anthropic_tool.get("input_schema", {}),
        },
    }
