"""SSE (Server-Sent Events) helpers.

Formats events according to the SSE spec and provides streaming utilities
for FastAPI endpoints.
"""

from __future__ import annotations

import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE event string.

    Args:
        event_type: The event name (e.g. 'stage_change', 'step_complete').
        data: JSON-serializable payload.

    Returns:
        Formatted SSE string: "event: <type>\\ndata: <json>\\n\\n"
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"
