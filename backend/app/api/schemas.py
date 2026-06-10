"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    """Request to create a new browser automation task."""

    user_task: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language description of the browser task",
        examples=["Find the price of iPhone 15 on Amazon"],
    )


# ── Response ─────────────────────────────────────────────────


class TaskResponse(BaseModel):
    """Response returned immediately after creating a task."""

    task_id: str = Field(..., description="Unique task ID for tracking")
    status: str = Field(default="accepted", description="Initial task status")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of creation",
    )


class TaskStatusResponse(BaseModel):
    """Full task status returned by GET /tasks/{task_id}."""

    task_id: str
    user_task: str
    status: str  # parsing | operating | extracting | summarizing | done | error
    stage_progress: str
    parsed_steps_count: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    final_summary: Optional[str] = None
    extracted_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    task_id: Optional[str] = None
