from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError

# --------------------------------------------------------------------------
# Isolated on purpose (spec section 27): this is the ONLY place that knows
# how rate limiting is implemented. Swapping the in-memory store below for a
# Redis-backed one (INCR + EXPIRE, or a sorted set) only touches this file --
# every route keeps calling `enforce_rate_limit(request, bucket, ...)`.
# --------------------------------------------------------------------------

_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _client_key(request: Request, bucket: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{bucket}:{client_ip}"


def enforce_rate_limit(request: Request, bucket: str, max_requests: int, window_seconds: int) -> None:
    """Sliding-window limiter. Raises RateLimitError (-> HTTP 429) over the cap."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    key = _client_key(request, bucket)
    now = time.monotonic()
    window_start = now - window_seconds

    hits = _hits[key]
    while hits and hits[0] < window_start:
        hits.popleft()

    if len(hits) >= max_requests:
        raise RateLimitError(
            f"Too many requests to '{bucket}'. Limit is {max_requests} per {window_seconds}s.",
            details={"bucket": bucket, "limit": max_requests, "window_seconds": window_seconds},
        )

    hits.append(now)
