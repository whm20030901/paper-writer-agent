from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass


from ..agents import PaperPipeline
from .run_store import (
    AlertArchiveRecord,
    AlertEventRecord,
    AlertRemediationTicket,
    AlertStrategyExperimentRecord,
    IdempotencyConflictError,
    PipelineRunRecord,
    RunStats,
    RunStore,
)


@dataclass
class GenerateResult:
    run_id: str
    draft: str
    review: str
    review_report: dict[str, object]
    iterations_used: int
    quality_score: int
    stop_reason: str
    trace_id: str
    prompt_version: str
    generation_params: dict[str, object]
    research_sources: list[dict[str, object]]
    created_at: str
    duration_ms: int
    idempotent_replay: bool


@dataclass
class RunLineage:
    run: PipelineRunRecord
    parent: PipelineRunRecord | None
    children: list[PipelineRunRecord]
    ancestors: list[PipelineRunRecord]
    descendants: list[PipelineRunRecord]


class PaperService:
    def __init__(self, pipeline: PaperPipeline, run_store: RunStore):
        self.pipeline = pipeline
        self.run_store = run_store

    def generate(
        self,
        task: str,
        outline: str,
        iterations: int,
        revision_notes: str = "",
        idempotency_key: str | None = None,
        prompt_version: str = "v1",
        generation_params: dict[str, object] | None = None,
    ) -> GenerateResult:
        normalized_generation_params = generation_params or {}
        trace_id = str(uuid.uuid4())
        request_fingerprint = self._build_request_fingerprint(
            task=task,
            outline=outline,
            iterations=iterations,
            revision_notes=revision_notes,
            prompt_version=prompt_version,
            generation_params=normalized_generation_params,
        )
        if idempotency_key:
            binding = self.run_store.get_idempotency_binding(idempotency_key)
            if (
                binding is not None
                and binding.request_fingerprint
                and binding.request_fingerprint != request_fingerprint
            ):
                raise IdempotencyConflictError("idempotency key already used for a different request")
            existing = self.run_store.get(binding.run_id) if binding is not None else None
            if existing is not None:
                return self._build_generate_result(existing, idempotent_replay=True)

        start = time.perf_counter()
        result = self.pipeline.run(
            task=task,
            outline=outline,
            iterations=iterations,
            revision_notes=revision_notes,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        research_sources = [source.__dict__.copy() for source in getattr(result, "research_sources", [])]
        review_report = dict(getattr(result, "review_report", {}))

        record = PipelineRunRecord(
            run_id="",
            parent_run_id="",
            root_run_id="",
            task=task,
            outline=outline,
            revision_notes=revision_notes,
            iterations_requested=iterations,
            iterations_used=result.iterations_used,
            quality_score=result.quality_score,
            stop_reason=result.stop_reason,
            trace_id=trace_id,
            prompt_version=prompt_version,
            generation_params=normalized_generation_params,
            draft=result.draft,
            review=result.review,
            review_report=review_report,
            research_sources=research_sources,
            created_at="",
            duration_ms=duration_ms,
        )
        run_id = self.run_store.create(record)
        if idempotency_key:
            bound_run_id = self.run_store.bind_idempotency_key(
                idempotency_key=idempotency_key,
                run_id=run_id,
                request_fingerprint=request_fingerprint,
            )
            if bound_run_id != run_id:
                existing = self.run_store.get(bound_run_id)
                assert existing is not None
                return self._build_generate_result(existing, idempotent_replay=True)

        saved = self.run_store.get(run_id)
        assert saved is not None
        return self._build_generate_result(saved, idempotent_replay=False)

    def _build_request_fingerprint(
        self,
        *,
        task: str,
        outline: str,
        iterations: int,
        revision_notes: str,
        prompt_version: str,
        generation_params: dict[str, object],
    ) -> str:
        payload = {
            "task": task,
            "outline": outline,
            "iterations": iterations,
            "revision_notes": revision_notes,
            "prompt_version": prompt_version,
            "generation_params": generation_params,
        }
        serialized_payload = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()

    def _build_generate_result(
        self,
        record: PipelineRunRecord,
        *,
        idempotent_replay: bool,
    ) -> GenerateResult:
        return GenerateResult(
            run_id=record.run_id,
            draft=record.draft,
            review=record.review,
            review_report=record.review_report,
            iterations_used=record.iterations_used,
            quality_score=record.quality_score,
            stop_reason=record.stop_reason,
            trace_id=record.trace_id,
            prompt_version=record.prompt_version,
            generation_params=record.generation_params,
            research_sources=record.research_sources,
            created_at=record.created_at,
            duration_ms=record.duration_ms,
            idempotent_replay=idempotent_replay,
        )

    def get_run(self, run_id: str) -> PipelineRunRecord | None:
        return self.run_store.get(run_id)

    def get_run_lineage(self, run_id: str) -> RunLineage | None:
        run = self.run_store.get(run_id)
        if run is None:
            return None
        parent = self.run_store.get(run.parent_run_id) if run.parent_run_id else None
        children = self.run_store.list_children(run_id)
        ancestors = self.run_store.list_ancestors(run_id)
        descendants = self.run_store.list_descendants(run_id)
        return RunLineage(
            run=run,
            parent=parent,
            children=children,
            ancestors=ancestors,
            descendants=descendants,
        )

    def save_edited_run(
        self,
        *,
        base_run_id: str,
        draft: str,
        review: str,
        revision_notes: str | None = None,
    ) -> GenerateResult | None:
        base_record = self.run_store.get(base_run_id)
        if base_record is None:
            return None

        record = PipelineRunRecord(
            run_id="",
            parent_run_id=base_run_id,
            root_run_id=base_record.root_run_id or base_record.run_id,
            task=base_record.task,
            outline=base_record.outline,
            revision_notes=base_record.revision_notes if revision_notes is None else revision_notes,
            iterations_requested=base_record.iterations_requested,
            iterations_used=base_record.iterations_used,
            quality_score=base_record.quality_score,
            stop_reason="manual_edit",
            trace_id=str(uuid.uuid4()),
            prompt_version=base_record.prompt_version,
            generation_params=base_record.generation_params,
            draft=draft,
            review=review,
            review_report=base_record.review_report,
            research_sources=base_record.research_sources,
            created_at="",
            duration_ms=0,
        )
        run_id = self.run_store.create(record)
        saved = self.run_store.get(run_id)
        assert saved is not None
        return self._build_generate_result(saved, idempotent_replay=False)

    def list_runs(
        self,
        limit: int = 10,
        offset: int = 0,
        stop_reason: str | None = None,
        parent_run_id: str | None = None,
        root_run_id: str | None = None,
        lineage_scope: str | None = None,
        query: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        min_quality_score: int | None = None,
        max_quality_score: int | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[PipelineRunRecord]:
        return self.run_store.list_recent(
            limit=limit,
            offset=offset,
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=query,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def count_runs(
        self,
        stop_reason: str | None = None,
        parent_run_id: str | None = None,
        root_run_id: str | None = None,
        lineage_scope: str | None = None,
        query: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        min_quality_score: int | None = None,
        max_quality_score: int | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
    ) -> int:
        return self.run_store.count_runs(
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=query,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
        )

    def get_stats(
        self,
        stop_reason: str | None = None,
        parent_run_id: str | None = None,
        root_run_id: str | None = None,
        lineage_scope: str | None = None,
        query: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        min_quality_score: int | None = None,
        max_quality_score: int | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
    ) -> RunStats:
        return self.run_store.stats(
            stop_reason=stop_reason,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            lineage_scope=lineage_scope,
            query=query,
            created_after=created_after,
            created_before=created_before,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
        )

    def purge_runs(self, retention_days: int) -> int:
        return self.run_store.purge_older_than_days(retention_days)

    def record_alert_event(
        self,
        tenant_id: str,
        policy_version: str,
        status: str,
        violations: list[str],
        should_alert: bool,
        suppressed: bool,
        suppression_reason: str | None,
        alert_fingerprint: str | None,
        routed_channels: list[str],
        rendered_message: str,
    ) -> str:
        return self.run_store.create_alert_event(
            tenant_id=tenant_id,
            policy_version=policy_version,
            status=status,
            violations=violations,
            should_alert=should_alert,
            suppressed=suppressed,
            suppression_reason=suppression_reason,
            alert_fingerprint=alert_fingerprint,
            routed_channels=routed_channels,
            rendered_message=rendered_message,
        )

    def get_alert_event(self, event_id: str) -> AlertEventRecord | None:
        return self.run_store.get_alert_event(event_id)

    def list_alert_events(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertEventRecord]:
        return self.run_store.list_alert_events(limit=limit, offset=offset, tenant_id=tenant_id)

    def summarize_alert_events(self, created_after: str, tenant_id: str | None = None) -> dict[str, object]:
        return self.run_store.summarize_alert_events(created_after=created_after, tenant_id=tenant_id)

    def archive_alert_events(self, before_ts: str, tenant_id: str | None = None) -> tuple[str, int, int]:
        return self.run_store.archive_alert_events(before_ts=before_ts, tenant_id=tenant_id)

    def list_alert_archives(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertArchiveRecord]:
        return self.run_store.list_alert_archives(limit=limit, offset=offset, tenant_id=tenant_id)

    def restore_alert_archive(self, archive_id: str) -> tuple[int, int]:
        return self.run_store.restore_alert_archive(archive_id=archive_id)

    def reconcile_alert_sla(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        return self.run_store.reconcile_alert_sla(created_after=created_after, tenant_id=tenant_id)

    def create_remediation_ticket(
        self,
        tenant_id: str,
        title: str,
        severity: str,
        details: str,
    ) -> AlertRemediationTicket:
        return self.run_store.create_remediation_ticket(
            tenant_id=tenant_id,
            title=title,
            severity=severity,
            details=details,
        )

    def list_remediation_tickets(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertRemediationTicket]:
        return self.run_store.list_remediation_tickets(limit=limit, offset=offset, tenant_id=tenant_id)

    def close_remediation_ticket(self, ticket_id: str, resolution_note: str = "") -> AlertRemediationTicket | None:
        return self.run_store.close_remediation_ticket(ticket_id=ticket_id, resolution_note=resolution_note)

    def summarize_root_causes(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        return self.run_store.summarize_root_causes(created_after=created_after, tenant_id=tenant_id)

    def summarize_ticket_status(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        return self.run_store.summarize_ticket_status(created_after=created_after, tenant_id=tenant_id)

    def create_strategy_experiment(
        self,
        *,
        tenant_id: str,
        days: int,
        baseline_max_open_degraded_alerts: int,
        candidate_max_open_degraded_alerts: int,
        baseline_quality_score: float,
        candidate_quality_score: float,
        regression_delta: float,
        min_allowed_delta: float,
        guardrail_passed: bool,
        recommend_promote_candidate: bool,
        reasons: list[str],
    ) -> AlertStrategyExperimentRecord:
        return self.run_store.create_strategy_experiment(
            tenant_id=tenant_id,
            days=days,
            baseline_max_open_degraded_alerts=baseline_max_open_degraded_alerts,
            candidate_max_open_degraded_alerts=candidate_max_open_degraded_alerts,
            baseline_quality_score=baseline_quality_score,
            candidate_quality_score=candidate_quality_score,
            regression_delta=regression_delta,
            min_allowed_delta=min_allowed_delta,
            guardrail_passed=guardrail_passed,
            recommend_promote_candidate=recommend_promote_candidate,
            reasons=reasons,
        )

    def list_strategy_experiments(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertStrategyExperimentRecord]:
        return self.run_store.list_strategy_experiments(limit=limit, offset=offset, tenant_id=tenant_id)

    def summarize_strategy_experiments(self, created_after: str, tenant_id: str | None = None) -> dict[str, float]:
        return self.run_store.summarize_strategy_experiments(created_after=created_after, tenant_id=tenant_id)

    def is_ready(self) -> bool:
        return self.run_store.ping()

    def close(self) -> None:
        self.pipeline.close()
        self.run_store.close()
