from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException


class InMemoryRateLimiter:
    def __init__(
        self,
        max_requests_per_minute: int = 60,
        window_seconds: int = 60,
        time_func: Callable[[], float] | None = None,
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.window_seconds = window_seconds
        self._time_func = time_func or time.monotonic
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune_queue(self, queue: deque[float], window_start: float) -> None:
        while queue and queue[0] <= window_start:
            queue.popleft()

    def _cleanup_stale_keys(self, window_start: float) -> None:
        stale_keys = [
            key
            for key, queue in self._events.items()
            if not queue or queue[-1] <= window_start
        ]
        for key in stale_keys:
            del self._events[key]

    def check(self, key: str) -> None:
        now = self._time_func()
        window_start = now - self.window_seconds

        with self._lock:
            self._cleanup_stale_keys(window_start)
            q = self._events.setdefault(key, deque())

            self._prune_queue(q, window_start)

            if len(q) >= self.max_requests_per_minute:
                retry_after = max(1, math.ceil((q[0] + self.window_seconds) - now))
                raise HTTPException(
                    status_code=429,
                    detail="rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            q.append(now)
