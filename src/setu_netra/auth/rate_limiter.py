"""
rate_limiter.py: Thread-safe in-memory sliding-window rate limiter for sensitive authentication endpoints.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Sliding-window rate limiter per client IP address."""

    def __init__(self, max_requests: int = 20, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, request: Request, cost: int = 1) -> None:
        """Inspect client IP request count; raises HTTP 429 if limit is exceeded."""
        client_ip = request.headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            # Filter timestamps inside window
            active_timestamps = [ts for ts in self._requests[client_ip] if ts > cutoff]
            self._requests[client_ip] = active_timestamps

            if len(active_timestamps) + cost > self.max_requests:
                retry_after = int(self.window_seconds - (now - active_timestamps[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for authentication requests. Retry in {max(1, retry_after)} seconds.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            for _ in range(cost):
                self._requests[client_ip].append(now)


# Global rate limiters
auth_rate_limiter = InMemoryRateLimiter(max_requests=30, window_seconds=60.0)
