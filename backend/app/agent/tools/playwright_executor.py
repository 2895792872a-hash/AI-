"""Playwright execution engine — BrowserSession and step dispatch.

Manages a single Playwright browser instance lifecycle and provides
typed async methods for each browser action the Agent can request.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Any

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

from app.agent.state import BrowserStep
from app.config import settings
from app.core.logging import logger


class BrowserSession:
    """Manages a Playwright browser lifecycle with per-step execution.

    Usage:
        async with managed_browser() as browser:
            result = await browser.execute_step(step)
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ── Lifecycle ──────────────────────────────────────────

    async def start(self) -> None:
        """Launch browser, create context and a single page."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        logger.info("BrowserSession started (headless=%s)", self.headless)

    async def stop(self) -> None:
        """Gracefully close page, context, browser, and playwright."""
        for resource in (self._page, self._context, self._browser, self._playwright):
            if resource is not None:
                try:
                    await resource.close()
                except Exception:
                    pass  # best-effort cleanup

        self._page = self._context = self._browser = self._playwright = None
        logger.info("BrowserSession stopped")

    @property
    def page(self) -> Page:
        """The active Playwright Page (raises if not started)."""
        if self._page is None:
            raise RuntimeError("BrowserSession not started — call start() first")
        return self._page

    # ── Browser Actions ────────────────────────────────────

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL and return page info."""
        p = self.page
        response = await p.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        await asyncio.sleep(1)  # let JS settle
        return {
            "action": "navigate",
            "url": p.url,
            "title": await p.title(),
            "status": response.status if response else None,
            "success": True,
        }

    async def click(self, selector: str) -> dict[str, Any]:
        """Click an element by CSS selector."""
        p = self.page
        await p.wait_for_selector(selector, timeout=self.timeout_ms)
        await p.click(selector)
        return {"action": "click", "selector": selector, "success": True}

    async def type_text(self, selector: str, text: str) -> dict[str, Any]:
        """Type text into an input field, clearing it first."""
        p = self.page
        await p.wait_for_selector(selector, timeout=self.timeout_ms)
        await p.fill(selector, text)
        return {"action": "type", "selector": selector, "text": text, "success": True}

    async def scroll(self, direction: str = "down", amount: int = 500) -> dict[str, Any]:
        """Scroll the page up or down."""
        p = self.page
        delta = amount if direction == "down" else -amount
        await p.evaluate(f"window.scrollBy(0, {delta})")
        return {"action": "scroll", "direction": direction, "amount": amount, "success": True}

    async def extract_content(self, selector: str | None = None) -> dict[str, Any]:
        """Extract text content from the page or a specific element."""
        p = self.page
        if selector:
            await p.wait_for_selector(selector, timeout=self.timeout_ms)
            element = p.locator(selector)
            text = await element.inner_text()
        else:
            text = await p.inner_text("body")
        # Truncate to avoid blowing up context
        return {"action": "extract", "selector": selector, "text": text[:10_000], "success": True}

    async def screenshot(self, full_page: bool = False) -> dict[str, Any]:
        """Take a screenshot; returns base64 PNG."""
        p = self.page
        import base64
        img_bytes = await p.screenshot(full_page=full_page)
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return {"action": "screenshot", "full_page": full_page, "image_base64": b64, "success": True}

    # ── Step Dispatcher ────────────────────────────────────

    ACTION_MAP = {
        "navigate": "navigate",
        "click": "click",
        "type": "type_text",
        "scroll": "scroll",
        "extract": "extract_content",
        "screenshot": "screenshot",
    }

    async def execute_step(self, step: BrowserStep) -> dict[str, Any]:
        """Dispatch a BrowserStep to the correct handler method.

        Returns a result dict with at least {step_id, action, status, error}.
        """
        step_id = step.get("step_id", -1)
        action_name = step.get("action", "")

        if action_name not in self.ACTION_MAP:
            return {
                "step_id": step_id,
                "action": action_name,
                "status": "failed",
                "error": f"Unknown action '{action_name}'",
            }

        method_name = self.ACTION_MAP[action_name]
        method = getattr(self, method_name, None)
        if method is None:
            return {
                "step_id": step_id,
                "action": action_name,
                "status": "failed",
                "error": f"No handler for '{action_name}'",
            }

        try:
            kwargs: dict = {}
            if action_name == "navigate":
                kwargs["url"] = step.get("url", "")
            elif action_name == "click":
                kwargs["selector"] = step.get("target_selector", "")
            elif action_name == "type":
                kwargs["selector"] = step.get("target_selector", "")
                kwargs["text"] = step.get("input_value", "")
            elif action_name == "scroll":
                kwargs["direction"] = step.get("input_value", "down") or "down"
            elif action_name == "extract":
                sel = step.get("target_selector")
                if sel:
                    kwargs["selector"] = sel
            elif action_name == "screenshot":
                kwargs["full_page"] = step.get("input_value", "") == "full"

            result = await method(**kwargs)
            result["step_id"] = step_id
            result["status"] = "completed"
            step["result"] = str(result)
            step["status"] = "completed"
            return result

        except Exception as exc:
            logger.warning("Step %d (%s) failed: %s", step_id, action_name, exc)
            step["status"] = "failed"
            step["error"] = str(exc)
            return {
                "step_id": step_id,
                "action": action_name,
                "status": "failed",
                "error": str(exc),
            }


# ── Context Manager ─────────────────────────────────────────


import contextlib


@contextlib.asynccontextmanager
async def managed_browser(headless: bool | None = None):
    """Async context manager that guarantees browser cleanup."""
    if headless is None:
        headless = settings.browser_headless

    session = BrowserSession(headless=headless, timeout_ms=settings.browser_timeout_ms)
    try:
        await session.start()
        yield session
    except Exception as exc:
        logger.error("Browser session fatal error: %s", exc)
        raise
    finally:
        await session.stop()
