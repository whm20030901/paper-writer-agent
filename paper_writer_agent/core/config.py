from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_str_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item] or default


def _get_route_overrides_env(name: str) -> dict[str, list[str]]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return {}
    result: dict[str, list[str]] = {}
    for segment in value.split(";"):
        part = segment.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"{name} must use 'group=channel1,channel2' segments")
        group, channels = part.split("=", 1)
        key = group.strip()
        if not key:
            raise ValueError(f"{name} contains empty route group")
        parsed_channels = [item.strip() for item in channels.split(",") if item.strip()]
        if not parsed_channels:
            raise ValueError(f"{name} contains empty channel list for group '{key}'")
        result[key] = parsed_channels
    return result


@dataclass(frozen=True)
class Settings:
    app_name: str = "paper-writer-agent"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    memory_db_path: str = "memory.db"
    run_db_path: str = "runs.db"
    api_key: str = ""
    rate_limit_per_minute: int = 60
    run_retention_days: int = 30
    auto_purge_on_startup: bool = False
    default_iterations: int = 2
    prompt_version: str = "v1"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com"
    llm_model: str = ""
    llm_timeout_s: int = 30
    llm_max_retries: int = 1
    llm_retry_backoff_s: float = 0.2
    llm_retry_jitter_s: float = 0.0
    llm_retry_max_delay_s: float = 30.0
    llm_retry_backoff_multiplier: float = 2.0
    slo_min_success_rate: float = 0.9
    slo_min_avg_quality_score: float = 7.0
    slo_max_avg_duration_ms: float = 5000.0
    slo_alert_channels: list[str] = field(default_factory=lambda: ["log"])
    slo_alert_webhook_url: str = ""
    slo_alert_cooldown_seconds: int = 300
    slo_alert_dedupe_window_seconds: int = 900
    slo_alert_webhook_timeout_s: float = 3.0
    slo_alert_route_overrides: dict[str, list[str]] = field(default_factory=dict)
    slo_alert_template: str = "[{status}] violations={violations} fingerprint={fingerprint}"
    slo_alert_policy_version: str = "v1"
    slo_alert_auto_archive_on_startup: bool = False
    slo_alert_auto_archive_days: int = 30
    slo_sla_max_open_degraded_alerts: int = 5
    slo_alert_auto_tune_enabled: bool = True
    slo_alert_regression_guardrail_min_delta: float = -3.0
    slo_alert_canary_enabled: bool = True
    slo_alert_canary_promotion_threshold: float = 0.75
    release_gate_min_score: float = 80.0
    release_gate_require_no_rollback: bool = True
    release_webhook_secret: str = ""
    acceptance_gate_max_failed_checks: int = 0
    rollout_auto_rollback_enabled: bool = True
    operations_audit_min_grade: str = "B"
    release_approval_required: bool = True
    release_approval_sync_url: str = ""
    release_approval_sync_timeout_s: float = 3.0
    audit_report_history_limit: int = 200
    audit_trend_notify_webhook_url: str = ""
    audit_trend_notify_timeout_s: float = 3.0

    def __post_init__(self) -> None:
        validations = [
            (1 <= self.app_port <= 65535, "app_port must be between 1 and 65535"),
            (self.rate_limit_per_minute >= 1, "rate_limit_per_minute must be at least 1"),
            (self.run_retention_days >= 0, "run_retention_days must be non-negative"),
            (self.default_iterations >= 1, "default_iterations must be at least 1"),
            (self.llm_timeout_s >= 1, "llm_timeout_s must be at least 1"),
            (self.llm_max_retries >= 0, "llm_max_retries must be non-negative"),
            (self.llm_retry_backoff_s >= 0, "llm_retry_backoff_s must be non-negative"),
            (self.llm_retry_jitter_s >= 0, "llm_retry_jitter_s must be non-negative"),
            (self.llm_retry_max_delay_s >= 0, "llm_retry_max_delay_s must be non-negative"),
            (
                self.llm_retry_backoff_multiplier >= 1.0,
                "llm_retry_backoff_multiplier must be at least 1.0",
            ),
            (0.0 <= self.slo_min_success_rate <= 1.0, "slo_min_success_rate must be between 0 and 1"),
            (0.0 <= self.slo_min_avg_quality_score <= 10.0, "slo_min_avg_quality_score must be between 0 and 10"),
            (self.slo_max_avg_duration_ms >= 0.0, "slo_max_avg_duration_ms must be non-negative"),
            (self.slo_alert_cooldown_seconds >= 0, "slo_alert_cooldown_seconds must be non-negative"),
            (self.slo_alert_dedupe_window_seconds >= 0, "slo_alert_dedupe_window_seconds must be non-negative"),
            (self.slo_alert_webhook_timeout_s > 0.0, "slo_alert_webhook_timeout_s must be positive"),
            (self.slo_alert_auto_archive_days >= 0, "slo_alert_auto_archive_days must be non-negative"),
            (self.slo_sla_max_open_degraded_alerts >= 0, "slo_sla_max_open_degraded_alerts must be non-negative"),
            (
                -20.0 <= self.slo_alert_regression_guardrail_min_delta <= 20.0,
                "slo_alert_regression_guardrail_min_delta must be between -20 and 20",
            ),
            (
                0.0 <= self.slo_alert_canary_promotion_threshold <= 1.0,
                "slo_alert_canary_promotion_threshold must be between 0 and 1",
            ),
            (0.0 <= self.release_gate_min_score <= 100.0, "release_gate_min_score must be between 0 and 100"),
            (self.acceptance_gate_max_failed_checks >= 0, "acceptance_gate_max_failed_checks must be non-negative"),
            (self.operations_audit_min_grade in {"A", "B", "C", "D"}, "operations_audit_min_grade must be A/B/C/D"),
            (self.release_approval_sync_timeout_s > 0.0, "release_approval_sync_timeout_s must be positive"),
            (self.audit_report_history_limit >= 1, "audit_report_history_limit must be at least 1"),
            (self.audit_trend_notify_timeout_s > 0.0, "audit_trend_notify_timeout_s must be positive"),
        ]
        alert_channels = self.slo_alert_channels or ["log"]
        if any(channel not in {"log", "webhook"} for channel in alert_channels):
            raise ValueError("slo_alert_channels only supports: log, webhook")
        for group, channels in self.slo_alert_route_overrides.items():
            if not group.strip():
                raise ValueError("slo_alert_route_overrides contains empty group")
            if any(channel not in {"log", "webhook"} for channel in channels):
                raise ValueError("slo_alert_route_overrides only supports channels: log, webhook")
        if "{status}" not in self.slo_alert_template:
            raise ValueError("slo_alert_template must include {status}")
        if not self.slo_alert_policy_version.strip():
            raise ValueError("slo_alert_policy_version must not be blank")
        for is_valid, message in validations:
            if not is_valid:
                raise ValueError(message)

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            app_name=_get_str_env("APP_NAME", "paper-writer-agent"),
            app_env=_get_str_env("APP_ENV", "dev"),
            app_host=_get_str_env("APP_HOST", "0.0.0.0"),
            app_port=_get_int_env("APP_PORT", 8000),
            memory_db_path=_get_str_env("MEMORY_DB_PATH", "memory.db"),
            run_db_path=_get_str_env("RUN_DB_PATH", "runs.db"),
            api_key=_get_str_env("API_KEY", ""),
            rate_limit_per_minute=_get_int_env("RATE_LIMIT_PER_MINUTE", 60),
            run_retention_days=_get_int_env("RUN_RETENTION_DAYS", 30),
            auto_purge_on_startup=_get_bool_env("AUTO_PURGE_ON_STARTUP", False),
            default_iterations=_get_int_env("DEFAULT_ITERATIONS", 2),
            prompt_version=_get_str_env("PROMPT_VERSION", "v1"),
            llm_api_key=_get_str_env("LLM_API_KEY", ""),
            llm_base_url=_get_str_env("LLM_BASE_URL", "https://api.openai.com"),
            llm_model=_get_str_env("LLM_MODEL", ""),
            llm_timeout_s=_get_int_env("LLM_TIMEOUT_S", 30),
            llm_max_retries=_get_int_env("LLM_MAX_RETRIES", 1),
            llm_retry_backoff_s=_get_float_env("LLM_RETRY_BACKOFF_S", 0.2),
            llm_retry_jitter_s=_get_float_env("LLM_RETRY_JITTER_S", 0.0),
            llm_retry_max_delay_s=_get_float_env("LLM_RETRY_MAX_DELAY_S", 30.0),
            llm_retry_backoff_multiplier=_get_float_env("LLM_RETRY_BACKOFF_MULTIPLIER", 2.0),
            slo_min_success_rate=_get_float_env("SLO_MIN_SUCCESS_RATE", 0.9),
            slo_min_avg_quality_score=_get_float_env("SLO_MIN_AVG_QUALITY_SCORE", 7.0),
            slo_max_avg_duration_ms=_get_float_env("SLO_MAX_AVG_DURATION_MS", 5000.0),
            slo_alert_channels=_get_csv_env("SLO_ALERT_CHANNELS", ["log"]),
            slo_alert_webhook_url=_get_str_env("SLO_ALERT_WEBHOOK_URL", ""),
            slo_alert_cooldown_seconds=_get_int_env("SLO_ALERT_COOLDOWN_SECONDS", 300),
            slo_alert_dedupe_window_seconds=_get_int_env("SLO_ALERT_DEDUPE_WINDOW_SECONDS", 900),
            slo_alert_webhook_timeout_s=_get_float_env("SLO_ALERT_WEBHOOK_TIMEOUT_S", 3.0),
            slo_alert_route_overrides=_get_route_overrides_env("SLO_ALERT_ROUTE_OVERRIDES"),
            slo_alert_template=_get_str_env(
                "SLO_ALERT_TEMPLATE", "[{status}] violations={violations} fingerprint={fingerprint}"
            ),
            slo_alert_policy_version=_get_str_env("SLO_ALERT_POLICY_VERSION", "v1"),
            slo_alert_auto_archive_on_startup=_get_bool_env("SLO_ALERT_AUTO_ARCHIVE_ON_STARTUP", False),
            slo_alert_auto_archive_days=_get_int_env("SLO_ALERT_AUTO_ARCHIVE_DAYS", 30),
            slo_sla_max_open_degraded_alerts=_get_int_env("SLO_SLA_MAX_OPEN_DEGRADED_ALERTS", 5),
            slo_alert_auto_tune_enabled=_get_bool_env("SLO_ALERT_AUTO_TUNE_ENABLED", True),
            slo_alert_regression_guardrail_min_delta=_get_float_env(
                "SLO_ALERT_REGRESSION_GUARDRAIL_MIN_DELTA",
                -3.0,
            ),
            slo_alert_canary_enabled=_get_bool_env("SLO_ALERT_CANARY_ENABLED", True),
            slo_alert_canary_promotion_threshold=_get_float_env("SLO_ALERT_CANARY_PROMOTION_THRESHOLD", 0.75),
            release_gate_min_score=_get_float_env("RELEASE_GATE_MIN_SCORE", 80.0),
            release_gate_require_no_rollback=_get_bool_env("RELEASE_GATE_REQUIRE_NO_ROLLBACK", True),
            release_webhook_secret=_get_str_env("RELEASE_WEBHOOK_SECRET", ""),
            acceptance_gate_max_failed_checks=_get_int_env("ACCEPTANCE_GATE_MAX_FAILED_CHECKS", 0),
            rollout_auto_rollback_enabled=_get_bool_env("ROLLOUT_AUTO_ROLLBACK_ENABLED", True),
            operations_audit_min_grade=_get_str_env("OPERATIONS_AUDIT_MIN_GRADE", "B").upper(),
            release_approval_required=_get_bool_env("RELEASE_APPROVAL_REQUIRED", True),
            release_approval_sync_url=_get_str_env("RELEASE_APPROVAL_SYNC_URL", ""),
            release_approval_sync_timeout_s=_get_float_env("RELEASE_APPROVAL_SYNC_TIMEOUT_S", 3.0),
            audit_report_history_limit=_get_int_env("AUDIT_REPORT_HISTORY_LIMIT", 200),
            audit_trend_notify_webhook_url=_get_str_env("AUDIT_TREND_NOTIFY_WEBHOOK_URL", ""),
            audit_trend_notify_timeout_s=_get_float_env("AUDIT_TREND_NOTIFY_TIMEOUT_S", 3.0),
        )
