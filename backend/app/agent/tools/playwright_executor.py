"""Playwright executor — runs browser in a subprocess to avoid asyncio conflicts.

Python 3.14 on Windows has broken asyncio subprocess. We completely isolate
Playwright by running it as a standalone sync subprocess, communicating via
stdin/stdout JSON lines.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
from typing import Any

from app.agent.state import BrowserStep
from app.config import settings
from app.core.logging import logger

WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "browser_worker.py")


class BrowserSubprocess:
    """Manages a Playwright subprocess worker."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        """Launch the browser worker subprocess."""
        self._proc = subprocess.Popen(
            [sys.executable, WORKER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=os.path.dirname(WORKER_SCRIPT),
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "BROWSER_HEADLESS": "true" if self.headless else "false",
            },
        )
        # Wait for ready signal
        ready = self._proc.stdout.readline()
        resp = json.loads(ready)
        if resp.get("status") != "ready":
            raise RuntimeError(f"Worker failed to start: {resp}")
        logger.info("Browser worker started")

    def stop(self) -> None:
        """Shutdown the worker subprocess."""
        if self._proc and self._proc.poll() is None:
            self._send({"action": "quit"})
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        logger.info("Browser worker stopped")

    def _send(self, cmd: dict) -> dict:
        """Send a command to the worker and read the JSON response."""
        if not self._proc or self._proc.poll() is not None:
            raise RuntimeError("Worker process is not running")
        line = json.dumps(cmd, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        response_line = self._proc.stdout.readline()
        return json.loads(response_line)

    def execute_step(self, step: BrowserStep) -> dict[str, Any]:
        cmd = {"step_id": step.get("step_id"), "action": step.get("action")}
        action = step.get("action", "")
        if action == "navigate":
            cmd["url"] = step.get("url", "")
        elif action == "type":
            cmd["text"] = step.get("input_value", "")
            cmd["hint"] = step.get("description", "")
        elif action == "scroll":
            cmd["direction"] = step.get("input_value", "down") or "down"
        elif action == "screenshot":
            cmd["full_page"] = step.get("input_value", "") == "full"
        elif action == "accessibility_click":
            cmd["role"] = step.get("role", "")
            cmd["name"] = step.get("name", "")
        return self._send(cmd)


class AsyncBrowserSession:
    """Async wrapper — runs subprocess management in thread."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000):
        self._session = BrowserSubprocess(headless=headless, timeout_ms=timeout_ms)

    async def start(self) -> None:
        # subprocess.Popen is fast, call directly
        self._session.start()

    async def stop(self) -> None:
        self._session.stop()

    async def execute_step(self, step: BrowserStep) -> dict[str, Any]:
        # subprocess communication is sync but fast (pipes)
        return self._session.execute_step(step)


@contextlib.asynccontextmanager
async def managed_browser(headless: bool | None = None):
    if headless is None:
        headless = settings.browser_headless
    session = AsyncBrowserSession(headless=headless, timeout_ms=settings.browser_timeout_ms)
    try:
        await session.start()
        yield session
    except Exception as exc:
        logger.error("Browser session error: %s", exc)
        raise
    finally:
        await session.stop()
