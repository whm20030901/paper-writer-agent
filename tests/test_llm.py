from datetime import datetime, timedelta, timezone

import pytest
import requests

from paper_writer_agent.llm import LLMClient, LLMSettings


class _FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}", response=self)
        return None

    def json(self):
        return self._payload


def test_llm_client_enabled_flag():
    client = LLMClient(LLMSettings(api_key="k", model="gpt-4o-mini"))
    assert client.enabled is True
    assert client.total_attempts == 2

    disabled_client = LLMClient(LLMSettings(api_key="", model=""))
    assert disabled_client.enabled is False
    assert disabled_client.total_attempts == 2


def test_llm_client_calls_openai_compatible_chat_completions(monkeypatch):
    captured = {}

    def _fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"choices": [{"message": {"content": "generated draft"}}]})

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _fake_post)

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            base_url="https://example-llm.local",
            model="demo-model",
            timeout_s=12,
        )
    )

    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert result == "generated draft"
    assert captured["url"] == "https://example-llm.local/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "demo-model"
    assert captured["timeout"] == 12


def test_llm_client_retries_request_failures(monkeypatch):
    calls = {"count": 0}

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.RequestException("temporary network error")
        return _FakeResponse({"choices": [{"message": {"content": "retry success"}}]})

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda _: None)

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=2,
            retry_backoff_s=0.0,
        )
    )

    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry success"


def test_llm_client_max_retries_zero_means_single_attempt(monkeypatch):
    calls = {"count": 0}

    def _failing_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.RequestException("temporary network error")

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _failing_post)

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=0,
            retry_backoff_s=0.0,
        )
    )

    with pytest.raises(requests.RequestException):
        client.generate_draft(
            task="Task",
            outline="Outline",
            context="Context",
            skills_summary="Skills",
            reviewer_feedback="N/A",
        )

    assert calls["count"] == 1


def test_llm_client_retries_retryable_http_status(monkeypatch):
    calls = {"count": 0}

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=429)
        return _FakeResponse({"choices": [{"message": {"content": "retry from 429"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda _: None)

    client = LLMClient(LLMSettings(api_key="test-key", model="demo-model", max_retries=2, retry_backoff_s=0.0))
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry from 429"


def test_llm_client_does_not_retry_non_retryable_http_status(monkeypatch):
    calls = {"count": 0}

    def _unauthorized_post(*args, **kwargs):
        calls["count"] += 1
        return _FakeResponse({}, status_code=401)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _unauthorized_post)

    client = LLMClient(LLMSettings(api_key="test-key", model="demo-model", max_retries=3, retry_backoff_s=0.0))

    try:
        client.generate_draft(
            task="Task",
            outline="Outline",
            context="Context",
            skills_summary="Skills",
            reviewer_feedback="N/A",
        )
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert calls["count"] == 1


def test_llm_client_prefers_retry_after_header(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=429, headers={"Retry-After": "0.7"})
        return _FakeResponse({"choices": [{"message": {"content": "retry from header"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(LLMSettings(api_key="test-key", model="demo-model", max_retries=2, retry_backoff_s=0.0))
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry from header"
    assert sleeps == [0.7]


def test_llm_client_parses_retry_after_http_date(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    retry_at = datetime.now(timezone.utc) + timedelta(seconds=2)
    retry_after = retry_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=503, headers={"Retry-After": retry_after})
        return _FakeResponse({"choices": [{"message": {"content": "retry from http-date"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(LLMSettings(api_key="test-key", model="demo-model", max_retries=2, retry_backoff_s=0.0))
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry from http-date"
    assert len(sleeps) == 1
    assert 0.0 <= sleeps[0] <= 3.0


def test_llm_client_invalid_retry_after_falls_back_to_configured_backoff(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=429, headers={"Retry-After": "not-a-number"})
        return _FakeResponse({"choices": [{"message": {"content": "retry with fallback backoff"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=2,
            retry_backoff_s=0.33,
        )
    )
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry with fallback backoff"
    assert sleeps == [0.33]


def test_llm_client_backoff_includes_jitter_when_configured(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=429, headers={"Retry-After": "invalid"})
        return _FakeResponse({"choices": [{"message": {"content": "retry with jitter"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.random.uniform", lambda a, b: 0.12)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=2,
            retry_backoff_s=0.3,
            retry_jitter_s=0.2,
        )
    )
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry with jitter"
    assert sleeps == [0.42]


def test_llm_client_caps_retry_delay_by_max_delay(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse({}, status_code=429, headers={"Retry-After": "10"})
        return _FakeResponse({"choices": [{"message": {"content": "retry with cap"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=2,
            retry_max_delay_s=0.5,
        )
    )
    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 2
    assert result == "retry with cap"
    assert sleeps == [0.5]


def test_llm_client_uses_exponential_backoff_multiplier(monkeypatch):
    calls = {"count": 0}
    sleeps: list[float] = []

    def _flaky_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.RequestException("temporary")
        return _FakeResponse({"choices": [{"message": {"content": "retry with multiplier"}}]}, status_code=200)

    monkeypatch.setattr("paper_writer_agent.llm.requests.post", _flaky_post)
    monkeypatch.setattr("paper_writer_agent.llm.time.sleep", lambda s: sleeps.append(s))

    client = LLMClient(
        LLMSettings(
            api_key="test-key",
            model="demo-model",
            max_retries=3,
            retry_backoff_s=0.2,
            retry_jitter_s=0.0,
            retry_backoff_multiplier=3.0,
            retry_max_delay_s=10.0,
        )
    )

    result = client.generate_draft(
        task="Task",
        outline="Outline",
        context="Context",
        skills_summary="Skills",
        reviewer_feedback="N/A",
    )

    assert calls["count"] == 3
    assert result == "retry with multiplier"
    assert sleeps == pytest.approx([0.2, 0.6])
