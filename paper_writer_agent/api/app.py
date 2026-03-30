from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..core.config import Settings
from ..core.logging import setup_logging
from ..main import bootstrap_pipeline
from ..services.paper_service import PaperService
from ..services.run_store import RunStore
from .frontend import frontend_static_dir
from .middleware import request_id_middleware
from .rate_limit import InMemoryRateLimiter
from .routes import register_routes

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    setup_logging("INFO")

    pipeline = bootstrap_pipeline(cfg)
    run_store = RunStore(cfg.run_db_path)
    paper_service = PaperService(pipeline=pipeline, run_store=run_store)
    limiter = InMemoryRateLimiter(max_requests_per_minute=cfg.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if cfg.auto_purge_on_startup:
            deleted = paper_service.purge_runs(cfg.run_retention_days)
            logger.info(
                "startup purge executed",
                extra={"deleted_runs": deleted, "retention_days": cfg.run_retention_days},
            )
        if cfg.slo_alert_auto_archive_on_startup:
            before_ts = (datetime.now(timezone.utc) - timedelta(days=cfg.slo_alert_auto_archive_days)).isoformat()
            archive_id, archived_count, compressed_bytes = paper_service.archive_alert_events(before_ts=before_ts)
            logger.info(
                "startup alert archive executed",
                extra={
                    "archive_id": archive_id,
                    "archived_events": archived_count,
                    "compressed_bytes": compressed_bytes,
                    "archive_days": cfg.slo_alert_auto_archive_days,
                },
            )
        yield
        paper_service.close()

    app = FastAPI(title=cfg.app_name, version="0.9.0", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    app.mount("/static", StaticFiles(directory=frontend_static_dir()), name="static")
    register_routes(app=app, cfg=cfg, paper_service=paper_service, limiter=limiter)
    return app


app = create_app()
