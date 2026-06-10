"""Standalone Playwright worker (optional microservice mode).

In simple setups the browser runs in-process with the API via managed_browser().
For production scaling, this worker can be deployed independently and receive
browser-step commands via Redis queues or HTTP.
"""

import asyncio
import json
import sys

import redis.asyncio as aioredis

REDIS_URL = "redis://redis:6379/0"

async def main():
    print("Browser Worker started, waiting for tasks...")
    r = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Subscribe to step execution requests
    pubsub = r.pubsub()
    await pubsub.subscribe("browser:step_requests")

    async for message in pubsub.listen():
        if message["type"] == "message":
            step = json.loads(message["data"])
            print(f"Received step: {step.get('action')}")
            # Actual execution handled by the API service in current architecture
            await r.publish("browser:step_results", json.dumps({"status": "ok"}))


if __name__ == "__main__":
    asyncio.run(main())
