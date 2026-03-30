from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchSourceResponse(BaseModel):
    citation_id: int
    title: str
    source_type: str
    locator: str
    excerpt: str


class ReviewReportResponse(BaseModel):
    structure_feedback: str
    evidence_feedback: str
    citation_feedback: str
    language_feedback: str
    score: int
    revision_plan: list[str]


class GeneratePaperRequest(BaseModel):
    task: str = Field(..., min_length=5, description="paper writing task")
    outline: str = Field(..., min_length=5, description="paper outline")
    revision_notes: str = Field(default="", max_length=2000, description="optional revision notes")
    paper_type: Literal["review", "empirical", "method"] | None = Field(default=None)
    tone: Literal["conservative", "neutral", "assertive"] | None = Field(default=None)
    citation_style: Literal["apa", "mla", "gbt7714"] | None = Field(default=None)
    target_venue: str | None = Field(default=None, max_length=200)
    iterations: int = Field(default=2, ge=1, le=8)


class GeneratePaperResponse(BaseModel):
    run_id: str
    trace_id: str
    created_at: str
    duration_ms: int
    draft: str
    review: str
    review_report: ReviewReportResponse | dict[str, object]
    iterations_used: int
    quality_score: int
    stop_reason: str
    prompt_version: str
    generation_params: dict[str, object]
    research_sources: list[ResearchSourceResponse]
    idempotent_replay: bool


class SaveEditedDraftRequest(BaseModel):
    draft: str = Field(..., min_length=20, description="edited markdown draft")
    review: str = Field(default="Manual edit saved from workspace.", max_length=4000)
    revision_notes: str | None = Field(default=None, max_length=2000)


class RewriteSectionRequest(BaseModel):
    section_title: str = Field(..., min_length=1, max_length=200)
    rewrite_goal: str = Field(..., min_length=5, max_length=2000)
    keep_citations: bool = Field(default=True)
    max_tokens: int = Field(default=400, ge=50, le=4000)


class RewriteSectionResponse(BaseModel):
    run_id: str
    section_title: str
    updated_section_markdown: str
    quality_delta_estimate: float


class ApplyRevisionPlanRequest(BaseModel):
    selected_items: list[str] = Field(..., min_length=1)
    mode: Literal["patch", "rewrite"] = Field(default="patch")


class RunRevisionPlanResponse(BaseModel):
    run_id: str
    items: list[str]
    total_items: int


class RunDiffResponse(BaseModel):
    run_id: str
    against_run_id: str
    changed: bool
    added_lines: int
    removed_lines: int
    diff_preview: str


class RollbackRunRequest(BaseModel):
    to_run_id: str = Field(..., min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=500)


class RunFormattedReferencesResponse(BaseModel):
    run_id: str
    style: Literal["apa", "mla", "gbt7714"]
    references: list[str]
    source_count: int


class RunQualityBreakdownResponse(BaseModel):
    run_id: str
    overall_score: int
    structure_score: int
    evidence_score: int
    citation_score: int
    language_score: int
    recommendations: list[str]


class RunDetailResponse(BaseModel):
    run_id: str
    trace_id: str
    parent_run_id: str
    root_run_id: str
    task: str
    outline: str
    revision_notes: str
    iterations_requested: int
    iterations_used: int
    quality_score: int
    stop_reason: str
    prompt_version: str
    generation_params: dict[str, object]
    draft: str
    review: str
    review_report: ReviewReportResponse | dict[str, object]
    research_sources: list[ResearchSourceResponse]
    created_at: str
    duration_ms: int


class RunSummaryResponse(BaseModel):
    run_id: str
    trace_id: str
    parent_run_id: str
    root_run_id: str
    task: str
    prompt_version: str
    quality_score: int
    stop_reason: str
    source_count: int
    has_review_report: bool
    inline_citation_count: int
    revision_plan_items: int
    created_at: str
    duration_ms: int


class RunListItemResponse(BaseModel):
    run_id: str
    trace_id: str
    parent_run_id: str
    root_run_id: str
    task: str
    prompt_version: str
    quality_score: int
    stop_reason: str
    source_count: int
    has_review_report: bool
    inline_citation_count: int
    revision_plan_items: int
    created_at: str
    duration_ms: int


