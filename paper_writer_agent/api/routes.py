from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from ..core.config import Settings
from ..services.paper_service import PaperService
from .frontend import load_index_html
from .rate_limit import InMemoryRateLimiter
from .routes_export import register_export_routes
from .routes_generation import register_generation_routes
from .routes_insights import register_insights_routes
from .routes_revision import register_revision_routes
from .routes_runs import register_runs_routes
from .schemas import HealthResponse, PurgeResponse
from .security import extract_api_key_header, verify_api_key


def register_routes(
    app: FastAPI,
    cfg: Settings,
    paper_service: PaperService,
    limiter: InMemoryRateLimiter,
) -> None:
    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(content=load_index_html())

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", app=cfg.app_name, env=cfg.app_env)

    @app.get("/ready", response_model=HealthResponse)
    def ready() -> HealthResponse:
        if not paper_service.is_ready():
            raise HTTPException(status_code=503, detail="service not ready")
        return HealthResponse(status="ready", app=cfg.app_name, env=cfg.app_env)

    register_generation_routes(app=app, cfg=cfg, paper_service=paper_service, limiter=limiter)
    register_export_routes(app=app, cfg=cfg, paper_service=paper_service)
    register_runs_routes(app=app, cfg=cfg, paper_service=paper_service)
    register_insights_routes(app=app, cfg=cfg, paper_service=paper_service)
    register_revision_routes(app=app, cfg=cfg, paper_service=paper_service)

    @app.post("/v1/papers/maintenance/purge", response_model=PurgeResponse)
    def purge_runs(
        retention_days: int | None = Query(default=None, ge=0, le=3650),
        x_api_key: str | None = Depends(extract_api_key_header),
    ) -> PurgeResponse:
        verify_api_key(cfg.api_key, x_api_key)
        days = cfg.run_retention_days if retention_days is None else retention_days
        deleted = paper_service.purge_runs(days)
        return PurgeResponse(deleted_runs=deleted, retention_days=days)
