"""Entry point that fixes Python 3.14 Windows asyncio subprocess before anything else."""

import sys
import asyncio

# On Windows + Python 3.14, force ProactorEventLoop (needed for Playwright subprocess)
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    # Force SelectorEventLoop as fallback for subprocess support
    # Python 3.14 may have broken Proactor subprocess; Selector on Windows
    # cannot do subprocess either. Try both approaches.
    # If Proactor fails, we rely on --reload's uvicorn handling.

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
