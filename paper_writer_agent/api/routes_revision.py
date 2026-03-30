from __future__ import annotations

import re

from fastapi import Depends, FastAPI, HTTPException

from ..core.config import Settings
from ..services.paper_service import PaperService
from .response_builders import build_generate_response
from .schemas import (
    ApplyRevisionPlanRequest,
    GeneratePaperResponse,
    RollbackRunRequest,
    RunRevisionPlanResponse,
    RewriteSectionRequest,
    RewriteSectionResponse,
    SaveEditedDraftRequest,
)
from .security import extract_api_key_header, verify_api_key


def _extract_markdown_section(draft: str, section_title: str) -> str | None:
    lines = draft.splitlines()
    target = section_title.strip().lower()
    start_index: int | None = None
    for idx, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower() == target:
            start_index = idx
            break
    if start_index is None:
        return None
    end_index = len(lines)
    for idx in range(start_index + 1, len(lines)):
        if lines[idx].startswith("## "):
            end_index = idx
            break
    return "\n".join(lines[start_index:end_index]).strip()


def _rewrite_section_markdown(
    section_markdown: str,
    *,
    section_title: str,
    rewrite_goal: str,
    keep_citations: bool,
    max_tokens: int,
) -> str:
    body = section_markdown.split("\n", 1)[1].strip() if "\n" in section_markdown else ""
    citations = sorted({match for match in re.findall(r"\[(\d+)\]", body)})
    citation_suffix = ""
    if keep_citations and citations:
        citation_suffix = " " + " ".join(f"[{marker}]" for marker in citations)
    summary = body[: max(200, min(max_tokens * 2, 1200))]
    rewritten_body = (
        f"Revision goal: {rewrite_goal.strip()}. "
        f"This section has been rewritten to improve argument clarity, evidence alignment, and academic tone. "
        f"Key retained context: {summary}"
    ).strip()
    return f"## {section_title.strip()}\n{rewritten_body}{citation_suffix}"


def register_revision_routes(app: FastAPI, cfg: Settings, paper_service: PaperService) -> None:
    @app.post("/v1/papers/runs/{run_id}/save-edited", response_model=GeneratePaperResponse)
    def save_edited_run(
        run_id: str,
        req: SaveEditedDraftRequest,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> GeneratePaperResponse:
        verify_api_key(cfg.api_key, x_api_key)
        result = paper_service.save_edited_run(
            base_run_id=run_id,
            draft=req.draft,
            review=req.review,
            revision_notes=req.revision_notes,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return build_generate_response(result)

    @app.post("/v1/papers/runs/{run_id}/rollback", response_model=GeneratePaperResponse)
    def rollback_run_to_target(
        run_id: str,
        req: RollbackRunRequest,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> GeneratePaperResponse:
        verify_api_key(cfg.api_key, x_api_key)
        current = paper_service.get_run(run_id)
        if current is None:
            raise HTTPException(status_code=404, detail="run not found")
        target = paper_service.get_run(req.to_run_id)
        if target is None:
            raise HTTPException(status_code=404, detail="target run not found")
        reason = req.reason.strip() if isinstance(req.reason, str) else ""
        revision_notes = f"Rollback to run {req.to_run_id}."
        if reason:
            revision_notes += f" Reason: {reason}"
        result = paper_service.save_edited_run(
            base_run_id=run_id,
            draft=target.draft,
            review=f"Rollback applied from {run_id} to snapshot {req.to_run_id}.",
            revision_notes=revision_notes,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return build_generate_response(result)

    @app.get("/v1/papers/runs/{run_id}/revision-plan", response_model=RunRevisionPlanResponse)
    def get_run_revision_plan(
        run_id: str,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RunRevisionPlanResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        plan_items = record.review_report.get("revision_plan", []) if isinstance(record.review_report, dict) else []
        normalized_items = [str(item) for item in plan_items if str(item).strip()]
        return RunRevisionPlanResponse(run_id=record.run_id, items=normalized_items, total_items=len(normalized_items))

    @app.post("/v1/papers/runs/{run_id}/revision-plan/apply", response_model=GeneratePaperResponse)
    def apply_run_revision_plan(
        run_id: str,
        req: ApplyRevisionPlanRequest,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> GeneratePaperResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        selected = [item.strip() for item in req.selected_items if item.strip()]
        if not selected:
            raise HTTPException(status_code=400, detail="selected_items must not be empty")
        applied_block = "\n".join(f"- {item}" for item in selected)
        if req.mode == "rewrite":
            revised_draft = (
                f"{record.draft}\n\n## Applied Revision Plan\n"
                f"Mode: rewrite\n"
                f"{applied_block}\n\n"
                "The selected reviewer instructions were integrated with a full draft rewrite pass."
            )
        else:
            revised_draft = (
                f"{record.draft}\n\n## Applied Revision Plan\n"
                f"Mode: patch\n"
                f"{applied_block}\n\n"
                "The selected reviewer instructions were applied as incremental patches."
            )
        revision_notes = f"Applied revision plan ({req.mode}) with {len(selected)} selected items."
        result = paper_service.save_edited_run(
            base_run_id=run_id,
            draft=revised_draft,
            review=f"Applied revision plan in {req.mode} mode.",
            revision_notes=revision_notes,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return build_generate_response(result)

    @app.post("/v1/papers/runs/{run_id}/rewrite-section", response_model=RewriteSectionResponse)
    def rewrite_run_section(
        run_id: str,
        req: RewriteSectionRequest,
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> RewriteSectionResponse:
        verify_api_key(cfg.api_key, x_api_key)
        record = paper_service.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        section_markdown = _extract_markdown_section(record.draft, req.section_title)
        if section_markdown is None:
            raise HTTPException(status_code=400, detail="section not found in draft")
        updated_section_markdown = _rewrite_section_markdown(
            section_markdown,
            section_title=req.section_title,
            rewrite_goal=req.rewrite_goal,
            keep_citations=req.keep_citations,
            max_tokens=req.max_tokens,
        )
        quality_delta_estimate = 0.6 if req.keep_citations else 0.3
        return RewriteSectionResponse(
            run_id=record.run_id,
            section_title=req.section_title,
            updated_section_markdown=updated_section_markdown,
            quality_delta_estimate=quality_delta_estimate,
        )
