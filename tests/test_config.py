import pytest

from paper_writer_agent.core.config import Settings
from paper_writer_agent.main import bootstrap_pipeline


def test_settings_blank_env_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("APP_NAME", "   ")
    monkeypatch.setenv("APP_PORT", "")
    monkeypatch.setenv("AUTO_PURGE_ON_STARTUP", " ")
    monkeypatch.setenv("LLM_RETRY_BACKOFF_S", "")

    settings = Settings.from_env()

    assert settings.app_name == "paper-writer-agent"
    assert settings.app_port == 8000
    assert settings.auto_purge_on_startup is False
    assert settings.llm_retry_backoff_s == 0.2


def test_settings_strips_string_env_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "  prod  ")
    monkeypatch.setenv("LLM_BASE_URL", " https://example.com/v1  ")
    monkeypatch.setenv("PROMPT_VERSION", " v2.1 ")

    settings = Settings.from_env()

    assert settings.app_env == "prod"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.prompt_version == "v2.1"


def test_settings_reads_llm_retry_backoff_multiplier_from_env(monkeypatch):
    monkeypatch.setenv("LLM_RETRY_BACKOFF_MULTIPLIER", "3.5")
    monkeypatch.setenv("SLO_MIN_SUCCESS_RATE", "0.88")
    monkeypatch.setenv("SLO_ALERT_CHANNELS", "log,webhook")
    monkeypatch.setenv("SLO_ALERT_COOLDOWN_SECONDS", "120")
    monkeypatch.setenv("SLO_ALERT_ROUTE_OVERRIDES", "quality=log;latency=webhook")
    monkeypatch.setenv("SLO_ALERT_POLICY_VERSION", "v3")
    monkeypatch.setenv("SLO_SLA_MAX_OPEN_DEGRADED_ALERTS", "9")
    monkeypatch.setenv("SLO_ALERT_AUTO_TUNE_ENABLED", "false")
    monkeypatch.setenv("SLO_ALERT_REGRESSION_GUARDRAIL_MIN_DELTA", "-1.5")
    monkeypatch.setenv("SLO_ALERT_CANARY_ENABLED", "true")
    monkeypatch.setenv("SLO_ALERT_CANARY_PROMOTION_THRESHOLD", "0.8")
    monkeypatch.setenv("RELEASE_GATE_MIN_SCORE", "85")
    monkeypatch.setenv("RELEASE_GATE_REQUIRE_NO_ROLLBACK", "false")
    monkeypatch.setenv("RELEASE_WEBHOOK_SECRET", "token-123")
    monkeypatch.setenv("ACCEPTANCE_GATE_MAX_FAILED_CHECKS", "1")
    monkeypatch.setenv("ROLLOUT_AUTO_ROLLBACK_ENABLED", "true")
    monkeypatch.setenv("OPERATIONS_AUDIT_MIN_GRADE", "A")
    monkeypatch.setenv("RELEASE_APPROVAL_REQUIRED", "false")
    monkeypatch.setenv("RELEASE_APPROVAL_SYNC_URL", "https://approval.example/sync")
    monkeypatch.setenv("RELEASE_APPROVAL_SYNC_TIMEOUT_S", "5.5")
    monkeypatch.setenv("AUDIT_REPORT_HISTORY_LIMIT", "300")
    monkeypatch.setenv("AUDIT_TREND_NOTIFY_WEBHOOK_URL", "https://notify.example/audit")
    monkeypatch.setenv("AUDIT_TREND_NOTIFY_TIMEOUT_S", "4.0")

    settings = Settings.from_env()

    assert settings.llm_retry_backoff_multiplier == 3.5
    assert settings.slo_min_success_rate == 0.88
    assert settings.slo_alert_channels == ["log", "webhook"]
    assert settings.slo_alert_cooldown_seconds == 120
    assert settings.slo_alert_route_overrides == {"quality": ["log"], "latency": ["webhook"]}
    assert settings.slo_alert_policy_version == "v3"
    assert settings.slo_sla_max_open_degraded_alerts == 9
    assert settings.slo_alert_auto_tune_enabled is False
    assert settings.slo_alert_regression_guardrail_min_delta == -1.5
    assert settings.slo_alert_canary_enabled is True
    assert settings.slo_alert_canary_promotion_threshold == 0.8
    assert settings.release_gate_min_score == 85
    assert settings.release_gate_require_no_rollback is False
    assert settings.release_webhook_secret == "token-123"
    assert settings.acceptance_gate_max_failed_checks == 1
    assert settings.rollout_auto_rollback_enabled is True
    assert settings.operations_audit_min_grade == "A"
    assert settings.release_approval_required is False
    assert settings.release_approval_sync_url == "https://approval.example/sync"
    assert settings.release_approval_sync_timeout_s == 5.5
    assert settings.audit_report_history_limit == 300
    assert settings.audit_trend_notify_webhook_url == "https://notify.example/audit"
    assert settings.audit_trend_notify_timeout_s == 4.0


