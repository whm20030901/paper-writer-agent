from __future__ import annotations

from datetime import datetime
from typing import Literal

from .filters import RunQueryFilters, validate_run_query_filters


def build_run_query_filters(
    *,
    stop_reason: str | None = None,
    parent_run_id: str | None = None,
    root_run_id: str | None = None,
    lineage_scope: Literal["root", "derived"] | None = None,
    query: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    min_quality_score: int | None = None,
    max_quality_score: int | None = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
) -> RunQueryFilters:
    filters = RunQueryFilters(
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
    validate_run_query_filters(filters)
    return filters
