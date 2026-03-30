from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Query

from ..core.config import Settings
from ..services.paper_service import PaperService
from .run_query import build_run_query_filters
from .schemas import (
    InsightTrendPoint,
    RunInsightsListResponse,
    RunInsightsMetricsResponse,
    RunInsightsResponse,
    RunInsightsTrendsResponse,
    TaskInsightRow,
    TopTaskInsightsResponse,
)
from .security import extract_api_key_header, verify_api_key


def _to_run_insights_response(record) -> RunInsightsResponse:
    body_text, _, _ = record.draft.partition("\n[References]\n")
    inline_citations = {match for match in re.findall(r"\[(\d+)\]", body_text)}
    reference_markers = {match for match in re.findall(r"^\[(\d+)\]\s+", record.draft, re.MULTILINE)}
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


def register_insights_routes(app: FastAPI, cfg: Settings, paper_service: PaperService) -> None:
    def iter_filtered_runs(
        filter_kwargs: dict[str, object],
        *,
        batch_size: int = 500,
    ):
        offset = 0
        while True:
            runs = paper_service.list_runs(
                limit=batch_size,
                offset=offset,
                **filter_kwargs,
                sort_by="created_at",
                sort_order="desc",
            )
            if not runs:
                break
            yield from runs
            offset += len(runs)
            if len(runs) < batch_size:
                break

    @app.get("/v1/papers/insights", response_model=RunInsightsListResponse)
    def list_run_insights(
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
    ) -> RunInsightsListResponse:
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
        items = [_to_run_insights_response(run) for run in runs]
        total = paper_service.count_runs(**filter_kwargs)
        has_more = (offset + len(items)) < total
        next_offset = (offset + len(items)) if has_more else None
        return RunInsightsListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=next_offset,
        )

    @app.get("/v1/papers/insights/metrics", response_model=RunInsightsMetricsResponse)
    def run_insights_metrics(
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
    ) -> RunInsightsMetricsResponse:
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
        total = paper_service.count_runs(**filter_kwargs)
        runs_with_review_report = 0
        sum_source_count = 0
        sum_inline_citation_count = 0
        sum_revision_plan_items = 0
        sum_citation_coverage_score = 0.0

        for run in iter_filtered_runs(filter_kwargs):
            insight = _to_run_insights_response(run)
            sum_source_count += insight.source_count
            sum_inline_citation_count += insight.inline_citation_count
            sum_revision_plan_items += insight.revision_plan_items
            sum_citation_coverage_score += insight.citation_coverage_score
            if run.review_report:
                runs_with_review_report += 1

        denominator = max(total, 1)

        return RunInsightsMetricsResponse(
            total_runs=total,
            runs_with_review_report=runs_with_review_report,
            avg_source_count=(sum_source_count / denominator) if total else 0.0,
            avg_inline_citation_count=(sum_inline_citation_count / denominator) if total else 0.0,
            avg_revision_plan_items=(sum_revision_plan_items / denominator) if total else 0.0,
            avg_citation_coverage_score=(sum_citation_coverage_score / denominator) if total else 0.0,
        )

    @app.get("/v1/papers/insights/trends", response_model=RunInsightsTrendsResponse)
    def run_insights_trends(
        interval: Literal["day", "week"] = Query(default="day"),
        group_by: Literal["all", "task", "paper_type"] = Query(default="all"),
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
    ) -> RunInsightsTrendsResponse:
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
        grouped: dict[tuple[str, str | None], dict[str, float]] = {}
        for run in iter_filtered_runs(filters.as_service_kwargs()):
            created_at = datetime.fromisoformat(run.created_at)
            if interval == "week":
                bucket_dt = created_at.date().toordinal() - created_at.weekday()
                bucket = datetime.fromordinal(bucket_dt).date().isoformat()
            else:
                bucket = created_at.date().isoformat()
            if group_by == "task":
                group_key = (run.task or "").strip() or "(untitled task)"
            elif group_by == "paper_type":
                matched = re.search(r"Paper Type:\s*([A-Za-z_-]+)", run.revision_notes or "", re.IGNORECASE)
                group_key = (matched.group(1).lower() if matched else "unknown")
            else:
                group_key = None
            insight = _to_run_insights_response(run)
            entry = grouped.setdefault((bucket, group_key), {"count": 0.0, "quality_sum": 0.0, "inline_sum": 0.0})
            entry["count"] += 1
            entry["quality_sum"] += float(run.quality_score)
            entry["inline_sum"] += float(insight.inline_citation_count)
        points = [
            InsightTrendPoint(
                group_key=group_key,
                bucket_start=bucket,
                total_runs=int(stats["count"]),
                avg_quality_score=(stats["quality_sum"] / stats["count"]) if stats["count"] else 0.0,
                avg_inline_citation_count=(stats["inline_sum"] / stats["count"]) if stats["count"] else 0.0,
            )
            for (bucket, group_key), stats in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] or ""))
        ]
        return RunInsightsTrendsResponse(interval=interval, group_by=group_by, points=points)

    @app.get("/v1/papers/insights/top-tasks", response_model=TopTaskInsightsResponse)
    def top_task_insights(
        limit: int = Query(default=10, ge=1, le=50),
        q: str | None = Query(default=None, min_length=1, max_length=200),
        stop_reason: str | None = Query(default=None),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> TopTaskInsightsResponse:
        verify_api_key(cfg.api_key, x_api_key)
        filters = build_run_query_filters(stop_reason=stop_reason, query=q)
        filter_kwargs = filters.as_service_kwargs()
        grouped: dict[str, dict[str, float]] = {}

        for run in iter_filtered_runs(filter_kwargs):
            task_key = (run.task or "").strip() or "(untitled task)"
            entry = grouped.setdefault(task_key, {"count": 0.0, "quality_sum": 0.0, "source_sum": 0.0})
            entry["count"] += 1
            entry["quality_sum"] += float(run.quality_score)
            entry["source_sum"] += float(len(run.research_sources))

        ranked_items = sorted(
            grouped.items(),
            key=lambda item: (item[1]["count"], item[1]["quality_sum"] / max(item[1]["count"], 1.0)),
            reverse=True,
        )[:limit]
        rows = [
            TaskInsightRow(
                task=task,
                run_count=int(stats["count"]),
                avg_quality_score=(stats["quality_sum"] / stats["count"]) if stats["count"] else 0.0,
                avg_source_count=(stats["source_sum"] / stats["count"]) if stats["count"] else 0.0,
            )
            for task, stats in ranked_items
        ]
        return TopTaskInsightsResponse(items=rows, total_tasks=len(grouped), limit=limit)
