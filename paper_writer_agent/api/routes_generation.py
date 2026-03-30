from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request

from ..core.config import Settings
from ..services.paper_service import PaperService
from ..services.run_store import IdempotencyConflictError
from .rate_limit import InMemoryRateLimiter
from .response_builders import build_generate_response
from .schemas import GeneratePaperRequest, GeneratePaperResponse
from .security import extract_api_key_header, verify_api_key

logger = logging.getLogger(__name__)


def register_generation_routes(
    app: FastAPI,
    cfg: Settings,
    paper_service: PaperService,
    limiter: InMemoryRateLimiter,
) -> None:
    @app.post("/v1/papers/generate", response_model=GeneratePaperResponse)
    def generate_paper(
        req: GeneratePaperRequest,
        request: Request,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> GeneratePaperResponse:
        verify_api_key(cfg.api_key, x_api_key)
        client_host = request.client.host if request.client else "unknown"
        rate_key = x_api_key or client_host
        limiter.check(rate_key)

        logger.info(
            "paper generation request",
            extra={"iterations": req.iterations, "request_id": request.state.request_id},
        )
        note_parts = [req.revision_notes.strip()] if req.revision_notes.strip() else []
        if req.paper_type:
            note_parts.append(f"Paper Type: {req.paper_type}")
        if req.tone:
            note_parts.append(f"Tone: {req.tone}")
        if req.citation_style:
            note_parts.append(f"Citation Style: {req.citation_style}")
        if req.target_venue:
            note_parts.append(f"Target Venue: {req.target_venue.strip()}")
        merged_revision_notes = "\n".join(part for part in note_parts if part).strip()
        idempotency_key = request.headers.get("X-Idempotency-Key")
        generation_params: dict[str, object] = {
            "paper_type": req.paper_type or "",
            "tone": req.tone or "",
            "citation_style": req.citation_style or "",
            "target_venue": (req.target_venue or "").strip(),
            "iterations": req.iterations,
        }
        try:
            result = paper_service.generate(
                task=req.task,
                outline=req.outline,
                iterations=req.iterations,
                revision_notes=merged_revision_notes,
                idempotency_key=idempotency_key,
                prompt_version=cfg.prompt_version,
                generation_params=generation_params,
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return build_generate_response(result)
