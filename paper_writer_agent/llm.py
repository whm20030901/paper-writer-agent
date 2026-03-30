from __future__ import annotations

from dataclasses import dataclass
import logging
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time

import requests


@dataclass(frozen=True)
class LLMSettings:
    api_key: str = ""
    base_url: str = "https://api.openai.com"
    model: str = ""
    timeout_s: int = 30
    max_retries: int = 1
    retry_backoff_s: float = 0.2
    retry_jitter_s: float = 0.0
    retry_max_delay_s: float = 30.0
    retry_backoff_multiplier: float = 2.0


RETRYABLE_STATUS_CODES = {408, 429}

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.api_key and self.settings.model)

    @property
    def total_attempts(self) -> int:
        """Initial request + configured retries."""
        return max(self.settings.max_retries, 0) + 1

    def _retry_delay(self, response: requests.Response | None, retry_index: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                    if delay >= 0:
                        return delay
                except ValueError:
                    pass

                try:
                    retry_dt = parsedate_to_datetime(retry_after)
                    if retry_dt.tzinfo is None:
                        retry_dt = retry_dt.replace(tzinfo=timezone.utc)
                    delay_from_date = (retry_dt - datetime.now(timezone.utc)).total_seconds()
                    if delay_from_date >= 0:
                        return delay_from_date
                except (TypeError, ValueError, OverflowError):
                    pass

        base = max(self.settings.retry_backoff_s, 0.0)
        jitter = max(self.settings.retry_jitter_s, 0.0)
        multiplier = max(self.settings.retry_backoff_multiplier, 1.0)
        scaled_base = base * (multiplier ** max(retry_index, 0))
        return scaled_base + (random.uniform(0.0, jitter) if jitter > 0 else 0.0)

    def _clamp_delay(self, delay: float) -> float:
        max_delay = max(self.settings.retry_max_delay_s, 0.0)
        return min(max(delay, 0.0), max_delay)

    def generate_draft(
        self,
        *,
        task: str,
        outline: str,
        context: str,
        skills_summary: str,
        reviewer_feedback: str,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("llm client not configured")

        attempts = self.total_attempts
        for attempt in range(attempts):
            try:
                response = requests.post(
                    f"{self.settings.base_url.rstrip('/')}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.model,
                        "temperature": 0.3,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an academic writing assistant. Produce concise, evidence-grounded drafts.",
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Task:\n{task}\n\n"
                                    f"Outline:\n{outline}\n\n"
                                    f"Skills:\n{skills_summary}\n\n"
                                    f"Reviewer Feedback:\n{reviewer_feedback}\n\n"
                                    f"Context:\n{context[:6000]}\n\n"
                                    "Write a structured draft and end with a short references section."
                                ),
                            },
                        ],
                    },
                    timeout=self.settings.timeout_s,
                )
                if response.status_code >= 400:
                    retryable = response.status_code in RETRYABLE_STATUS_CODES or response.status_code >= 500
                    if retryable and attempt < attempts - 1:
                        delay = self._clamp_delay(self._retry_delay(response, attempt))
                        logger.warning(
                            "llm response retry scheduled",
                            extra={"status_code": response.status_code, "attempt": attempt + 1, "max_attempts": attempts, "delay_s": delay},
                        )
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise RuntimeError("missing choices in llm response")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if not content:
                    raise RuntimeError("missing content in llm response")
                return content
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                retryable_http = status_code in RETRYABLE_STATUS_CODES or (status_code is not None and status_code >= 500)
                retryable = status_code is None or retryable_http
                if retryable and attempt < attempts - 1:
                    delay = self._clamp_delay(self._retry_delay(getattr(exc, "response", None), attempt))
                    logger.warning(
                        "llm request retry scheduled",
                        extra={"status_code": status_code, "attempt": attempt + 1, "max_attempts": attempts, "delay_s": delay, "error": str(exc)},
                    )
                    time.sleep(delay)
                    continue
                raise

        raise RuntimeError("llm request failed")
