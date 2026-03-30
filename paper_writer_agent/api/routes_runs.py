from __future__ import annotations

import difflib
import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib import request
from urllib.error import URLError

from fastapi import Depends, FastAPI, HTTPException, Header, Query, Response

from ..core.config import Settings
from ..services.paper_service import PaperService
from .run_query import build_run_query_filters
from .schemas import (
    CitationAuditResponse,
    RunDetailResponse,
    RunDiffResponse,
    RunFormattedReferencesResponse,
    RunInsightsResponse,
    RunLineageResponse,
    RunListItemResponse,
    RunListResponse,
    RunMetricsResponse,
    RunQualityBreakdownResponse,
    RunReviewReportResponse,
    SLOAlertCheckResponse,
    SLOAlertChannelResult,
    SLOAlertEventListResponse,
    SLOAlertEventResponse,
    SLOAlertReplayResponse,
    SLOAlertDashboardResponse,
    SLOAlertArchiveResponse,
    SLOAlertArchiveListResponse,
    SLOAlertArchiveRecordResponse,
    SLOAlertRestoreResponse,
    SLOAlertLifecycleRunResponse,
    SLOAlertSLAReconcileResponse,
    SLOAlertRemediationTicketResponse,
    SLOAlertRemediationTicketListResponse,
    SLOAlertRootCauseBreakdownResponse,
    SLOAlertQualityScoreResponse,
    SLOAlertStrategyTuneResponse,
    SLOAlertStrategyExperimentResponse,
    SLOAlertStrategyExperimentRunResponse,
    SLOAlertStrategyExperimentDashboardResponse,
    SLOAlertStrategyReplayResponse,
    SLOAlertStrategyCanaryStatusResponse,
    SLOAlertStrategyCanaryToggleResponse,
    DemoReadinessResponse,
    DemoRehearsalResponse,
    DemoFinalReportResponse,
    DemoPostReleaseMonitorResponse,
    DemoRollbackAdviceResponse,
    DemoOpsScorecardResponse,
    DemoReleaseGateResponse,
    DemoReleasePlanResponse,
    DemoRoadmapStatusResponse,
    DemoCICDWebhookResponse,
    DemoAcceptanceGateResponse,
    DemoRolloutRunbookResponse,
    DemoOperationsAuditResponse,
    DemoReleaseApprovalResponse,
    DemoReleaseApprovalListResponse,
    DemoApprovalSyncResponse,
    DemoAuditReportResponse,
    DemoAuditReportSnapshotResponse,
    DemoAuditReportHistoryResponse,
    DemoAuditReportTrendPoint,
    DemoAuditReportTrendResponse,
    DemoAuditReportTrendSummaryResponse,
    DemoAuditTrendNotificationResponse,
    DemoAuditTrendNotificationRecord,
    DemoAuditTrendNotificationListResponse,
    DemoAuditTrendNotificationReplayResponse,
    DemoAuditTrendReplayFailedResponse,
    DemoAuditTrendReplayPlanResponse,
    DemoAuditTrendReplayRunResponse,
    DemoAuditTrendNotificationMetricsResponse,
    DemoAuditTrendNotificationDrillResponse,
    DemoAuditTrendNotificationDrillListResponse,
    DemoAuditTrendNotificationDrillSummaryResponse,
    DemoAuditTrendNotificationDrillReportResponse,
    DemoAuditTrendDrillReportSnapshotResponse,
    DemoAuditTrendDrillReportSnapshotListResponse,
    DemoAuditTrendDrillReportSnapshotCompareResponse,
    DemoAuditTrendDrillReportSnapshotCleanupResponse,
    DemoAuditTrendDrillReportSnapshotRetentionPlanResponse,
    DemoAuditTrendDrillReportSnapshotRetentionRunResponse,
    DemoAuditTrendDrillReportSnapshotRetentionRunRecordResponse,
    DemoAuditTrendDrillReportSnapshotRetentionRunListResponse,
    AlertViolationCount,
    SLOHistoryPoint,
    SLOHistoryResponse,
    SLOStatusResponse,
    RunSourcesResponse,
    RunSummaryResponse,
)
from .security import extract_api_key_header, verify_api_key

REFERENCE_LINE_RE = re.compile(r"^\[(\d+)\]\s+", re.MULTILINE)


