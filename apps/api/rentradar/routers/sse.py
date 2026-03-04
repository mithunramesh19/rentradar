"""SSE endpoint — streams real-time notifications to authenticated users."""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from rentradar.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])

SSE_CHANNEL_PREFIX = "rentradar:sse:user:"


async def _event_generator(request: Request, user_id: int):
    """Subscribe to user's Redis pub/sub channel and yield SSE events."""
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    channel = f"{SSE_CHANNEL_PREFIX}{user_id}"

    await pubsub.subscribe(channel)
    logger.info("SSE client connected — user %d", user_id)

    try:
        while True:
            if await request.is_disconnected():
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                yield {
                    "event": data.get("event", "notification"),
                    "data": json.dumps(data.get("data", data)),
                }
            else:
                # Heartbeat every ~15s to keep connection alive
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.close()
        logger.info("SSE client disconnected — user %d", user_id)


@router.get("/notifications")
async def stream_notifications(request: Request, user_id: int):
    """Stream real-time notifications for a user via Server-Sent Events.

    Query params:
        user_id: int — the authenticated user ID (will be from JWT in production)
    """
    return EventSourceResponse(_event_generator(request, user_id))
