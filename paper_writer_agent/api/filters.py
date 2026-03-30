from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException


@dataclass(frozen=True)
class RunQueryFilters:
    stop_reason: str | None = None
    parent_run_id: str | None = None
    root_run_id: str | None = None
    lineage_scope: str | None = None
    query: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    min_quality_score: int | None = None
    max_quality_score: int | None = None
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None

    def as_service_kwargs(self) -> dict[str, object | None]:
        return {
            "stop_reason": self.stop_reason,
            "parent_run_id": self.parent_run_id,
            "root_run_id": self.root_run_id,
            "lineage_scope": self.lineage_scope,
            "query": self.query,
            "created_after": self.created_after.isoformat() if self.created_after else None,
            "created_before": self.created_before.isoformat() if self.created_before else None,
            "min_quality_score": self.min_quality_score,
            "max_quality_score": self.max_quality_score,
            "min_duration_ms": self.min_duration_ms,
            "max_duration_ms": self.max_duration_ms,
        }



def validate_run_query_filters(filters: RunQueryFilters) -> None:
    if (
        filters.created_after
        and filters.created_before
        and filters.created_after >= filters.created_before
    ):
        raise HTTPException(status_code=422, detail="created_after must be earlier than created_before")
    if (
        filters.min_quality_score is not None
        and filters.max_quality_score is not None
        and filters.min_quality_score > filters.max_quality_score
    ):
        raise HTTPException(
            status_code=422,
            detail="min_quality_score must be less than or equal to max_quality_score",
        )
    if (
        filters.min_duration_ms is not None
        and filters.max_duration_ms is not None
        and filters.min_duration_ms > filters.max_duration_ms
    ):
        raise HTTPException(
            status_code=422,
            detail="min_duration_ms must be less than or equal to max_duration_ms",
        )
