"""SSE notification bridge — Redis pub/sub publisher side."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

logger = logging.getLogger(__name__)

SSE_CHANNEL_PREFIX = "rentradar:sse:user:"


def publish_sse_event(
    redis_url: str,
    user_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """Publish notification to user's SSE channel via Redis pub/sub.

    Returns the number of subscribers that received the message.
    """
    r = redis.from_url(redis_url)
    channel = f"{SSE_CHANNEL_PREFIX}{user_id}"
    message = json.dumps({"event": event_type, "data": payload})
    count = r.publish(channel, message)
    logger.debug("SSE publish to %s — %d subscribers", channel, count)
    return count