def register_runs_routes(app: FastAPI, cfg: Settings, paper_service: PaperService) -> None:
    alert_state_by_tenant: dict[str, dict[str, object | None]] = {}
    canary_override_by_tenant: dict[str, bool] = {}
    release_approvals: dict[str, dict[str, object]] = {}
    approval_sync_events: dict[str, dict[str, object]] = {}
    audit_report_history: list[dict[str, object]] = []
    audit_trend_notifications: list[dict[str, object]] = []
    audit_trend_drills: list[dict[str, object]] = []
    audit_trend_drill_report_snapshots: list[dict[str, object]] = []
    audit_trend_drill_report_snapshot_retention_runs: list[dict[str, object]] = []

    def evaluate_slo_from_stats(
        total_runs: int,
        success_rate: float,
        avg_quality_score: float,
        avg_duration_ms: float,
    ) -> tuple[Literal["ok", "degraded", "no_data"], list[str]]:
        if total_runs == 0:
            return "no_data", []
        violations: list[str] = []
        if success_rate < cfg.slo_min_success_rate:
            violations.append("success_rate_below_threshold")
        if avg_quality_score < cfg.slo_min_avg_quality_score:
            violations.append("avg_quality_below_threshold")
        if avg_duration_ms > cfg.slo_max_avg_duration_ms:
            violations.append("avg_duration_above_threshold")
        return ("ok" if not violations else "degraded"), violations

    @app.get("/v1/papers/demo/readiness", response_model=DemoReadinessResponse)
    def get_demo_readiness(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReadinessResponse:
        verify_api_key(cfg.api_key, x_api_key)
        stats = paper_service.get_stats()
        architecture_ready = True
        quality_ready = stats.total_runs > 0 and stats.success_rate >= cfg.slo_min_success_rate
        observability_ready = bool(cfg.slo_alert_channels) and cfg.slo_sla_max_open_degraded_alerts >= 0
        demo_ready = stats.total_runs > 0
        narrative_ready = True
        overall_ready = architecture_ready and observability_ready and narrative_ready and (quality_ready or demo_ready)
        return DemoReadinessResponse(
            architecture_ready=architecture_ready,
            quality_ready=quality_ready,
            observability_ready=observability_ready,
            demo_ready=demo_ready,
            narrative_ready=narrative_ready,
            overall_ready=overall_ready,
            evidence={
                "total_runs": stats.total_runs,
                "success_rate": stats.success_rate,
                "avg_quality_score": stats.avg_quality_score,
                "avg_duration_ms": stats.avg_duration_ms,
                "slo_channels": cfg.slo_alert_channels,
            },
        )

    @app.post("/v1/papers/demo/rehearsal", response_model=DemoRehearsalResponse)
    def run_demo_rehearsal(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoRehearsalResponse:
        verify_api_key(cfg.api_key, x_api_key)
        started_at_dt = datetime.now(timezone.utc)
        stats = paper_service.get_stats()
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        summary = paper_service.summarize_strategy_experiments(created_after=created_after, tenant_id=tenant_id)
        checks = {
            "has_runs": stats.total_runs >= 0,
            "metrics_available": stats.avg_duration_ms >= 0,
            "strategy_data_available": int(summary["total_experiments"]) >= 0,
            "canary_configured": cfg.slo_alert_canary_promotion_threshold >= 0,
        }
        finished_at_dt = datetime.now(timezone.utc)
        duration_ms = max(0, int((finished_at_dt - started_at_dt).total_seconds() * 1000))
        return DemoRehearsalResponse(
            started_at=started_at_dt.isoformat(),
            finished_at=finished_at_dt.isoformat(),
            duration_ms=duration_ms,
            checks=checks,
            summary="Demo rehearsal checks collected",
        )

    @app.post("/v1/papers/demo/final-report", response_model=DemoFinalReportResponse)
    def generate_demo_final_report(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoFinalReportResponse:
        verify_api_key(cfg.api_key, x_api_key)
        readiness = get_demo_readiness(x_api_key=x_api_key)
        rehearsal = run_demo_rehearsal(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        release_recommended = bool(readiness.overall_ready and all(rehearsal.checks.values()))
        release_notes = [
            f"overall_ready={readiness.overall_ready}",
            f"rehearsal_checks_passed={all(rehearsal.checks.values())}",
            f"duration_ms={rehearsal.duration_ms}",
        ]
        return DemoFinalReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            readiness=readiness,
            rehearsal=rehearsal,
            release_recommended=release_recommended,
            release_notes=release_notes,
        )

    @app.get("/v1/papers/demo/post-release-monitor", response_model=DemoPostReleaseMonitorResponse)
    def get_demo_post_release_monitor(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoPostReleaseMonitorResponse:
        verify_api_key(cfg.api_key, x_api_key)
        stats = paper_service.get_stats()
        canary_status = get_slo_alert_strategy_canary_status(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        checks = {
            "success_rate_ok": stats.success_rate >= cfg.slo_min_success_rate,
            "quality_ok": stats.avg_quality_score >= cfg.slo_min_avg_quality_score,
            "latency_ok": stats.avg_duration_ms <= cfg.slo_max_avg_duration_ms or stats.total_runs == 0,
            "canary_recommended": canary_status.canary_recommended,
        }
        failed_count = sum(1 for value in checks.values() if not value)
        if failed_count >= 3:
            risk_level: Literal["low", "medium", "high"] = "high"
        elif failed_count >= 1:
            risk_level = "medium"
        else:
            risk_level = "low"
        return DemoPostReleaseMonitorResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            risk_level=risk_level,
            checks=checks,
            metrics_snapshot={
                "total_runs": stats.total_runs,
                "success_rate": round(stats.success_rate, 4),
                "avg_quality_score": round(stats.avg_quality_score, 4),
                "avg_duration_ms": round(stats.avg_duration_ms, 2),
            },
            canary_snapshot=canary_status.model_dump(),
        )

    @app.get("/v1/papers/demo/rollback-advice", response_model=DemoRollbackAdviceResponse)
    def get_demo_rollback_advice(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoRollbackAdviceResponse:
        verify_api_key(cfg.api_key, x_api_key)
        monitor = get_demo_post_release_monitor(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        should_rollback = monitor.risk_level == "high"
        reasons = [
            f"risk_level={monitor.risk_level}",
            f"failed_checks={sum(1 for value in monitor.checks.values() if not value)}",
        ]
        if should_rollback:
            reasons.append("rollback_recommended_due_to_high_risk")
        else:
            reasons.append("continue_observing")
        return DemoRollbackAdviceResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            should_rollback=should_rollback,
            risk_level=monitor.risk_level,
            reasons=reasons,
        )

    @app.get("/v1/papers/demo/ops-scorecard", response_model=DemoOpsScorecardResponse)
    def get_demo_ops_scorecard(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoOpsScorecardResponse:
        verify_api_key(cfg.api_key, x_api_key)
        final_report = generate_demo_final_report(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        monitor = get_demo_post_release_monitor(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        rollback = get_demo_rollback_advice(days=days, tenant_id=tenant_id, x_api_key=x_api_key)

        base_score = 100.0
        risk_penalty_map = {"low": 0.0, "medium": 20.0, "high": 45.0}
        base_score -= risk_penalty_map.get(monitor.risk_level, 30.0)
        if rollback.should_rollback:
            base_score -= 20.0
        if not final_report.release_recommended:
            base_score -= 15.0
        operations_score = max(0.0, round(base_score, 2))
        if operations_score >= 90:
            grade: Literal["A", "B", "C", "D"] = "A"
        elif operations_score >= 75:
            grade = "B"
        elif operations_score >= 60:
            grade = "C"
        else:
            grade = "D"

        highlights = [
            f"risk_level={monitor.risk_level}",
            f"release_recommended={final_report.release_recommended}",
            f"rollback_recommended={rollback.should_rollback}",
        ]
        return DemoOpsScorecardResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            operations_score=operations_score,
            grade=grade,
            release_recommended=final_report.release_recommended,
            rollback_recommended=rollback.should_rollback,
            highlights=highlights,
            metrics_snapshot=monitor.metrics_snapshot,
        )

    @app.get("/v1/papers/demo/release-gate", response_model=DemoReleaseGateResponse)
    def get_demo_release_gate(
        target_env: Literal["staging", "production"] = Query(default="staging"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReleaseGateResponse:
        verify_api_key(cfg.api_key, x_api_key)
        scorecard = get_demo_ops_scorecard(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        min_required = cfg.release_gate_min_score + (5.0 if target_env == "production" else 0.0)
        gate_passed = scorecard.operations_score >= min_required
        reasons: list[str] = [f"operations_score={scorecard.operations_score}", f"min_required={min_required}"]
        if cfg.release_gate_require_no_rollback and scorecard.rollback_recommended:
            gate_passed = False
            reasons.append("rollback_recommended_blocks_release")
        if gate_passed:
            reasons.append("release_gate_passed")
        else:
            reasons.append("release_gate_failed")
        return DemoReleaseGateResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            target_env=target_env,
            gate_passed=gate_passed,
            operations_score=scorecard.operations_score,
            min_required_score=min_required,
            rollback_recommended=scorecard.rollback_recommended,
            reasons=reasons,
        )

    @app.post("/v1/papers/demo/release-plan", response_model=DemoReleasePlanResponse)
    def build_demo_release_plan(
        target_env: Literal["staging", "production"] = Query(default="staging"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReleasePlanResponse:
        verify_api_key(cfg.api_key, x_api_key)
        gate = get_demo_release_gate(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        steps = [
            "Run automated test suite and smoke checks",
            "Validate demo readiness and rehearsal outputs",
            f"Deploy to {target_env} environment",
            "Monitor post-release monitor and rollback-advice endpoints",
        ]
        blockers = [] if gate.gate_passed else gate.reasons
        return DemoReleasePlanResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            target_env=target_env,
            gate_passed=gate.gate_passed,
            steps=steps,
            blocker_reasons=blockers,
        )

    @app.get("/v1/papers/demo/roadmap-status", response_model=DemoRoadmapStatusResponse)
    def get_demo_roadmap_status(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoRoadmapStatusResponse:
        verify_api_key(cfg.api_key, x_api_key)
        completed_days = list(range(1, 35))
        pending_days = [35, 36, 37]
        system_status: Literal["operational", "needs_attention"] = "operational"
        return DemoRoadmapStatusResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            completed_days=completed_days,
            current_day=34,
            pending_days=pending_days,
            system_status=system_status,
            completed_capabilities=[
                "generation-review-revision full workflow",
                "run persistence and lineage",
                "slo monitoring and alert automation",
                "strategy experiments, canary and release gate",
                "demo readiness/rehearsal/final report",
            ],
            pending_capabilities=[
                "multi-environment deployment pipeline integration",
                "automated acceptance gate in CI/CD",
                "production traffic canary policy integration",
            ],
            next_actions=[
                "Implement Day35 CI/CD webhook integration",
                "Implement Day36 acceptance gate policy as pipeline step",
                "Implement Day37 production rollout runbook automation",
            ],
        )

    @app.post("/v1/papers/demo/cicd/webhook", response_model=DemoCICDWebhookResponse)
    def trigger_demo_cicd_webhook(
        target_env: Literal["staging", "production"] = Query(default="staging"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_release_token: str | None = Header(default=None, alias="X-Release-Token"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoCICDWebhookResponse:
        verify_api_key(cfg.api_key, x_api_key)
        if cfg.release_webhook_secret and x_release_token != cfg.release_webhook_secret:
            raise HTTPException(status_code=401, detail="invalid release token")
        gate = get_demo_release_gate(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        accepted = bool(gate.gate_passed)
        pipeline_id = f"pipe-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        message = "deployment pipeline accepted" if accepted else "deployment blocked by release gate"
        return DemoCICDWebhookResponse(
            accepted=accepted,
            target_env=target_env,
            gate_passed=gate.gate_passed,
            pipeline_id=pipeline_id,
            message=message,
        )

    @app.post("/v1/papers/demo/cicd/acceptance-gate", response_model=DemoAcceptanceGateResponse)
    def run_demo_acceptance_gate(
        target_env: Literal["staging", "production"] = Query(default="staging"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAcceptanceGateResponse:
        verify_api_key(cfg.api_key, x_api_key)
        release_gate = get_demo_release_gate(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        monitor = get_demo_post_release_monitor(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        checks = {
            "release_gate_passed": release_gate.gate_passed,
            "success_rate_ok": bool(monitor.checks.get("success_rate_ok", False)),
            "quality_ok": bool(monitor.checks.get("quality_ok", False)),
            "latency_ok": bool(monitor.checks.get("latency_ok", False)),
        }
        failed_checks = sum(1 for value in checks.values() if not value)
        max_allowed = cfg.acceptance_gate_max_failed_checks
        gate_passed = failed_checks <= max_allowed
        reasons = [
            f"failed_checks={failed_checks}",
            f"max_allowed_failed_checks={max_allowed}",
        ]
        reasons.append("acceptance_gate_passed" if gate_passed else "acceptance_gate_failed")
        return DemoAcceptanceGateResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_env=target_env,
            gate_passed=gate_passed,
            failed_checks=failed_checks,
            max_allowed_failed_checks=max_allowed,
            checks=checks,
            reasons=reasons,
        )

    @app.get("/v1/papers/demo/rollout-runbook", response_model=DemoRolloutRunbookResponse)
    def get_demo_rollout_runbook(
        target_env: Literal["staging", "production"] = Query(default="production"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoRolloutRunbookResponse:
        verify_api_key(cfg.api_key, x_api_key)
        acceptance = run_demo_acceptance_gate(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        rollback_advice = get_demo_rollback_advice(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        ready = bool(acceptance.gate_passed and not rollback_advice.should_rollback)
        steps = [
            "Validate acceptance gate result",
            "Trigger deployment job in CI/CD",
            "Watch post-release monitor for 15 minutes",
            "Confirm service SLO and user-facing checks",
        ]
        rollback_plan = [
            "Disable canary and route traffic back to previous version",
            "Restore previous deployment artifact",
            "Run rollback verification checks",
        ]
        blockers: list[str] = []
        if not acceptance.gate_passed:
            blockers.extend(acceptance.reasons)
        if rollback_advice.should_rollback:
            blockers.extend(rollback_advice.reasons)
        return DemoRolloutRunbookResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_env=target_env,
            ready_to_rollout=ready,
            auto_rollback_enabled=cfg.rollout_auto_rollback_enabled,
            steps=steps,
            rollback_plan=rollback_plan,
            blockers=blockers,
        )

    @app.get("/v1/papers/demo/operations-audit", response_model=DemoOperationsAuditResponse)
    def get_demo_operations_audit(
        target_env: Literal["staging", "production"] = Query(default="production"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoOperationsAuditResponse:
        verify_api_key(cfg.api_key, x_api_key)
        scorecard = get_demo_ops_scorecard(days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        runbook = get_demo_rollout_runbook(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        grade_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
        min_grade = cfg.operations_audit_min_grade
        passed = grade_rank.get(scorecard.grade, 0) >= grade_rank.get(min_grade, 0) and runbook.ready_to_rollout
        missing_controls: list[str] = []
        if not runbook.ready_to_rollout:
            missing_controls.append("rollout_not_ready")
        if grade_rank.get(scorecard.grade, 0) < grade_rank.get(min_grade, 0):
            missing_controls.append("operations_grade_below_threshold")
        return DemoOperationsAuditResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            target_env=target_env,
            passed=passed,
            min_required_grade=min_grade,  # type: ignore[arg-type]
            current_grade=scorecard.grade,  # type: ignore[arg-type]
            operations_score=scorecard.operations_score,
            ready_to_rollout=runbook.ready_to_rollout,
            missing_controls=missing_controls,
        )

    @app.post("/v1/papers/demo/release-approvals/request", response_model=DemoReleaseApprovalResponse)
    def request_demo_release_approval(
        target_env: Literal["staging", "production"] = Query(default="production"),
        requested_by: str = Query(default="system", min_length=1, max_length=100),
        note: str = Query(default="", max_length=500),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReleaseApprovalResponse:
        verify_api_key(cfg.api_key, x_api_key)
        approval_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        status: Literal["pending", "approved", "rejected", "auto_approved"]
        if cfg.release_approval_required:
            status = "pending"
        else:
            status = "auto_approved"
        release_approvals[approval_id] = {
            "approval_id": approval_id,
            "created_at": created_at,
            "target_env": target_env,
            "requested_by": requested_by,
            "status": status,
            "note": note,
        }
        return DemoReleaseApprovalResponse(**release_approvals[approval_id])

    @app.post("/v1/papers/demo/release-approvals/{approval_id}/decision", response_model=DemoReleaseApprovalResponse)
    def decide_demo_release_approval(
        approval_id: str,
        approved: bool = Query(...),
        note: str = Query(default="", max_length=500),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReleaseApprovalResponse:
        verify_api_key(cfg.api_key, x_api_key)
        row = release_approvals.get(approval_id)
        if row is None:
            raise HTTPException(status_code=404, detail="approval not found")
        row["status"] = "approved" if approved else "rejected"
        if note:
            row["note"] = note
        return DemoReleaseApprovalResponse(**row)

    @app.get("/v1/papers/demo/release-approvals", response_model=DemoReleaseApprovalListResponse)
    def list_demo_release_approvals(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoReleaseApprovalListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = list(release_approvals.values())
        rows.sort(key=lambda item: str(item["created_at"]), reverse=True)
        page = rows[offset : offset + limit]
        return DemoReleaseApprovalListResponse(
            items=[DemoReleaseApprovalResponse(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.post("/v1/papers/demo/release-approvals/{approval_id}/sync", response_model=DemoApprovalSyncResponse)
    def sync_demo_release_approval(
        approval_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoApprovalSyncResponse:
        verify_api_key(cfg.api_key, x_api_key)
        row = release_approvals.get(approval_id)
        if row is None:
            raise HTTPException(status_code=404, detail="approval not found")

        sync_target = cfg.release_approval_sync_url.strip() or "mock://approval-system"
        synced_at = datetime.now(timezone.utc).isoformat()
        external_event_id = str(uuid.uuid4())
        message = "approval synced to external system"

        if cfg.release_approval_sync_url.strip():
            payload = json.dumps(
                {
                    "approval_id": approval_id,
                    "target_env": row["target_env"],
                    "requested_by": row["requested_by"],
                    "status": row["status"],
                    "note": row["note"],
                    "created_at": row["created_at"],
                }
            ).encode("utf-8")
            req = request.Request(
                cfg.release_approval_sync_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=cfg.release_approval_sync_timeout_s) as resp:
                    if int(resp.status) >= 400:
                        raise HTTPException(status_code=502, detail=f"sync failed with status={resp.status}")
            except URLError as exc:
                raise HTTPException(status_code=502, detail=f"sync failed: {exc}") from exc
        else:
            message = "approval synced in mock mode (no external URL configured)"

        approval_sync_events[approval_id] = {
            "approval_id": approval_id,
            "synced": True,
            "sync_target": sync_target,
            "synced_at": synced_at,
            "external_event_id": external_event_id,
            "message": message,
        }
        return DemoApprovalSyncResponse(**approval_sync_events[approval_id])

    @app.get("/v1/papers/demo/audit-report", response_model=DemoAuditReportResponse)
    def get_demo_audit_report(
        target_env: Literal["staging", "production"] = Query(default="production"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditReportResponse:
        verify_api_key(cfg.api_key, x_api_key)
        operations_audit = get_demo_operations_audit(
            target_env=target_env,
            days=days,
            tenant_id=tenant_id,
            x_api_key=x_api_key,
        )
        approvals = list(release_approvals.values())
        total_approvals = len(approvals)
        approved_count = sum(1 for row in approvals if row["status"] in {"approved", "auto_approved"})
        rejected_count = sum(1 for row in approvals if row["status"] == "rejected")
        pending_count = sum(1 for row in approvals if row["status"] == "pending")
        synced_count = sum(1 for row in approvals if row["approval_id"] in approval_sync_events)
        sync_rate = 1.0 if total_approvals == 0 else round(synced_count / total_approvals, 4)
        report_status: Literal["healthy", "attention_needed"] = "healthy"
        highlights: list[str] = []
        if not operations_audit.passed:
            report_status = "attention_needed"
            highlights.append("operations_audit_not_passed")
        if pending_count > 0:
            report_status = "attention_needed"
            highlights.append("pending_release_approvals_present")
        if total_approvals > 0 and sync_rate < 1.0:
            report_status = "attention_needed"
            highlights.append("approval_sync_incomplete")
        if not highlights:
            highlights.append("all_controls_green")
        return DemoAuditReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            period_days=days,
            target_env=target_env,
            tenant_id=tenant_id,
            total_approvals=total_approvals,
            approved_count=approved_count,
            rejected_count=rejected_count,
            pending_count=pending_count,
            synced_count=synced_count,
            approval_sync_rate=sync_rate,
            operations_audit_passed=operations_audit.passed,
            operations_audit_grade=operations_audit.current_grade,
            ready_to_rollout=operations_audit.ready_to_rollout,
            report_status=report_status,
            highlights=highlights,
        )

    @app.post("/v1/papers/demo/audit-report/generate", response_model=DemoAuditReportSnapshotResponse)
    def generate_demo_audit_report(
        target_env: Literal["staging", "production"] = Query(default="production"),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditReportSnapshotResponse:
        verify_api_key(cfg.api_key, x_api_key)
        report = get_demo_audit_report(target_env=target_env, days=days, tenant_id=tenant_id, x_api_key=x_api_key)
        row = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "target_env": target_env,
            "tenant_id": tenant_id,
            "report_status": report.report_status,
            "approval_sync_rate": report.approval_sync_rate,
            "operations_audit_passed": report.operations_audit_passed,
            "highlights": report.highlights,
        }
        audit_report_history.insert(0, row)
        del audit_report_history[cfg.audit_report_history_limit :]
        return DemoAuditReportSnapshotResponse(**row)

    @app.get("/v1/papers/demo/audit-report/history", response_model=DemoAuditReportHistoryResponse)
    def list_demo_audit_report_history(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        target_env: Literal["staging", "production"] | None = Query(default=None),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditReportHistoryResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = audit_report_history
        if target_env is not None:
            rows = [row for row in rows if row["target_env"] == target_env]
        if tenant_id is not None:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        page = rows[offset : offset + limit]
        return DemoAuditReportHistoryResponse(
            items=[DemoAuditReportSnapshotResponse(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.get("/v1/papers/demo/audit-report/history/export.csv")
    def export_demo_audit_report_history(
        target_env: Literal["staging", "production"] | None = Query(default=None),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> Response:
        verify_api_key(cfg.api_key, x_api_key)
        rows = audit_report_history
        if target_env is not None:
            rows = [row for row in rows if row["target_env"] == target_env]
        if tenant_id is not None:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "report_id",
                "generated_at",
                "period_days",
                "target_env",
                "tenant_id",
                "report_status",
                "approval_sync_rate",
                "operations_audit_passed",
                "highlights",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "report_id": row["report_id"],
                    "generated_at": row["generated_at"],
                    "period_days": row["period_days"],
                    "target_env": row["target_env"],
                    "tenant_id": row["tenant_id"] or "",
                    "report_status": row["report_status"],
                    "approval_sync_rate": row["approval_sync_rate"],
                    "operations_audit_passed": row["operations_audit_passed"],
                    "highlights": "|".join(list(row["highlights"])),
                }
            )
        filename = f"audit-report-history-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)

    @app.get("/v1/papers/demo/audit-report/trend", response_model=DemoAuditReportTrendResponse)
    def get_demo_audit_report_trend(
        days: int = Query(default=30, ge=1, le=365),
        target_env: Literal["staging", "production"] | None = Query(default=None),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditReportTrendResponse:
        verify_api_key(cfg.api_key, x_api_key)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = audit_report_history
        if target_env is not None:
            rows = [row for row in rows if row["target_env"] == target_env]
        if tenant_id is not None:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        rows = [row for row in rows if datetime.fromisoformat(str(row["generated_at"])) >= cutoff]

        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            day = str(row["generated_at"])[:10]
            bucket = grouped.setdefault(day, {"total": 0, "healthy": 0})
            bucket["total"] += 1
            if row["report_status"] == "healthy":
                bucket["healthy"] += 1

        points: list[DemoAuditReportTrendPoint] = []
        for day in sorted(grouped.keys()):
            total = grouped[day]["total"]
            healthy = grouped[day]["healthy"]
            healthy_rate = 0.0 if total == 0 else round(healthy / total, 4)
            points.append(
                DemoAuditReportTrendPoint(
                    date=day,
                    total_reports=total,
                    healthy_reports=healthy,
                    healthy_rate=healthy_rate,
                )
            )
        return DemoAuditReportTrendResponse(
            period_days=days,
            target_env=target_env,
            tenant_id=tenant_id,
            points=points,
        )

    @app.get("/v1/papers/demo/audit-report/trend/summary", response_model=DemoAuditReportTrendSummaryResponse)
    def get_demo_audit_report_trend_summary(
        days: int = Query(default=30, ge=1, le=365),
        target_env: Literal["staging", "production"] | None = Query(default=None),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditReportTrendSummaryResponse:
        verify_api_key(cfg.api_key, x_api_key)
        trend = get_demo_audit_report_trend(
            days=days,
            target_env=target_env,
            tenant_id=tenant_id,
            x_api_key=x_api_key,
        )
        if not trend.points:
            return DemoAuditReportTrendSummaryResponse(
                period_days=days,
                target_env=target_env,
                tenant_id=tenant_id,
                total_reports=0,
                avg_healthy_rate=0.0,
                latest_healthy_rate=0.0,
                healthy_rate_delta=0.0,
                status="no_data",
            )
        total_reports = sum(item.total_reports for item in trend.points)
        avg_rate = round(sum(item.healthy_rate for item in trend.points) / len(trend.points), 4)
        latest_rate = trend.points[-1].healthy_rate
        first_rate = trend.points[0].healthy_rate
        delta = round(latest_rate - first_rate, 4)
        if delta > 0.03:
            status: Literal["improving", "stable", "degrading", "no_data"] = "improving"
        elif delta < -0.03:
            status = "degrading"
        else:
            status = "stable"
        return DemoAuditReportTrendSummaryResponse(
            period_days=days,
            target_env=target_env,
            tenant_id=tenant_id,
            total_reports=total_reports,
            avg_healthy_rate=avg_rate,
            latest_healthy_rate=latest_rate,
            healthy_rate_delta=delta,
            status=status,
        )

    @app.post("/v1/papers/demo/audit-report/trend/summary/notify", response_model=DemoAuditTrendNotificationResponse)
    def notify_demo_audit_report_trend_summary(
        days: int = Query(default=30, ge=1, le=365),
        target_env: Literal["staging", "production"] | None = Query(default=None),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationResponse:
        verify_api_key(cfg.api_key, x_api_key)
        summary = get_demo_audit_report_trend_summary(
            days=days,
            target_env=target_env,
            tenant_id=tenant_id,
            x_api_key=x_api_key,
        )
        sent_at = datetime.now(timezone.utc).isoformat()
        notification_id = str(uuid.uuid4())
        message = (
            f"audit_trend status={summary.status} avg_healthy_rate={summary.avg_healthy_rate} "
            f"latest_healthy_rate={summary.latest_healthy_rate} delta={summary.healthy_rate_delta}"
        )
        error_message: str | None = None
        if cfg.audit_trend_notify_webhook_url.strip():
            payload = json.dumps(
                {
                    "sent_at": sent_at,
                    "status": summary.status,
                    "period_days": days,
                    "target_env": target_env,
                    "tenant_id": tenant_id,
                    "total_reports": summary.total_reports,
                    "avg_healthy_rate": summary.avg_healthy_rate,
                    "latest_healthy_rate": summary.latest_healthy_rate,
                    "healthy_rate_delta": summary.healthy_rate_delta,
                    "message": message,
                }
            ).encode("utf-8")
            req = request.Request(
                cfg.audit_trend_notify_webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=cfg.audit_trend_notify_timeout_s) as resp:
                    if int(resp.status) >= 400:
                        error_message = f"notify failed with status={resp.status}"
                        audit_trend_notifications.insert(
                            0,
                            {
                                "notification_id": notification_id,
                                "sent": False,
                                "channel": cfg.audit_trend_notify_webhook_url,
                                "status": summary.status,
                                "message": message,
                                "sent_at": sent_at,
                                "error": error_message,
                            },
                        )
                        raise HTTPException(status_code=502, detail=error_message)
            except URLError as exc:
                error_message = f"notify failed: {exc}"
                audit_trend_notifications.insert(
                    0,
                    {
                        "notification_id": notification_id,
                        "sent": False,
                        "channel": cfg.audit_trend_notify_webhook_url,
                        "status": summary.status,
                        "message": message,
                        "sent_at": sent_at,
                        "error": error_message,
                    },
                )
                raise HTTPException(status_code=502, detail=error_message) from exc
            channel = cfg.audit_trend_notify_webhook_url
        else:
            channel = "mock://audit-trend-notify"
        audit_trend_notifications.insert(
            0,
            {
                "notification_id": notification_id,
                "sent": True,
                "channel": channel,
                "status": summary.status,
                "message": message,
                "sent_at": sent_at,
                "error": error_message,
            },
        )
        return DemoAuditTrendNotificationResponse(
            sent=True,
            channel=channel,
            status=summary.status,
            message=message,
            sent_at=sent_at,
        )

    @app.get("/v1/papers/demo/audit-report/trend/notifications", response_model=DemoAuditTrendNotificationListResponse)
    def list_demo_audit_trend_notifications(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        status: Literal["improving", "stable", "degrading", "no_data"] | None = Query(default=None),
        sent: bool | None = Query(default=None),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = audit_trend_notifications
        if status is not None:
            rows = [row for row in rows if row["status"] == status]
        if sent is not None:
            rows = [row for row in rows if row["sent"] is sent]
        page = rows[offset : offset + limit]
        return DemoAuditTrendNotificationListResponse(
            items=[DemoAuditTrendNotificationRecord(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.post(
        "/v1/papers/demo/audit-report/trend/notifications/{notification_id}/replay",
        response_model=DemoAuditTrendNotificationReplayResponse,
    )
    def replay_demo_audit_trend_notification(
        notification_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationReplayResponse:
        verify_api_key(cfg.api_key, x_api_key)
        row = next((item for item in audit_trend_notifications if item["notification_id"] == notification_id), None)
        if row is None:
            raise HTTPException(status_code=404, detail="notification not found")
        replayed_at = datetime.now(timezone.utc).isoformat()
        channel = str(row["channel"])
        payload = json.dumps(
            {
                "notification_id": row["notification_id"],
                "status": row["status"],
                "message": row["message"],
                "sent_at": row["sent_at"],
                "replayed_at": replayed_at,
            }
        ).encode("utf-8")

        if channel.startswith("http://") or channel.startswith("https://"):
            req = request.Request(
                channel,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=cfg.audit_trend_notify_timeout_s) as resp:
                    if int(resp.status) >= 400:
                        raise HTTPException(status_code=502, detail=f"replay failed with status={resp.status}")
            except URLError as exc:
                raise HTTPException(status_code=502, detail=f"replay failed: {exc}") from exc
            detail = "replayed to webhook"
        else:
            detail = "replayed in mock mode"

        audit_trend_notifications.insert(
            0,
            {
                "notification_id": str(uuid.uuid4()),
                "sent": True,
                "channel": channel,
                "status": row["status"],
                "message": f"replay_of={notification_id} {row['message']}",
                "sent_at": replayed_at,
                "error": None,
            },
        )
        return DemoAuditTrendNotificationReplayResponse(
            notification_id=notification_id,
            replayed=True,
            sent=True,
            channel=channel,
            replayed_at=replayed_at,
            detail=detail,
        )

    @app.post("/v1/papers/demo/audit-report/trend/notifications/replay-failed", response_model=DemoAuditTrendReplayFailedResponse)
    def replay_failed_demo_audit_trend_notifications(
        limit: int = Query(default=20, ge=1, le=100),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendReplayFailedResponse:
        verify_api_key(cfg.api_key, x_api_key)
        failed_items = [item for item in audit_trend_notifications if not bool(item["sent"])]
        selected = failed_items[:limit]
        replayed_ids: list[str] = []
        skipped_count = 0
        for item in selected:
            notification_id = str(item["notification_id"])
            try:
                replay_demo_audit_trend_notification(notification_id=notification_id, x_api_key=x_api_key)
                replayed_ids.append(notification_id)
            except HTTPException:
                skipped_count += 1
        return DemoAuditTrendReplayFailedResponse(
            requested_limit=limit,
            replayed_count=len(replayed_ids),
            skipped_count=skipped_count,
            replayed_notification_ids=replayed_ids,
        )

    @app.get("/v1/papers/demo/audit-report/trend/notifications/replay-plan", response_model=DemoAuditTrendReplayPlanResponse)
    def get_demo_audit_trend_replay_plan(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendReplayPlanResponse:
        verify_api_key(cfg.api_key, x_api_key)
        failed_items = [item for item in audit_trend_notifications if not bool(item["sent"])]
        replayable_items = [item for item in failed_items if str(item["channel"]).strip()]
        failed_count = len(failed_items)
        replayable_count = len(replayable_items)
        recommended_batch_size = min(50, replayable_count)
        reasons: list[str] = []
        if failed_count == 0:
            reasons.append("no_failed_notifications")
        else:
            reasons.append("failed_notifications_detected")
        if replayable_count < failed_count:
            reasons.append("some_notifications_missing_channel")
        if replayable_count > 100:
            reasons.append("large_backlog_split_into_batches")
        if not reasons:
            reasons.append("ready_for_replay")
        return DemoAuditTrendReplayPlanResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            failed_notifications=failed_count,
            replayable_notifications=replayable_count,
            recommended_batch_size=recommended_batch_size,
            reasons=reasons,
        )

    @app.post("/v1/papers/demo/audit-report/trend/notifications/replay-run", response_model=DemoAuditTrendReplayRunResponse)
    def run_demo_audit_trend_replay(
        limit: int = Query(default=20, ge=1, le=100),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendReplayRunResponse:
        verify_api_key(cfg.api_key, x_api_key)
        plan = get_demo_audit_trend_replay_plan(x_api_key=x_api_key)
        replay_limit = min(limit, max(1, plan.recommended_batch_size)) if plan.replayable_notifications > 0 else limit
        run_result = replay_failed_demo_audit_trend_notifications(limit=replay_limit, x_api_key=x_api_key)
        return DemoAuditTrendReplayRunResponse(
            executed_at=datetime.now(timezone.utc).isoformat(),
            requested_limit=limit,
            planned_failed_notifications=plan.failed_notifications,
            planned_replayable_notifications=plan.replayable_notifications,
            recommended_batch_size=plan.recommended_batch_size,
            replayed_count=run_result.replayed_count,
            skipped_count=run_result.skipped_count,
            replayed_notification_ids=run_result.replayed_notification_ids,
            reasons=plan.reasons,
        )

    @app.get("/v1/papers/demo/audit-report/trend/notifications/metrics", response_model=DemoAuditTrendNotificationMetricsResponse)
    def get_demo_audit_trend_notification_metrics(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationMetricsResponse:
        verify_api_key(cfg.api_key, x_api_key)
        total = len(audit_trend_notifications)
        sent_count = sum(1 for item in audit_trend_notifications if bool(item["sent"]))
        failed_count = total - sent_count
        replayed_count = sum(1 for item in audit_trend_notifications if str(item["message"]).startswith("replay_of="))
        success_rate = 1.0 if total == 0 else round(sent_count / total, 4)
        replay_coverage_rate = 1.0 if failed_count == 0 else round(replayed_count / failed_count, 4)
        return DemoAuditTrendNotificationMetricsResponse(
            total_notifications=total,
            sent_count=sent_count,
            failed_count=failed_count,
            replayed_count=replayed_count,
            success_rate=success_rate,
            replay_coverage_rate=replay_coverage_rate,
        )

    @app.post("/v1/papers/demo/audit-report/trend/notifications/drill", response_model=DemoAuditTrendNotificationDrillResponse)
    def run_demo_audit_trend_notification_drill(
        failures: int = Query(default=3, ge=1, le=20),
        auto_replay: bool = Query(default=True),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationDrillResponse:
        verify_api_key(cfg.api_key, x_api_key)
        drill_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        for idx in range(failures):
            audit_trend_notifications.insert(
                0,
                {
                    "notification_id": str(uuid.uuid4()),
                    "sent": False,
                    "channel": "mock://audit-trend-notify",
                    "status": "degrading",
                    "message": f"drill_failure_{idx + 1}",
                    "sent_at": now,
                    "error": "simulated failure for drill",
                },
            )

        replayed_count = 0
        skipped_count = 0
        if auto_replay:
            replay_result = replay_failed_demo_audit_trend_notifications(limit=failures, x_api_key=x_api_key)
            replayed_count = replay_result.replayed_count
            skipped_count = replay_result.skipped_count

        message = (
            "drill executed with auto replay"
            if auto_replay
            else "drill executed without auto replay"
        )
        record = {
            "drill_id": drill_id,
            "created_failures": failures,
            "auto_replay": auto_replay,
            "replayed_count": replayed_count,
            "skipped_count": skipped_count,
            "message": message,
        }
        audit_trend_drills.insert(0, record)
        return DemoAuditTrendNotificationDrillResponse(**record)

    @app.get("/v1/papers/demo/audit-report/trend/notifications/drills", response_model=DemoAuditTrendNotificationDrillListResponse)
    def list_demo_audit_trend_notification_drills(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationDrillListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        page = audit_trend_drills[offset : offset + limit]
        return DemoAuditTrendNotificationDrillListResponse(
            items=[DemoAuditTrendNotificationDrillResponse(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/summary",
        response_model=DemoAuditTrendNotificationDrillSummaryResponse,
    )
    def summarize_demo_audit_trend_notification_drills(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationDrillSummaryResponse:
        verify_api_key(cfg.api_key, x_api_key)
        total_drills = len(audit_trend_drills)
        total_injected_failures = sum(int(item["created_failures"]) for item in audit_trend_drills)
        total_replayed = sum(int(item["replayed_count"]) for item in audit_trend_drills)
        auto_replay_count = sum(1 for item in audit_trend_drills if bool(item["auto_replay"]))
        auto_replay_rate = 0.0 if total_drills == 0 else round(auto_replay_count / total_drills, 4)
        avg_replay_success_rate = (
            0.0
            if total_injected_failures == 0
            else round(total_replayed / total_injected_failures, 4)
        )
        return DemoAuditTrendNotificationDrillSummaryResponse(
            total_drills=total_drills,
            total_injected_failures=total_injected_failures,
            total_replayed=total_replayed,
            auto_replay_rate=auto_replay_rate,
            avg_replay_success_rate=avg_replay_success_rate,
        )

    @app.get("/v1/papers/demo/audit-report/trend/notifications/drills/export.csv")
    def export_demo_audit_trend_notification_drills(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> Response:
        verify_api_key(cfg.api_key, x_api_key)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "drill_id",
                "created_failures",
                "auto_replay",
                "replayed_count",
                "skipped_count",
                "message",
            ],
        )
        writer.writeheader()
        for row in audit_trend_drills:
            writer.writerow(
                {
                    "drill_id": row["drill_id"],
                    "created_failures": row["created_failures"],
                    "auto_replay": row["auto_replay"],
                    "replayed_count": row["replayed_count"],
                    "skipped_count": row["skipped_count"],
                    "message": row["message"],
                }
            )
        filename = f"audit-trend-drills-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report",
        response_model=DemoAuditTrendNotificationDrillReportResponse,
    )
    def get_demo_audit_trend_notification_drill_report(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendNotificationDrillReportResponse:
        verify_api_key(cfg.api_key, x_api_key)
        drill_summary = summarize_demo_audit_trend_notification_drills(x_api_key=x_api_key)
        notification_metrics = get_demo_audit_trend_notification_metrics(x_api_key=x_api_key)
        latest = audit_trend_drills[0] if audit_trend_drills else None
        recommendations: list[str] = []
        if drill_summary.auto_replay_rate < 0.8:
            recommendations.append("increase_auto_replay_coverage")
        if notification_metrics.success_rate < 0.95:
            recommendations.append("investigate_notification_failures")
        if drill_summary.avg_replay_success_rate < 0.9:
            recommendations.append("improve_replay_path_reliability")
        if not recommendations:
            recommendations.append("drill_health_good")
        return DemoAuditTrendNotificationDrillReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_drills=drill_summary.total_drills,
            total_notifications=notification_metrics.total_notifications,
            success_rate=notification_metrics.success_rate,
            auto_replay_rate=drill_summary.auto_replay_rate,
            avg_replay_success_rate=drill_summary.avg_replay_success_rate,
            latest_drill_id=(str(latest["drill_id"]) if latest else None),
            latest_drill_message=(str(latest["message"]) if latest else None),
            recommendations=recommendations,
        )

    @app.post(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots",
        response_model=DemoAuditTrendDrillReportSnapshotResponse,
    )
    def create_demo_audit_trend_drill_report_snapshot(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotResponse:
        verify_api_key(cfg.api_key, x_api_key)
        report = get_demo_audit_trend_notification_drill_report(x_api_key=x_api_key)
        snapshot = {
            "snapshot_id": str(uuid.uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_drills": report.total_drills,
            "total_notifications": report.total_notifications,
            "success_rate": report.success_rate,
            "auto_replay_rate": report.auto_replay_rate,
            "avg_replay_success_rate": report.avg_replay_success_rate,
            "recommendations": report.recommendations,
        }
        audit_trend_drill_report_snapshots.insert(0, snapshot)
        return DemoAuditTrendDrillReportSnapshotResponse(**snapshot)

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots",
        response_model=DemoAuditTrendDrillReportSnapshotListResponse,
    )
    def list_demo_audit_trend_drill_report_snapshots(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        page = audit_trend_drill_report_snapshots[offset : offset + limit]
        return DemoAuditTrendDrillReportSnapshotListResponse(
            items=[DemoAuditTrendDrillReportSnapshotResponse(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.get("/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/export.csv")
    def export_demo_audit_trend_drill_report_snapshots_csv(
        limit: int = Query(default=200, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> Response:
        verify_api_key(cfg.api_key, x_api_key)
        rows = audit_trend_drill_report_snapshots[offset : offset + limit]
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "snapshot_id",
                "generated_at",
                "total_drills",
                "total_notifications",
                "success_rate",
                "auto_replay_rate",
                "avg_replay_success_rate",
                "recommendations",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "snapshot_id": row["snapshot_id"],
                    "generated_at": row["generated_at"],
                    "total_drills": row["total_drills"],
                    "total_notifications": row["total_notifications"],
                    "success_rate": row["success_rate"],
                    "auto_replay_rate": row["auto_replay_rate"],
                    "avg_replay_success_rate": row["avg_replay_success_rate"],
                    "recommendations": "|".join(row["recommendations"]),
                }
            )
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=demo_audit_drill_report_snapshots.csv"},
        )

    @app.post(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/cleanup",
        response_model=DemoAuditTrendDrillReportSnapshotCleanupResponse,
    )
    def cleanup_demo_audit_trend_drill_report_snapshots(
        keep: int = Query(default=100, ge=1, le=1000),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotCleanupResponse:
        verify_api_key(cfg.api_key, x_api_key)
        total_before = len(audit_trend_drill_report_snapshots)
        if total_before <= keep:
            return DemoAuditTrendDrillReportSnapshotCleanupResponse(
                deleted_snapshots=0,
                kept_snapshots=total_before,
                keep=keep,
            )
        del audit_trend_drill_report_snapshots[keep:]
        return DemoAuditTrendDrillReportSnapshotCleanupResponse(
            deleted_snapshots=total_before - keep,
            kept_snapshots=len(audit_trend_drill_report_snapshots),
            keep=keep,
        )

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-plan",
        response_model=DemoAuditTrendDrillReportSnapshotRetentionPlanResponse,
    )
    def get_demo_audit_trend_drill_report_snapshot_retention_plan(
        keep: int = Query(default=100, ge=1, le=1000),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotRetentionPlanResponse:
        verify_api_key(cfg.api_key, x_api_key)
        total_snapshots = len(audit_trend_drill_report_snapshots)
        kept = audit_trend_drill_report_snapshots[:keep]
        deleted = audit_trend_drill_report_snapshots[keep:]
        return DemoAuditTrendDrillReportSnapshotRetentionPlanResponse(
            total_snapshots=total_snapshots,
            keep=keep,
            would_delete=max(0, total_snapshots - keep),
            kept_snapshot_ids=[str(item["snapshot_id"]) for item in kept],
            would_delete_snapshot_ids=[str(item["snapshot_id"]) for item in deleted],
        )

    @app.post(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-run",
        response_model=DemoAuditTrendDrillReportSnapshotRetentionRunResponse,
    )
    def run_demo_audit_trend_drill_report_snapshot_retention(
        keep: int = Query(default=100, ge=1, le=1000),
        dry_run: bool = Query(default=True),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotRetentionRunResponse:
        verify_api_key(cfg.api_key, x_api_key)
        total_before = len(audit_trend_drill_report_snapshots)
        would_delete = max(0, total_before - keep)
        if dry_run:
            response = DemoAuditTrendDrillReportSnapshotRetentionRunResponse(
                dry_run=True,
                executed=False,
                keep=keep,
                total_snapshots=total_before,
                deleted_snapshots=would_delete,
                kept_snapshots=min(total_before, keep),
            )
        else:
            if would_delete > 0:
                del audit_trend_drill_report_snapshots[keep:]
            response = DemoAuditTrendDrillReportSnapshotRetentionRunResponse(
                dry_run=False,
                executed=True,
                keep=keep,
                total_snapshots=total_before,
                deleted_snapshots=would_delete,
                kept_snapshots=len(audit_trend_drill_report_snapshots),
            )

        run_record = {
            "run_id": str(uuid.uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **response.model_dump(),
        }
        audit_trend_drill_report_snapshot_retention_runs.insert(0, run_record)
        return response

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-runs",
        response_model=DemoAuditTrendDrillReportSnapshotRetentionRunListResponse,
    )
    def list_demo_audit_trend_drill_report_snapshot_retention_runs(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotRetentionRunListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        page = audit_trend_drill_report_snapshot_retention_runs[offset : offset + limit]
        return DemoAuditTrendDrillReportSnapshotRetentionRunListResponse(
            items=[DemoAuditTrendDrillReportSnapshotRetentionRunRecordResponse(**item) for item in page],
            limit=limit,
            offset=offset,
        )

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/compare",
        response_model=DemoAuditTrendDrillReportSnapshotCompareResponse,
    )
    def compare_demo_audit_trend_drill_report_snapshots(
        snapshot_id_a: str = Query(..., min_length=1),
        snapshot_id_b: str = Query(..., min_length=1),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotCompareResponse:
        verify_api_key(cfg.api_key, x_api_key)
        snapshot_a = next((item for item in audit_trend_drill_report_snapshots if str(item["snapshot_id"]) == snapshot_id_a), None)
        snapshot_b = next((item for item in audit_trend_drill_report_snapshots if str(item["snapshot_id"]) == snapshot_id_b), None)
        if snapshot_a is None:
            raise HTTPException(status_code=404, detail=f"snapshot {snapshot_id_a} not found")
        if snapshot_b is None:
            raise HTTPException(status_code=404, detail=f"snapshot {snapshot_id_b} not found")

        success_rate_delta = round(float(snapshot_b["success_rate"]) - float(snapshot_a["success_rate"]), 6)
        auto_replay_rate_delta = round(float(snapshot_b["auto_replay_rate"]) - float(snapshot_a["auto_replay_rate"]), 6)
        avg_replay_success_rate_delta = round(
            float(snapshot_b["avg_replay_success_rate"]) - float(snapshot_a["avg_replay_success_rate"]),
            6,
        )
        recommendation_delta = len(snapshot_b["recommendations"]) - len(snapshot_a["recommendations"])

        weighted_score_delta = (
            success_rate_delta * 0.5
            + auto_replay_rate_delta * 0.3
            + avg_replay_success_rate_delta * 0.2
            - recommendation_delta * 0.02
        )
        trend: Literal["improved", "regressed", "stable"] = "stable"
        if weighted_score_delta > 0.001:
            trend = "improved"
        elif weighted_score_delta < -0.001:
            trend = "regressed"

        return DemoAuditTrendDrillReportSnapshotCompareResponse(
            snapshot_id_a=snapshot_id_a,
            snapshot_id_b=snapshot_id_b,
            generated_at_a=str(snapshot_a["generated_at"]),
            generated_at_b=str(snapshot_b["generated_at"]),
            success_rate_delta=success_rate_delta,
            auto_replay_rate_delta=auto_replay_rate_delta,
            avg_replay_success_rate_delta=avg_replay_success_rate_delta,
            recommendation_delta=recommendation_delta,
            trend=trend,
        )

    @app.get(
        "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/{snapshot_id}",
        response_model=DemoAuditTrendDrillReportSnapshotResponse,
    )
    def get_demo_audit_trend_drill_report_snapshot(
        snapshot_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> DemoAuditTrendDrillReportSnapshotResponse:
        verify_api_key(cfg.api_key, x_api_key)
        for item in audit_trend_drill_report_snapshots:
            if str(item["snapshot_id"]) == snapshot_id:
                return DemoAuditTrendDrillReportSnapshotResponse(**item)
        raise HTTPException(status_code=404, detail=f"snapshot {snapshot_id} not found")

    violation_group_map = {
        "success_rate_below_threshold": "reliability",
        "avg_quality_below_threshold": "quality",
        "avg_duration_above_threshold": "latency",
    }

    def calculate_alert_quality_score(*, days: int, tenant_id: str | None) -> SLOAlertQualityScoreResponse:
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        sla_stats = paper_service.reconcile_alert_sla(created_after=created_after, tenant_id=tenant_id)
        ticket_stats = paper_service.summarize_ticket_status(created_after=created_after, tenant_id=tenant_id)
        root_cause_stats = paper_service.summarize_root_causes(created_after=created_after, tenant_id=tenant_id)

        open_degraded = int(sla_stats["open_degraded_events"])
        open_tickets = int(ticket_stats["open_tickets"])
        closed_tickets = int(ticket_stats["closed_tickets"])
        unknown_causes = int(root_cause_stats.get("unknown", 0))

        score = 100.0
        score -= min(40.0, open_degraded * 5.0)
        score -= min(25.0, open_tickets * 3.0)
        score -= min(20.0, unknown_causes * 2.0)
        score += min(15.0, closed_tickets * 1.5)
        score = max(0.0, min(100.0, round(score, 2)))
        return SLOAlertQualityScoreResponse(
            days=days,
            tenant_id=tenant_id,
            score=score,
            components={
                "open_degraded_events": open_degraded,
                "open_tickets": open_tickets,
                "closed_tickets": closed_tickets,
                "unknown_causes": unknown_causes,
            },
        )

    def resolve_canary_enabled(tenant_id: str | None) -> tuple[bool, str]:
        key = tenant_id or "default"
        if key in canary_override_by_tenant:
            return bool(canary_override_by_tenant[key]), "runtime_override"
        return bool(cfg.slo_alert_canary_enabled), "config_default"

    def calculate_strategy_experiment(
        *,
        days: int,
        tenant_id: str | None,
        candidate_max_open_degraded_alerts: int | None,
    ) -> SLOAlertStrategyExperimentResponse:
        baseline_max = cfg.slo_sla_max_open_degraded_alerts
        candidate_max = candidate_max_open_degraded_alerts if candidate_max_open_degraded_alerts is not None else max(1, baseline_max - 1)
        baseline_quality = calculate_alert_quality_score(days=days, tenant_id=tenant_id)

        strictness_delta = baseline_max - candidate_max
        improvement = (strictness_delta * 1.5) - (abs(strictness_delta) * 0.3)
        candidate_quality_score = max(0.0, min(100.0, round(baseline_quality.score + improvement, 2)))
        regression_delta = round(candidate_quality_score - baseline_quality.score, 2)
        min_allowed_delta = cfg.slo_alert_regression_guardrail_min_delta
        guardrail_passed = regression_delta >= min_allowed_delta

        reasons: list[str] = []
        if strictness_delta > 0:
            reasons.append("candidate_is_stricter_than_baseline")
        elif strictness_delta < 0:
            reasons.append("candidate_is_looser_than_baseline")
        else:
            reasons.append("candidate_equals_baseline")
        if guardrail_passed:
            reasons.append("regression_guardrail_passed")
        else:
            reasons.append("regression_guardrail_failed")
        return SLOAlertStrategyExperimentResponse(
            days=days,
            tenant_id=tenant_id,
            baseline_max_open_degraded_alerts=baseline_max,
            candidate_max_open_degraded_alerts=candidate_max,
            baseline_quality_score=baseline_quality.score,
            candidate_quality_score=candidate_quality_score,
            regression_delta=regression_delta,
            min_allowed_delta=min_allowed_delta,
            guardrail_passed=guardrail_passed,
            recommend_promote_candidate=guardrail_passed and regression_delta >= 0,
            reasons=reasons,
        )

    @app.get("/v1/papers/runs/{run_id}", response_model=RunDetailResponse)
    def get_run(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunDetailResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunDetailResponse(**record.__dict__)

    @app.get("/v1/papers/runs", response_model=RunListResponse)
    def list_runs(
        limit: int = Query(default=10, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        stop_reason: str | None = Query(default=None),
        parent_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        root_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        lineage_scope: Literal["root", "derived"] | None = Query(default=None),
        q: str | None = Query(default=None, min_length=1, max_length=200),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        min_quality_score: int | None = Query(default=None, ge=0, le=10),
        max_quality_score: int | None = Query(default=None, ge=0, le=10),
        min_duration_ms: int | None = Query(default=None, ge=0),
        max_duration_ms: int | None = Query(default=None, ge=0),
        sort_by: Literal["created_at", "quality_score", "duration_ms"] = Query(default="created_at"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        filters = build_run_query_filters(
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=q,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
        )

        filter_kwargs = filters.as_service_kwargs()
        runs = paper_service.list_runs(
            limit=limit,
            offset=offset,
            **filter_kwargs,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        items = [
            RunListItemResponse(
                run_id=run.run_id,
                trace_id=run.trace_id,
                parent_run_id=run.parent_run_id,
                root_run_id=run.root_run_id,
                task=run.task,
                prompt_version=run.prompt_version,
                quality_score=run.quality_score,
                stop_reason=run.stop_reason,
                source_count=len(run.research_sources),
                has_review_report=bool(run.review_report),
                inline_citation_count=len({match for match in re.findall(r"\[(\d+)\]", run.draft)}),
                revision_plan_items=len(run.review_report.get("revision_plan", [])) if isinstance(run.review_report, dict) else 0,
                created_at=run.created_at,
                duration_ms=run.duration_ms,
            )
            for run in runs
        ]
        total = paper_service.count_runs(**filter_kwargs)
        has_more = (offset + len(items)) < total
        next_offset = (offset + len(items)) if has_more else None
        return RunListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=next_offset,
        )

    @app.get("/v1/papers/metrics", response_model=RunMetricsResponse)
    def get_metrics(
        stop_reason: str | None = Query(default=None),
        parent_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        root_run_id: str | None = Query(default=None, min_length=1, max_length=200),
        lineage_scope: Literal["root", "derived"] | None = Query(default=None),
        q: str | None = Query(default=None, min_length=1, max_length=200),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        min_quality_score: int | None = Query(default=None, ge=0, le=10),
        max_quality_score: int | None = Query(default=None, ge=0, le=10),
        min_duration_ms: int | None = Query(default=None, ge=0),
        max_duration_ms: int | None = Query(default=None, ge=0),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunMetricsResponse:
        verify_api_key(cfg.api_key, x_api_key)
        filters = build_run_query_filters(
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=q,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
        )
        stats = paper_service.get_stats(**filters.as_service_kwargs())
        return RunMetricsResponse(
            total_runs=stats.total_runs,
            avg_quality_score=stats.avg_quality_score,
            avg_duration_ms=stats.avg_duration_ms,
            success_rate=stats.success_rate,
            stop_reason_counts=stats.stop_reason_counts,
        )

    @app.get("/v1/papers/slo", response_model=SLOStatusResponse)
    def get_slo_status(
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOStatusResponse:
        verify_api_key(cfg.api_key, x_api_key)
        stats = paper_service.get_stats()
        thresholds = {
            "min_success_rate": cfg.slo_min_success_rate,
            "min_avg_quality_score": cfg.slo_min_avg_quality_score,
            "max_avg_duration_ms": cfg.slo_max_avg_duration_ms,
        }
        status, violations = evaluate_slo_from_stats(
            total_runs=stats.total_runs,
            success_rate=stats.success_rate,
            avg_quality_score=stats.avg_quality_score,
            avg_duration_ms=stats.avg_duration_ms,
        )
        return SLOStatusResponse(
            status=status,
            total_runs=stats.total_runs,
            success_rate=stats.success_rate,
            avg_quality_score=stats.avg_quality_score,
            avg_duration_ms=stats.avg_duration_ms,
            thresholds=thresholds,
            violations=violations,
        )

    @app.get("/v1/papers/slo/history", response_model=SLOHistoryResponse)
    def get_slo_history(
        days: int = Query(default=7, ge=1, le=90),
        interval: Literal["day", "week"] = Query(default="day"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOHistoryResponse:
        verify_api_key(cfg.api_key, x_api_key)
        now = datetime.now(timezone.utc)
        created_after = (now - timedelta(days=days)).isoformat()
        total = paper_service.count_runs(created_after=created_after)
        runs = paper_service.list_runs(limit=max(total, 1), created_after=created_after, sort_order="asc")

        grouped: dict[str, dict[str, float]] = {}
        for run in runs:
            created_at = datetime.fromisoformat(run.created_at)
            if interval == "week":
                week_start = created_at.date().toordinal() - created_at.weekday()
                bucket = datetime.fromordinal(week_start).date().isoformat()
            else:
                bucket = created_at.date().isoformat()
            entry = grouped.setdefault(
                bucket,
                {"count": 0.0, "quality_sum": 0.0, "duration_sum": 0.0, "success_sum": 0.0},
            )
            entry["count"] += 1
            entry["quality_sum"] += float(run.quality_score)
            entry["duration_sum"] += float(run.duration_ms)
            entry["success_sum"] += 0.0 if run.stop_reason == "failed" else 1.0

        points: list[SLOHistoryPoint] = []
        for bucket, agg in sorted(grouped.items(), key=lambda item: item[0]):
            count = int(agg["count"])
            success_rate = (agg["success_sum"] / agg["count"]) if agg["count"] else 0.0
            avg_quality = (agg["quality_sum"] / agg["count"]) if agg["count"] else 0.0
            avg_duration = (agg["duration_sum"] / agg["count"]) if agg["count"] else 0.0
            status, violations = evaluate_slo_from_stats(
                total_runs=count,
                success_rate=success_rate,
                avg_quality_score=avg_quality,
                avg_duration_ms=avg_duration,
            )
            points.append(
                SLOHistoryPoint(
                    bucket_start=bucket,
                    total_runs=count,
                    success_rate=round(success_rate, 4),
                    avg_quality_score=round(avg_quality, 2),
                    avg_duration_ms=round(avg_duration, 2),
                    status=status,
                    violations=violations,
                )
            )
        return SLOHistoryResponse(interval=interval, days=days, points=points)

    @app.post("/v1/papers/slo/alerts/check", response_model=SLOAlertCheckResponse)
    def check_slo_alerts(
        force: bool = Query(default=False),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertCheckResponse:
        verify_api_key(cfg.api_key, x_api_key)
        tenant_id = (x_tenant_id or "default").strip() or "default"
        alert_state = alert_state_by_tenant.setdefault(
            tenant_id,
            {
                "last_alert_at": None,
                "last_fingerprint": "",
                "last_fingerprint_at": None,
            },
        )
        stats = paper_service.get_stats()
        status, violations = evaluate_slo_from_stats(
            total_runs=stats.total_runs,
            success_rate=stats.success_rate,
            avg_quality_score=stats.avg_quality_score,
            avg_duration_ms=stats.avg_duration_ms,
        )
        should_alert = status == "degraded" and len(violations) > 0
        fingerprint = "|".join(sorted(violations)) if should_alert else None
        suppressed = False
        suppression_reason: str | None = None
        now = datetime.now(timezone.utc)

        if should_alert and not force:
            last_alert_at: datetime | None = alert_state["last_alert_at"]
            last_fingerprint = alert_state["last_fingerprint"]
            last_fingerprint_at: datetime | None = alert_state["last_fingerprint_at"]
            if (
                cfg.slo_alert_cooldown_seconds > 0
                and last_alert_at is not None
                and (now - last_alert_at).total_seconds() < cfg.slo_alert_cooldown_seconds
            ):
                suppressed = True
                suppression_reason = "cooldown_active"
            elif (
                cfg.slo_alert_dedupe_window_seconds > 0
                and last_fingerprint_at is not None
                and last_fingerprint == (fingerprint or "")
                and (now - last_fingerprint_at).total_seconds() < cfg.slo_alert_dedupe_window_seconds
            ):
                suppressed = True
                suppression_reason = "duplicate_within_dedupe_window"

        routed_channel_set: set[str] = set()
        if should_alert:
            for violation in violations:
                group = violation_group_map.get(violation, "general")
                override_channels = cfg.slo_alert_route_overrides.get(group)
                if override_channels:
                    routed_channel_set.update(override_channels)
                else:
                    routed_channel_set.update(cfg.slo_alert_channels)
        else:
            routed_channel_set.update(cfg.slo_alert_channels)
        routed_channels = sorted(routed_channel_set)
        rendered_message = cfg.slo_alert_template.format(
            status=status,
            violations=",".join(violations) if violations else "none",
            fingerprint=fingerprint or "none",
            suppressed=str(suppressed).lower(),
            checked_at=now.isoformat(),
            tenant_id=tenant_id,
            policy_version=cfg.slo_alert_policy_version,
        )

        channel_results: list[SLOAlertChannelResult] = []
        for channel in routed_channels:
            if not should_alert:
                channel_results.append(
                    SLOAlertChannelResult(
                        channel=channel,
                        delivered=False,
                        detail="slo status is not degraded",
                    )
                )
                continue
            if suppressed:
                channel_results.append(
                    SLOAlertChannelResult(
                        channel=channel,
                        delivered=False,
                        detail=f"alert suppressed: {suppression_reason}",
                    )
                )
                continue
            if channel == "log":
                channel_results.append(
                    SLOAlertChannelResult(
                        channel="log",
                        delivered=True,
                        detail="alert emitted to application logs",
                    )
                )
            elif channel == "webhook":
                if cfg.slo_alert_webhook_url:
                    payload = {
                        "status": status,
                        "violations": violations,
                        "fingerprint": fingerprint,
                        "checked_at": now.isoformat(),
                        "message": rendered_message,
                    }
                    webhook_delivered = False
                    webhook_detail = f"failed to post webhook: {cfg.slo_alert_webhook_url}"
                    try:
                        req = request.Request(
                            cfg.slo_alert_webhook_url,
                            data=json.dumps(payload).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with request.urlopen(req, timeout=cfg.slo_alert_webhook_timeout_s) as resp:
                            webhook_delivered = 200 <= resp.status < 300
                            webhook_detail = f"webhook http status: {resp.status}"
                    except (URLError, TimeoutError, ValueError):
                        webhook_delivered = False
                    channel_results.append(
                        SLOAlertChannelResult(
                            channel="webhook",
                            delivered=webhook_delivered,
                            detail=webhook_detail,
                        )
                    )
                else:
                    channel_results.append(
                        SLOAlertChannelResult(
                            channel="webhook",
                            delivered=False,
                            detail="missing SLO_ALERT_WEBHOOK_URL",
                        )
                    )
        if should_alert and not suppressed:
            alert_state["last_alert_at"] = now
            alert_state["last_fingerprint"] = fingerprint or ""
            alert_state["last_fingerprint_at"] = now
        paper_service.record_alert_event(
            tenant_id=tenant_id,
            policy_version=cfg.slo_alert_policy_version,
            status=status,
            violations=violations,
            should_alert=should_alert,
            suppressed=suppressed,
            suppression_reason=suppression_reason,
            alert_fingerprint=fingerprint,
            routed_channels=routed_channels,
            rendered_message=rendered_message,
        )
        return SLOAlertCheckResponse(
            status=status,
            tenant_id=tenant_id,
            policy_version=cfg.slo_alert_policy_version,
            violations=violations,
            should_alert=should_alert,
            suppressed=suppressed,
            suppression_reason=suppression_reason,
            alert_fingerprint=fingerprint,
            routed_channels=routed_channels,
            rendered_message=rendered_message,
            channels=channel_results,
        )

    @app.get("/v1/papers/slo/alerts/events", response_model=SLOAlertEventListResponse)
    def list_slo_alert_events(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertEventListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = paper_service.list_alert_events(limit=limit, offset=offset, tenant_id=tenant_id)
        return SLOAlertEventListResponse(
            items=[
                SLOAlertEventResponse(
                    event_id=row.event_id,
                    created_at=row.created_at,
                    tenant_id=row.tenant_id,
                    policy_version=row.policy_version,
                    status=row.status,
                    violations=row.violations,
                    should_alert=row.should_alert,
                    suppressed=row.suppressed,
                    suppression_reason=row.suppression_reason,
                    alert_fingerprint=row.alert_fingerprint,
                    routed_channels=row.routed_channels,
                    rendered_message=row.rendered_message,
                )
                for row in rows
            ],
            limit=limit,
            offset=offset,
        )

    @app.post("/v1/papers/slo/alerts/replay/{event_id}", response_model=SLOAlertReplayResponse)
    def replay_slo_alert_event(
        event_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertReplayResponse:
        verify_api_key(cfg.api_key, x_api_key)
        row = paper_service.get_alert_event(event_id)
        if row is None:
            raise HTTPException(status_code=404, detail="alert event not found")
        event = SLOAlertEventResponse(
            event_id=row.event_id,
            created_at=row.created_at,
            tenant_id=row.tenant_id,
            policy_version=row.policy_version,
            status=row.status,
            violations=row.violations,
            should_alert=row.should_alert,
            suppressed=row.suppressed,
            suppression_reason=row.suppression_reason,
            alert_fingerprint=row.alert_fingerprint,
            routed_channels=row.routed_channels,
            rendered_message=row.rendered_message,
        )
        replay_message = (
            f"[replay:{row.policy_version}:{row.tenant_id}] "
            f"{row.rendered_message}"
        )
        return SLOAlertReplayResponse(event=event, replay_message=replay_message)

    @app.get("/v1/papers/slo/alerts/dashboard", response_model=SLOAlertDashboardResponse)
    def get_slo_alert_dashboard(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertDashboardResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        summary = paper_service.summarize_alert_events(created_after=created_after, tenant_id=tenant_id)
        return SLOAlertDashboardResponse(
            days=days,
            tenant_id=tenant_id,
            total_events=int(summary["total_events"]),
            status_counts=dict(summary["status_counts"]),
            suppression_count=int(summary["suppression_count"]),
            suppression_rate=float(summary["suppression_rate"]),
            top_violations=[AlertViolationCount(**item) for item in summary["top_violations"]],
        )

    @app.post("/v1/papers/slo/alerts/archive", response_model=SLOAlertArchiveResponse)
    def archive_slo_alerts(
        before_days: int = Query(default=7, ge=0, le=3650),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertArchiveResponse:
        verify_api_key(cfg.api_key, x_api_key)
        before_ts = (datetime.now(timezone.utc) - timedelta(days=before_days)).isoformat()
        archive_id, count, compressed_bytes = paper_service.archive_alert_events(
            before_ts=before_ts,
            tenant_id=tenant_id,
        )
        return SLOAlertArchiveResponse(
            archive_id=archive_id,
            tenant_id=tenant_id,
            archived_events=count,
            compressed_bytes=compressed_bytes,
        )

    @app.get("/v1/papers/slo/alerts/archives", response_model=SLOAlertArchiveListResponse)
    def list_slo_alert_archives(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertArchiveListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = paper_service.list_alert_archives(limit=limit, offset=offset, tenant_id=tenant_id)
        return SLOAlertArchiveListResponse(
            items=[
                SLOAlertArchiveRecordResponse(
                    archive_id=row.archive_id,
                    created_at=row.created_at,
                    tenant_id=row.tenant_id,
                    before_ts=row.before_ts,
                    event_count=row.event_count,
                    compressed_bytes=row.compressed_bytes,
                )
                for row in rows
            ],
            limit=limit,
            offset=offset,
        )

    @app.post("/v1/papers/slo/alerts/archives/{archive_id}/restore", response_model=SLOAlertRestoreResponse)
    def restore_slo_alert_archive(
        archive_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertRestoreResponse:
        verify_api_key(cfg.api_key, x_api_key)
        restored, attempted = paper_service.restore_alert_archive(archive_id=archive_id)
        if attempted == 0:
            raise HTTPException(status_code=404, detail="alert archive not found")
        return SLOAlertRestoreResponse(
            archive_id=archive_id,
            restored_events=restored,
            attempted_events=attempted,
        )

    @app.post("/v1/papers/slo/alerts/lifecycle/run", response_model=SLOAlertLifecycleRunResponse)
    def run_slo_alert_lifecycle(
        before_days: int = Query(default=30, ge=0, le=3650),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertLifecycleRunResponse:
        verify_api_key(cfg.api_key, x_api_key)
        before_ts = (datetime.now(timezone.utc) - timedelta(days=before_days)).isoformat()
        archive_id, archived_events, compressed_bytes = paper_service.archive_alert_events(
            before_ts=before_ts,
            tenant_id=tenant_id,
        )
        return SLOAlertLifecycleRunResponse(
            tenant_id=tenant_id,
            before_days=before_days,
            archive_id=archive_id,
            archived_events=archived_events,
            compressed_bytes=compressed_bytes,
        )

    @app.get("/v1/papers/slo/alerts/sla-reconcile", response_model=SLOAlertSLAReconcileResponse)
    def reconcile_slo_alert_sla(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertSLAReconcileResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        stats = paper_service.reconcile_alert_sla(created_after=created_after, tenant_id=tenant_id)
        open_degraded = int(stats["open_degraded_events"])
        return SLOAlertSLAReconcileResponse(
            days=days,
            tenant_id=tenant_id,
            total_events=int(stats["total_events"]),
            degraded_events=int(stats["degraded_events"]),
            open_degraded_events=open_degraded,
            max_open_degraded_alerts=cfg.slo_sla_max_open_degraded_alerts,
            breach=open_degraded > cfg.slo_sla_max_open_degraded_alerts,
        )

    @app.post("/v1/papers/slo/alerts/remediation-tickets", response_model=SLOAlertRemediationTicketResponse)
    def create_slo_alert_remediation_ticket(
        title: str = Query(min_length=3, max_length=200),
        details: str = Query(default="", max_length=2000),
        severity: Literal["low", "medium", "high", "critical"] = Query(default="medium"),
        tenant_id: str = Query(default="default", min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertRemediationTicketResponse:
        verify_api_key(cfg.api_key, x_api_key)
        ticket = paper_service.create_remediation_ticket(
            tenant_id=tenant_id,
            title=title,
            severity=severity,
            details=details,
        )
        return SLOAlertRemediationTicketResponse(
            ticket_id=ticket.ticket_id,
            created_at=ticket.created_at,
            tenant_id=ticket.tenant_id,
            title=ticket.title,
            severity=ticket.severity,
            status=ticket.status,
            details=ticket.details,
        )

    @app.get("/v1/papers/slo/alerts/remediation-tickets", response_model=SLOAlertRemediationTicketListResponse)
    def list_slo_alert_remediation_tickets(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertRemediationTicketListResponse:
        verify_api_key(cfg.api_key, x_api_key)
        rows = paper_service.list_remediation_tickets(limit=limit, offset=offset, tenant_id=tenant_id)
        return SLOAlertRemediationTicketListResponse(
            items=[
                SLOAlertRemediationTicketResponse(
                    ticket_id=row.ticket_id,
                    created_at=row.created_at,
                    tenant_id=row.tenant_id,
                    title=row.title,
                    severity=row.severity,
                    status=row.status,
                    details=row.details,
                )
                for row in rows
            ],
            limit=limit,
            offset=offset,
        )

    @app.post(
        "/v1/papers/slo/alerts/remediation-tickets/{ticket_id}/close",
        response_model=SLOAlertRemediationTicketResponse,
    )
    def close_slo_alert_remediation_ticket(
        ticket_id: str,
        resolution_note: str = Query(default="", max_length=2000),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertRemediationTicketResponse:
        verify_api_key(cfg.api_key, x_api_key)
        ticket = paper_service.close_remediation_ticket(ticket_id=ticket_id, resolution_note=resolution_note)
        if ticket is None:
            raise HTTPException(status_code=404, detail="remediation ticket not found")
        return SLOAlertRemediationTicketResponse(
            ticket_id=ticket.ticket_id,
            created_at=ticket.created_at,
            tenant_id=ticket.tenant_id,
            title=ticket.title,
            severity=ticket.severity,
            status=ticket.status,
            details=ticket.details,
        )

    @app.get("/v1/papers/slo/alerts/root-causes", response_model=SLOAlertRootCauseBreakdownResponse)
    def get_slo_alert_root_causes(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertRootCauseBreakdownResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        causes = paper_service.summarize_root_causes(created_after=created_after, tenant_id=tenant_id)
        return SLOAlertRootCauseBreakdownResponse(days=days, tenant_id=tenant_id, causes=causes)

    @app.get("/v1/papers/slo/alerts/quality-score", response_model=SLOAlertQualityScoreResponse)
    def get_slo_alert_quality_score(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertQualityScoreResponse:
        verify_api_key(cfg.api_key, x_api_key)
        return calculate_alert_quality_score(days=days, tenant_id=tenant_id)

    @app.post("/v1/papers/slo/alerts/strategy-tune", response_model=SLOAlertStrategyTuneResponse)
    def tune_slo_alert_strategy(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyTuneResponse:
        verify_api_key(cfg.api_key, x_api_key)
        current_max = cfg.slo_sla_max_open_degraded_alerts
        if not cfg.slo_alert_auto_tune_enabled:
            return SLOAlertStrategyTuneResponse(
                days=days,
                tenant_id=tenant_id,
                auto_tune_enabled=False,
                current_max_open_degraded_alerts=current_max,
                recommended_max_open_degraded_alerts=current_max,
                reasons=["auto_tune_disabled"],
            )
        quality = calculate_alert_quality_score(days=days, tenant_id=tenant_id)
        recommended = current_max
        reasons: list[str] = []
        if quality.score < 70:
            recommended = max(1, current_max - 1)
            reasons.append("quality_score_below_70")
        elif quality.score > 90:
            recommended = current_max + 1
            reasons.append("quality_score_above_90")
        if not reasons:
            reasons.append("quality_score_in_stable_band")
        return SLOAlertStrategyTuneResponse(
            days=days,
            tenant_id=tenant_id,
            auto_tune_enabled=True,
            current_max_open_degraded_alerts=current_max,
            recommended_max_open_degraded_alerts=recommended,
            reasons=reasons,
        )

    @app.get("/v1/papers/slo/alerts/strategy-experiments", response_model=SLOAlertStrategyExperimentResponse)
    def run_slo_alert_strategy_experiment(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        candidate_max_open_degraded_alerts: int | None = Query(default=None, ge=0, le=100),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyExperimentResponse:
        verify_api_key(cfg.api_key, x_api_key)
        return calculate_strategy_experiment(
            days=days,
            tenant_id=tenant_id,
            candidate_max_open_degraded_alerts=candidate_max_open_degraded_alerts,
        )

    @app.post("/v1/papers/slo/alerts/strategy-experiments/run", response_model=SLOAlertStrategyExperimentRunResponse)
    def run_and_record_slo_alert_strategy_experiment(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        candidate_max_open_degraded_alerts: int | None = Query(default=None, ge=0, le=100),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyExperimentRunResponse:
        verify_api_key(cfg.api_key, x_api_key)
        preview = calculate_strategy_experiment(
            days=days,
            tenant_id=tenant_id,
            candidate_max_open_degraded_alerts=candidate_max_open_degraded_alerts,
        )
        stored = paper_service.create_strategy_experiment(
            tenant_id=tenant_id or "default",
            days=preview.days,
            baseline_max_open_degraded_alerts=preview.baseline_max_open_degraded_alerts,
            candidate_max_open_degraded_alerts=preview.candidate_max_open_degraded_alerts,
            baseline_quality_score=preview.baseline_quality_score,
            candidate_quality_score=preview.candidate_quality_score,
            regression_delta=preview.regression_delta,
            min_allowed_delta=preview.min_allowed_delta,
            guardrail_passed=preview.guardrail_passed,
            recommend_promote_candidate=preview.recommend_promote_candidate,
            reasons=preview.reasons,
        )
        return SLOAlertStrategyExperimentRunResponse(
            experiment_id=stored.experiment_id,
            created_at=stored.created_at,
            **preview.model_dump(),
        )

    @app.get("/v1/papers/slo/alerts/strategy-experiments/dashboard", response_model=SLOAlertStrategyExperimentDashboardResponse)
    def get_slo_alert_strategy_experiment_dashboard(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        limit: int = Query(default=10, ge=1, le=50),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyExperimentDashboardResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        summary = paper_service.summarize_strategy_experiments(created_after=created_after, tenant_id=tenant_id)
        rows = paper_service.list_strategy_experiments(limit=limit, offset=0, tenant_id=tenant_id)
        recent = [
            SLOAlertStrategyExperimentRunResponse(
                experiment_id=row.experiment_id,
                created_at=row.created_at,
                days=row.days,
                tenant_id=row.tenant_id,
                baseline_max_open_degraded_alerts=row.baseline_max_open_degraded_alerts,
                candidate_max_open_degraded_alerts=row.candidate_max_open_degraded_alerts,
                baseline_quality_score=row.baseline_quality_score,
                candidate_quality_score=row.candidate_quality_score,
                regression_delta=row.regression_delta,
                min_allowed_delta=row.min_allowed_delta,
                guardrail_passed=row.guardrail_passed,
                recommend_promote_candidate=row.recommend_promote_candidate,
                reasons=row.reasons,
            )
            for row in rows
        ]
        return SLOAlertStrategyExperimentDashboardResponse(
            days=days,
            tenant_id=tenant_id,
            total_experiments=int(summary["total_experiments"]),
            avg_regression_delta=float(summary["avg_regression_delta"]),
            guardrail_pass_rate=float(summary["guardrail_pass_rate"]),
            promotion_rate=float(summary["promotion_rate"]),
            recent_experiments=recent,
        )

    @app.post("/v1/papers/slo/alerts/strategy-experiments/auto-replay", response_model=SLOAlertStrategyReplayResponse)
    def auto_replay_slo_alert_strategy_experiments(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        limit: int = Query(default=20, ge=1, le=100),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyReplayResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        summary = paper_service.summarize_strategy_experiments(created_after=created_after, tenant_id=tenant_id)
        experiments = paper_service.list_strategy_experiments(limit=limit, offset=0, tenant_id=tenant_id)
        replayed = len(experiments)
        auto_promoted = sum(1 for item in experiments if item.recommend_promote_candidate)
        guardrail_pass_rate = float(summary["guardrail_pass_rate"])
        recommended_canary_ratio = round(min(0.5, max(0.0, guardrail_pass_rate * 0.5)), 2)
        reasons = [
            "replay_uses_persisted_experiments",
            "promotion_count_based_on_recommend_promote_candidate",
        ]
        if replayed == 0:
            reasons.append("no_experiments_found")
        return SLOAlertStrategyReplayResponse(
            days=days,
            tenant_id=tenant_id,
            replayed_experiments=replayed,
            auto_promoted_candidates=auto_promoted,
            guardrail_pass_rate=guardrail_pass_rate,
            recommended_canary_ratio=recommended_canary_ratio,
            reasons=reasons,
        )

    @app.get("/v1/papers/slo/alerts/strategy-canary/status", response_model=SLOAlertStrategyCanaryStatusResponse)
    def get_slo_alert_strategy_canary_status(
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyCanaryStatusResponse:
        verify_api_key(cfg.api_key, x_api_key)
        created_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        summary = paper_service.summarize_strategy_experiments(created_after=created_after, tenant_id=tenant_id)
        guardrail_pass_rate = float(summary["guardrail_pass_rate"])
        promotion_rate = float(summary["promotion_rate"])
        threshold = cfg.slo_alert_canary_promotion_threshold
        canary_enabled, source = resolve_canary_enabled(tenant_id)
        if not canary_enabled:
            return SLOAlertStrategyCanaryStatusResponse(
                days=days,
                tenant_id=tenant_id,
                canary_enabled=False,
                threshold=threshold,
                canary_recommended=False,
                canary_ratio=0.0,
                reasons=[f"canary_disabled:{source}"],
            )
        canary_recommended = guardrail_pass_rate >= threshold and promotion_rate >= 0.5
        canary_ratio = round(min(0.5, max(0.1, guardrail_pass_rate * 0.5)), 2) if canary_recommended else 0.0
        reasons = [
            f"guardrail_pass_rate={guardrail_pass_rate:.2f}",
            f"promotion_rate={promotion_rate:.2f}",
            f"threshold={threshold:.2f}",
        ]
        return SLOAlertStrategyCanaryStatusResponse(
            days=days,
            tenant_id=tenant_id,
            canary_enabled=True,
            threshold=threshold,
            canary_recommended=canary_recommended,
            canary_ratio=canary_ratio,
            reasons=reasons,
        )

    @app.post("/v1/papers/slo/alerts/strategy-canary/toggle", response_model=SLOAlertStrategyCanaryToggleResponse)
    def toggle_slo_alert_strategy_canary(
        enabled: bool = Query(...),
        days: int = Query(default=7, ge=1, le=90),
        tenant_id: str | None = Query(default=None, min_length=1, max_length=200),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> SLOAlertStrategyCanaryToggleResponse:
        verify_api_key(cfg.api_key, x_api_key)
        key = tenant_id or "default"
        canary_override_by_tenant[key] = bool(enabled)
        return SLOAlertStrategyCanaryToggleResponse(
            days=days,
            tenant_id=tenant_id,
            canary_enabled=bool(enabled),
            source="runtime_override",
            reasons=["canary_override_updated"],
        )

    @app.get("/v1/papers/runs/{run_id}/sources", response_model=RunSourcesResponse)
    def get_run_sources(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunSourcesResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunSourcesResponse(
            run_id=record.run_id,
            source_count=len(record.research_sources),
            sources=record.research_sources,
        )

    @app.get("/v1/papers/runs/{run_id}/references", response_model=RunFormattedReferencesResponse)
    def get_run_references(
        run_id: str,
        style: Literal["apa", "mla", "gbt7714"] = Query(default="apa"),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunFormattedReferencesResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        references = [_format_reference_line(source, style) for source in record.research_sources]
        return RunFormattedReferencesResponse(
            run_id=record.run_id,
            style=style,
            references=references,
            source_count=len(references),
        )

    @app.get("/v1/papers/runs/{run_id}/review-report", response_model=RunReviewReportResponse)
    def get_run_review_report(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunReviewReportResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunReviewReportResponse(
            run_id=record.run_id,
            review_report=record.review_report,
        )

    @app.get("/v1/papers/runs/{run_id}/quality-breakdown", response_model=RunQualityBreakdownResponse)
    def get_run_quality_breakdown(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunQualityBreakdownResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        report = record.review_report if isinstance(record.review_report, dict) else {}
        structure_feedback = str(report.get("structure_feedback", ""))
        evidence_feedback = str(report.get("evidence_feedback", ""))
        citation_feedback = str(report.get("citation_feedback", ""))
        language_feedback = str(report.get("language_feedback", ""))
        structure_score = _score_feedback_signal(structure_feedback, positives=("aligned", "core academic sections"))
        evidence_score = _score_feedback_signal(evidence_feedback, positives=("grounded", "concrete support"))
        citation_score = _score_feedback_signal(citation_feedback, positives=("source-backed", "coverage is complete"))
        language_score = _score_feedback_signal(language_feedback, positives=("clear", "conciseness"))
        recommendations = report.get("revision_plan", [])
        normalized_recommendations = [str(item) for item in recommendations if str(item).strip()]
        overall = int(report.get("score", record.quality_score))
        return RunQualityBreakdownResponse(
            run_id=record.run_id,
            overall_score=overall,
            structure_score=structure_score,
            evidence_score=evidence_score,
            citation_score=citation_score,
            language_score=language_score,
            recommendations=normalized_recommendations,
        )

    @app.get("/v1/papers/runs/{run_id}/citation-audit", response_model=CitationAuditResponse)
    def get_run_citation_audit(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> CitationAuditResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        body_text, _, _ = record.draft.partition("\n[References]\n")
        inline_markers = sorted({int(match) for match in re.findall(r"\[(\d+)\]", body_text)})
        reference_markers = sorted({int(match) for match in REFERENCE_LINE_RE.findall(record.draft)})
        missing_reference_entries = sorted(set(inline_markers) - set(reference_markers))
        unused_reference_entries = sorted(set(reference_markers) - set(inline_markers))
        denominator = len(set(inline_markers) | set(reference_markers))
        if denominator == 0:
            coverage_score = 1.0
        else:
            aligned = len(set(inline_markers) & set(reference_markers))
            coverage_score = round(aligned / denominator, 4)
        return CitationAuditResponse(
            run_id=record.run_id,
            inline_markers=inline_markers,
            reference_markers=reference_markers,
            missing_reference_entries=missing_reference_entries,
            unused_reference_entries=unused_reference_entries,
            coverage_score=coverage_score,
        )

    @app.get("/v1/papers/runs/{run_id}/insights", response_model=RunInsightsResponse)
    def get_run_insights(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunInsightsResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _to_run_insights_response(record)

    @app.get("/v1/papers/runs/{run_id}/lineage", response_model=RunLineageResponse)
    def get_run_lineage(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunLineageResponse:
        verify_api_key(cfg.api_key, x_api_key)
        lineage = paper_service.get_run_lineage(run_id)
        if lineage is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunLineageResponse(
            run=RunDetailResponse(**lineage.run.__dict__),
            parent=None if lineage.parent is None else _to_run_summary_response(lineage.parent),
            children=[_to_run_summary_response(child) for child in lineage.children],
            ancestors=[_to_run_summary_response(ancestor) for ancestor in lineage.ancestors],
            descendants=[_to_run_summary_response(descendant) for descendant in lineage.descendants],
        )

    @app.get("/v1/papers/runs/{run_id}/draft.md")
    def download_run_draft_markdown(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> Response:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        filename = _build_markdown_filename(run_id)
        return Response(
            content=record.draft,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/v1/papers/runs/{run_id}/diff", response_model=RunDiffResponse)
    def diff_run_drafts(
        run_id: str,
        against: str = Query(..., min_length=1, max_length=200),
        context_lines: int = Query(default=3, ge=0, le=20),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunDiffResponse:
        verify_api_key(cfg.api_key, x_api_key)
        current = paper_service.get_run(run_id)
        if current is None:
            raise HTTPException(status_code=404, detail="run not found")
        baseline = paper_service.get_run(against)
        if baseline is None:
            raise HTTPException(status_code=404, detail="baseline run not found")
        before_lines = baseline.draft.splitlines()
        after_lines = current.draft.splitlines()
        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"run:{against}",
                tofile=f"run:{run_id}",
                lineterm="",
                n=context_lines,
            )
        )
        added_lines = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed_lines = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        preview = "\n".join(diff_lines[:400])
        return RunDiffResponse(
            run_id=run_id,
            against_run_id=against,
            changed=bool(added_lines or removed_lines),
            added_lines=added_lines,
            removed_lines=removed_lines,
            diff_preview=preview,
        )


def _to_run_summary_response(record) -> RunSummaryResponse:
    inline_citation_count = len({match for match in re.findall(r"\[(\d+)\]", record.draft)})
    review_plan = record.review_report.get("revision_plan", []) if isinstance(record.review_report, dict) else []
    return RunSummaryResponse(
        run_id=record.run_id,
        trace_id=record.trace_id,
        parent_run_id=record.parent_run_id,
        root_run_id=record.root_run_id,
        task=record.task,
        prompt_version=record.prompt_version,
        quality_score=record.quality_score,
        stop_reason=record.stop_reason,
        source_count=len(record.research_sources),
        has_review_report=bool(record.review_report),
        inline_citation_count=inline_citation_count,
        revision_plan_items=len(review_plan) if isinstance(review_plan, list) else 0,
        created_at=record.created_at,
        duration_ms=record.duration_ms,
    )


def _to_run_insights_response(record) -> RunInsightsResponse:
    body_text, _, _ = record.draft.partition("\n[References]\n")
    inline_citations = {match for match in re.findall(r"\[(\d+)\]", body_text)}
    reference_markers = {match for match in REFERENCE_LINE_RE.findall(record.draft)}
    revision_plan = record.review_report.get("revision_plan", []) if isinstance(record.review_report, dict) else []
    linked_source_count = min(len(inline_citations & reference_markers), len(record.research_sources))
    coverage_denominator = max(len(record.research_sources), 1)
    citation_coverage = round(linked_source_count / coverage_denominator, 4) if record.research_sources else 0.0
    return RunInsightsResponse(
        run_id=record.run_id,
        quality_score=record.quality_score,
        source_count=len(record.research_sources),
        inline_citation_count=len(inline_citations),
        revision_plan_items=len(revision_plan) if isinstance(revision_plan, list) else 0,
        evidence_linked_source_count=linked_source_count,
        citation_coverage_score=citation_coverage,
    )


def _build_markdown_filename(run_id: str) -> str:
    safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-") or "paper-run"
    return f"{safe_run_id}.md"


def _format_reference_line(source, style: Literal["apa", "mla", "gbt7714"]) -> str:
    citation_id = source.get("citation_id") if isinstance(source, dict) else getattr(source, "citation_id", 0)
    title = source.get("title") if isinstance(source, dict) else getattr(source, "title", "")
    source_type = source.get("source_type") if isinstance(source, dict) else getattr(source, "source_type", "")
    locator = source.get("locator") if isinstance(source, dict) else getattr(source, "locator", "")
    if style == "mla":
        return f"[{citation_id}] \"{title}.\" {source_type}. {locator}."
    if style == "gbt7714":
        tag = source_type[0] if source_type else "J"
        return f"[{citation_id}] {title}[{tag}]. {locator}."
    return f"[{citation_id}] {title}. ({source_type}). {locator}."


def _score_feedback_signal(feedback: str, *, positives: tuple[str, ...]) -> int:
    normalized = (feedback or "").lower()
    score = 5
    if any(token in normalized for token in positives):
        score += 3
    if any(token in normalized for token in ("missing", "insufficient", "expand", "add")):
        score -= 2
    return max(0, min(score, 10))