def test_bootstrap_pipeline_passes_multiplier_to_llm_client():
    settings = Settings(llm_api_key="k", llm_model="demo", llm_retry_backoff_multiplier=4.0)

    pipeline = bootstrap_pipeline(settings)

    assert pipeline.llm.settings.retry_backoff_multiplier == 4.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"app_port": 0}, "app_port"),
        ({"rate_limit_per_minute": 0}, "rate_limit_per_minute"),
        ({"run_retention_days": -1}, "run_retention_days"),
        ({"default_iterations": 0}, "default_iterations"),
        ({"llm_timeout_s": 0}, "llm_timeout_s"),
        ({"llm_max_retries": -1}, "llm_max_retries"),
        ({"llm_retry_backoff_s": -0.1}, "llm_retry_backoff_s"),
        ({"llm_retry_jitter_s": -0.1}, "llm_retry_jitter_s"),
        ({"llm_retry_max_delay_s": -1.0}, "llm_retry_max_delay_s"),
        ({"llm_retry_backoff_multiplier": 0.5}, "llm_retry_backoff_multiplier"),
        ({"slo_min_success_rate": 1.5}, "slo_min_success_rate"),
        ({"slo_min_avg_quality_score": 11.0}, "slo_min_avg_quality_score"),
        ({"slo_max_avg_duration_ms": -1.0}, "slo_max_avg_duration_ms"),
        ({"slo_alert_channels": ["email"]}, "slo_alert_channels"),
        ({"slo_alert_cooldown_seconds": -1}, "slo_alert_cooldown_seconds"),
        ({"slo_alert_regression_guardrail_min_delta": -21.0}, "slo_alert_regression_guardrail_min_delta"),
        ({"slo_alert_canary_promotion_threshold": 1.5}, "slo_alert_canary_promotion_threshold"),
        ({"release_gate_min_score": 120.0}, "release_gate_min_score"),
        ({"acceptance_gate_max_failed_checks": -1}, "acceptance_gate_max_failed_checks"),
        ({"operations_audit_min_grade": "E"}, "operations_audit_min_grade"),
        ({"slo_alert_dedupe_window_seconds": -1}, "slo_alert_dedupe_window_seconds"),
        ({"slo_alert_webhook_timeout_s": 0.0}, "slo_alert_webhook_timeout_s"),
        ({"slo_alert_route_overrides": {"quality": ["email"]}}, "slo_alert_route_overrides"),
        ({"slo_alert_template": "invalid-template"}, "slo_alert_template"),
        ({"slo_alert_policy_version": " "}, "slo_alert_policy_version"),
        ({"slo_sla_max_open_degraded_alerts": -1}, "slo_sla_max_open_degraded_alerts"),
        ({"release_approval_sync_timeout_s": 0.0}, "release_approval_sync_timeout_s"),
        ({"audit_report_history_limit": 0}, "audit_report_history_limit"),
        ({"audit_trend_notify_timeout_s": 0.0}, "audit_trend_notify_timeout_s"),
    ],
)
def test_settings_reject_invalid_numeric_values(kwargs, message):
    with pytest.raises(ValueError) as exc_info:
        Settings(**kwargs)

    assert message in str(exc_info.value)
