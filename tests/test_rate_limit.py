import pytest
from fastapi import HTTPException

from paper_writer_agent.api.rate_limit import InMemoryRateLimiter


def test_rate_limiter_returns_retry_after_header_when_limited():
    now = [100.0]
    limiter = InMemoryRateLimiter(max_requests_per_minute=2, window_seconds=60, time_func=lambda: now[0])

    limiter.check("client-a")
    limiter.check("client-a")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}


def test_rate_limiter_cleans_up_stale_keys_after_window_passes():
    now = [100.0]
    limiter = InMemoryRateLimiter(max_requests_per_minute=1, window_seconds=60, time_func=lambda: now[0])

    limiter.check("stale-client")
    assert "stale-client" in limiter._events

    now[0] = 161.0
    limiter.check("fresh-client")

    assert "stale-client" not in limiter._events
    assert "fresh-client" in limiter._events


def test_rate_limiter_allows_request_exactly_at_window_boundary():
    now = [100.0]
    limiter = InMemoryRateLimiter(max_requests_per_minute=1, window_seconds=60, time_func=lambda: now[0])

    limiter.check("boundary-client")

    now[0] = 160.0
    limiter.check("boundary-client")

    assert list(limiter._events["boundary-client"]) == [160.0]