class RunListResponse(BaseModel):
    items: list[RunListItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class RunSourcesResponse(BaseModel):
    run_id: str
    source_count: int
    sources: list[ResearchSourceResponse]


class RunReviewReportResponse(BaseModel):
    run_id: str
    review_report: ReviewReportResponse | dict[str, object]


class CitationAuditResponse(BaseModel):
    run_id: str
    inline_markers: list[int]
    reference_markers: list[int]
    missing_reference_entries: list[int]
    unused_reference_entries: list[int]
    coverage_score: float


class RunInsightsResponse(BaseModel):
    run_id: str
    quality_score: int
    source_count: int
    inline_citation_count: int
    revision_plan_items: int
    evidence_linked_source_count: int
    citation_coverage_score: float


class RunInsightsListResponse(BaseModel):
    items: list[RunInsightsResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class RunInsightsMetricsResponse(BaseModel):
    total_runs: int
    runs_with_review_report: int
    avg_source_count: float
    avg_inline_citation_count: float
    avg_revision_plan_items: float
    avg_citation_coverage_score: float


class InsightTrendPoint(BaseModel):
    bucket_start: str
    group_key: str | None = None
    total_runs: int
    avg_quality_score: float
    avg_inline_citation_count: float


class RunInsightsTrendsResponse(BaseModel):
    interval: str
    group_by: str
    points: list[InsightTrendPoint]


class TaskInsightRow(BaseModel):
    task: str
    run_count: int
    avg_quality_score: float
    avg_source_count: float


class TopTaskInsightsResponse(BaseModel):
    items: list[TaskInsightRow]
    total_tasks: int
    limit: int


class RunLineageResponse(BaseModel):
    run: RunDetailResponse
    parent: RunSummaryResponse | None
    children: list[RunSummaryResponse]
    ancestors: list[RunSummaryResponse]
    descendants: list[RunSummaryResponse]


class RunMetricsResponse(BaseModel):
    total_runs: int
    avg_quality_score: float
    avg_duration_ms: float
    success_rate: float
    stop_reason_counts: dict[str, int]


class SLOStatusResponse(BaseModel):
    status: Literal["ok", "degraded", "no_data"]
    total_runs: int
    success_rate: float
    avg_quality_score: float
    avg_duration_ms: float
    thresholds: dict[str, float]
    violations: list[str]


class SLOHistoryPoint(BaseModel):
    bucket_start: str
    total_runs: int
    success_rate: float
    avg_quality_score: float
    avg_duration_ms: float
    status: Literal["ok", "degraded", "no_data"]
    violations: list[str]


class SLOHistoryResponse(BaseModel):
    interval: Literal["day", "week"]
    days: int
    points: list[SLOHistoryPoint]


class SLOAlertChannelResult(BaseModel):
    channel: Literal["log", "webhook"]
    delivered: bool
    detail: str


class SLOAlertCheckResponse(BaseModel):
    status: Literal["ok", "degraded", "no_data"]
    tenant_id: str
    policy_version: str
    violations: list[str]
    should_alert: bool
    suppressed: bool
    suppression_reason: str | None = None
    alert_fingerprint: str | None = None
    routed_channels: list[Literal["log", "webhook"]]
    rendered_message: str
    channels: list[SLOAlertChannelResult]


class SLOAlertEventResponse(BaseModel):
    event_id: str
    created_at: str
    tenant_id: str
    policy_version: str
    status: Literal["ok", "degraded", "no_data"]
    violations: list[str]
    should_alert: bool
    suppressed: bool
    suppression_reason: str
    alert_fingerprint: str
    routed_channels: list[str]
    rendered_message: str


class SLOAlertEventListResponse(BaseModel):
    items: list[SLOAlertEventResponse]
    limit: int
    offset: int


class SLOAlertReplayResponse(BaseModel):
    event: SLOAlertEventResponse
    replay_message: str


class AlertViolationCount(BaseModel):
    violation: str
    count: int


class SLOAlertDashboardResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    total_events: int
    status_counts: dict[str, int]
    suppression_count: int
    suppression_rate: float
    top_violations: list[AlertViolationCount]


class SLOAlertArchiveResponse(BaseModel):
    archive_id: str
    tenant_id: str | None = None
    archived_events: int
    compressed_bytes: int


class SLOAlertArchiveRecordResponse(BaseModel):
    archive_id: str
    created_at: str
    tenant_id: str
    before_ts: str
    event_count: int
    compressed_bytes: int


class SLOAlertArchiveListResponse(BaseModel):
    items: list[SLOAlertArchiveRecordResponse]
    limit: int
    offset: int


class SLOAlertRestoreResponse(BaseModel):
    archive_id: str
    restored_events: int
    attempted_events: int


class SLOAlertLifecycleRunResponse(BaseModel):
    tenant_id: str | None = None
    before_days: int
    archive_id: str
    archived_events: int
    compressed_bytes: int


class SLOAlertSLAReconcileResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    total_events: int
    degraded_events: int
    open_degraded_events: int
    max_open_degraded_alerts: int
    breach: bool


class SLOAlertRemediationTicketResponse(BaseModel):
    ticket_id: str
    created_at: str
    tenant_id: str
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    status: str
    details: str


class SLOAlertRemediationTicketListResponse(BaseModel):
    items: list[SLOAlertRemediationTicketResponse]
    limit: int
    offset: int


class SLOAlertRootCauseBreakdownResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    causes: dict[str, int]


class SLOAlertQualityScoreResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    score: float
    components: dict[str, int]


class SLOAlertStrategyTuneResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    auto_tune_enabled: bool
    current_max_open_degraded_alerts: int
    recommended_max_open_degraded_alerts: int
    reasons: list[str]


class SLOAlertStrategyExperimentResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    baseline_max_open_degraded_alerts: int
    candidate_max_open_degraded_alerts: int
    baseline_quality_score: float
    candidate_quality_score: float
    regression_delta: float
    min_allowed_delta: float
    guardrail_passed: bool
    recommend_promote_candidate: bool
    reasons: list[str]


class SLOAlertStrategyExperimentRunResponse(SLOAlertStrategyExperimentResponse):
    experiment_id: str
    created_at: str


class SLOAlertStrategyExperimentDashboardResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    total_experiments: int
    avg_regression_delta: float
    guardrail_pass_rate: float
    promotion_rate: float
    recent_experiments: list[SLOAlertStrategyExperimentRunResponse]


class SLOAlertStrategyReplayResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    replayed_experiments: int
    auto_promoted_candidates: int
    guardrail_pass_rate: float
    recommended_canary_ratio: float
    reasons: list[str]


class SLOAlertStrategyCanaryStatusResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    canary_enabled: bool
    threshold: float
    canary_recommended: bool
    canary_ratio: float
    reasons: list[str]


class SLOAlertStrategyCanaryToggleResponse(BaseModel):
    days: int
    tenant_id: str | None = None
    canary_enabled: bool
    source: str
    reasons: list[str]


class DemoReadinessResponse(BaseModel):
    architecture_ready: bool
    quality_ready: bool
    observability_ready: bool
    demo_ready: bool
    narrative_ready: bool
    overall_ready: bool
    evidence: dict[str, object]


class DemoRehearsalResponse(BaseModel):
    started_at: str
    finished_at: str
    duration_ms: int
    checks: dict[str, bool]
    summary: str


class DemoFinalReportResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    readiness: DemoReadinessResponse
    rehearsal: DemoRehearsalResponse
    release_recommended: bool
    release_notes: list[str]


class DemoPostReleaseMonitorResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    risk_level: Literal["low", "medium", "high"]
    checks: dict[str, bool]
    metrics_snapshot: dict[str, float | int]
    canary_snapshot: dict[str, object]


class DemoRollbackAdviceResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    should_rollback: bool
    risk_level: Literal["low", "medium", "high"]
    reasons: list[str]


class DemoOpsScorecardResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    operations_score: float
    grade: Literal["A", "B", "C", "D"]
    release_recommended: bool
    rollback_recommended: bool
    highlights: list[str]
    metrics_snapshot: dict[str, float | int]


class DemoReleaseGateResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    target_env: Literal["staging", "production"]
    gate_passed: bool
    operations_score: float
    min_required_score: float
    rollback_recommended: bool
    reasons: list[str]


class DemoReleasePlanResponse(BaseModel):
    generated_at: str
    tenant_id: str | None = None
    target_env: Literal["staging", "production"]
    gate_passed: bool
    steps: list[str]
    blocker_reasons: list[str]


class DemoRoadmapStatusResponse(BaseModel):
    generated_at: str
    completed_days: list[int]
    current_day: int
    pending_days: list[int]
    system_status: Literal["operational", "needs_attention"]
    completed_capabilities: list[str]
    pending_capabilities: list[str]
    next_actions: list[str]


class DemoCICDWebhookResponse(BaseModel):
    accepted: bool
    target_env: Literal["staging", "production"]
    gate_passed: bool
    pipeline_id: str
    message: str


class DemoAcceptanceGateResponse(BaseModel):
    generated_at: str
    target_env: Literal["staging", "production"]
    gate_passed: bool
    failed_checks: int
    max_allowed_failed_checks: int
    checks: dict[str, bool]
    reasons: list[str]


class DemoRolloutRunbookResponse(BaseModel):
    generated_at: str
    target_env: Literal["staging", "production"]
    ready_to_rollout: bool
    auto_rollback_enabled: bool
    steps: list[str]
    rollback_plan: list[str]
    blockers: list[str]


class DemoOperationsAuditResponse(BaseModel):
    generated_at: str
    target_env: Literal["staging", "production"]
    passed: bool
    min_required_grade: Literal["A", "B", "C", "D"]
    current_grade: Literal["A", "B", "C", "D"]
    operations_score: float
    ready_to_rollout: bool
    missing_controls: list[str]


class DemoReleaseApprovalResponse(BaseModel):
    approval_id: str
    created_at: str
    target_env: Literal["staging", "production"]
    requested_by: str
    status: Literal["pending", "approved", "rejected", "auto_approved"]
    note: str


class DemoReleaseApprovalListResponse(BaseModel):
    items: list[DemoReleaseApprovalResponse]
    limit: int
    offset: int


class DemoApprovalSyncResponse(BaseModel):
    approval_id: str
    synced: bool
    sync_target: str
    synced_at: str | None = None
    external_event_id: str | None = None
    message: str


class DemoAuditReportResponse(BaseModel):
    generated_at: str
    period_days: int
    target_env: Literal["staging", "production"]
    tenant_id: str | None = None
    total_approvals: int
    approved_count: int
    rejected_count: int
    pending_count: int
    synced_count: int
    approval_sync_rate: float
    operations_audit_passed: bool
    operations_audit_grade: Literal["A", "B", "C", "D"]
    ready_to_rollout: bool
    report_status: Literal["healthy", "attention_needed"]
    highlights: list[str]


class DemoAuditReportSnapshotResponse(BaseModel):
    report_id: str
    generated_at: str
    period_days: int
    target_env: Literal["staging", "production"]
    tenant_id: str | None = None
    report_status: Literal["healthy", "attention_needed"]
    approval_sync_rate: float
    operations_audit_passed: bool
    highlights: list[str]


class DemoAuditReportHistoryResponse(BaseModel):
    items: list[DemoAuditReportSnapshotResponse]
    limit: int
    offset: int


class DemoAuditReportTrendPoint(BaseModel):
    date: str
    total_reports: int
    healthy_reports: int
    healthy_rate: float


class DemoAuditReportTrendResponse(BaseModel):
    period_days: int
    target_env: Literal["staging", "production"] | None = None
    tenant_id: str | None = None
    points: list[DemoAuditReportTrendPoint]


class DemoAuditReportTrendSummaryResponse(BaseModel):
    period_days: int
    target_env: Literal["staging", "production"] | None = None
    tenant_id: str | None = None
    total_reports: int
    avg_healthy_rate: float
    latest_healthy_rate: float
    healthy_rate_delta: float
    status: Literal["improving", "stable", "degrading", "no_data"]


class DemoAuditTrendNotificationResponse(BaseModel):
    sent: bool
    channel: str
    status: Literal["improving", "stable", "degrading", "no_data"]
    message: str
    sent_at: str


class DemoAuditTrendNotificationRecord(BaseModel):
    notification_id: str
    sent: bool
    channel: str
    status: Literal["improving", "stable", "degrading", "no_data"]
    message: str
    sent_at: str
    error: str | None = None


class DemoAuditTrendNotificationListResponse(BaseModel):
    items: list[DemoAuditTrendNotificationRecord]
    limit: int
    offset: int


class DemoAuditTrendNotificationReplayResponse(BaseModel):
    notification_id: str
    replayed: bool
    sent: bool
    channel: str
    replayed_at: str
    detail: str


class DemoAuditTrendReplayFailedResponse(BaseModel):
    requested_limit: int
    replayed_count: int
    skipped_count: int
    replayed_notification_ids: list[str]


class DemoAuditTrendReplayPlanResponse(BaseModel):
    generated_at: str
    failed_notifications: int
    replayable_notifications: int
    recommended_batch_size: int
    reasons: list[str]


class DemoAuditTrendReplayRunResponse(BaseModel):
    executed_at: str
    requested_limit: int
    planned_failed_notifications: int
    planned_replayable_notifications: int
    recommended_batch_size: int
    replayed_count: int
    skipped_count: int
    replayed_notification_ids: list[str]
    reasons: list[str]


class DemoAuditTrendNotificationMetricsResponse(BaseModel):
    total_notifications: int
    sent_count: int
    failed_count: int
    replayed_count: int
    success_rate: float
    replay_coverage_rate: float


class DemoAuditTrendNotificationDrillResponse(BaseModel):
    drill_id: str
    created_failures: int
    auto_replay: bool
    replayed_count: int
    skipped_count: int
    message: str


class DemoAuditTrendNotificationDrillListResponse(BaseModel):
    items: list[DemoAuditTrendNotificationDrillResponse]
    limit: int
    offset: int


class DemoAuditTrendNotificationDrillSummaryResponse(BaseModel):
    total_drills: int
    total_injected_failures: int
    total_replayed: int
    auto_replay_rate: float
    avg_replay_success_rate: float


class DemoAuditTrendNotificationDrillReportResponse(BaseModel):
    generated_at: str
    total_drills: int
    total_notifications: int
    success_rate: float
    auto_replay_rate: float
    avg_replay_success_rate: float
    latest_drill_id: str | None = None
    latest_drill_message: str | None = None
    recommendations: list[str]


class DemoAuditTrendDrillReportSnapshotResponse(BaseModel):
    snapshot_id: str
    generated_at: str
    total_drills: int
    total_notifications: int
    success_rate: float
    auto_replay_rate: float
    avg_replay_success_rate: float
    recommendations: list[str]


class DemoAuditTrendDrillReportSnapshotListResponse(BaseModel):
    items: list[DemoAuditTrendDrillReportSnapshotResponse]
    limit: int
    offset: int


class DemoAuditTrendDrillReportSnapshotCompareResponse(BaseModel):
    snapshot_id_a: str
    snapshot_id_b: str
    generated_at_a: str
    generated_at_b: str
    success_rate_delta: float
    auto_replay_rate_delta: float
    avg_replay_success_rate_delta: float
    recommendation_delta: int
    trend: Literal["improved", "regressed", "stable"]


class DemoAuditTrendDrillReportSnapshotCleanupResponse(BaseModel):
    deleted_snapshots: int
    kept_snapshots: int
    keep: int


class DemoAuditTrendDrillReportSnapshotRetentionPlanResponse(BaseModel):
    total_snapshots: int
    keep: int
    would_delete: int
    kept_snapshot_ids: list[str]
    would_delete_snapshot_ids: list[str]


class DemoAuditTrendDrillReportSnapshotRetentionRunResponse(BaseModel):
    dry_run: bool
    executed: bool
    keep: int
    total_snapshots: int
    deleted_snapshots: int
    kept_snapshots: int


class DemoAuditTrendDrillReportSnapshotRetentionRunRecordResponse(BaseModel):
    run_id: str
    generated_at: str
    dry_run: bool
    executed: bool
    keep: int
    total_snapshots: int
    deleted_snapshots: int
    kept_snapshots: int


class DemoAuditTrendDrillReportSnapshotRetentionRunListResponse(BaseModel):
    items: list[DemoAuditTrendDrillReportSnapshotRetentionRunRecordResponse]
    limit: int
    offset: int


class PurgeResponse(BaseModel):
    deleted_runs: int
    retention_days: int


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
