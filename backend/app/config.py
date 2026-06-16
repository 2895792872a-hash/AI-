"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── LLM ───────────────────────────────────────────────────
    llm_provider: str = "anthropic"  # anthropic | qwen | openai
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ── Vision (VL) ────────────────────────────────────────────
    vl_api_key: str = ""
    vl_model: str = "qwen-vl-max"

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
