"""Application configuration via Pydantic Settings."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── Claude API ──────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # ── Redis ───────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Playwright ──────────────────────────────────────────────
    browser_headless: bool = True
    browser_timeout_ms: int = 30000
    browser_max_retries_per_step: int = 2

    # ── API Server ──────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Agent Limits ────────────────────────────────────────────
    max_steps_per_task: int = 20
    max_retries_per_stage: int = 3
    task_timeout_seconds: int = 300

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Singleton settings instance
settings = Settings()
