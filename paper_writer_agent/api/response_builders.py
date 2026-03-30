from __future__ import annotations

from .schemas import GeneratePaperResponse


def build_generate_response(result) -> GeneratePaperResponse:
    return GeneratePaperResponse(
        run_id=result.run_id,
        trace_id=result.trace_id,
        created_at=result.created_at,
        duration_ms=result.duration_ms,
        draft=result.draft,
        review=result.review,
        review_report=result.review_report,
        iterations_used=result.iterations_used,
        quality_score=result.quality_score,
        stop_reason=result.stop_reason,
        prompt_version=result.prompt_version,
        generation_params=result.generation_params,
        research_sources=result.research_sources,
        idempotent_replay=result.idempotent_replay,
    )
