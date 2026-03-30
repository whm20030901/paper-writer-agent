from __future__ import annotations

import json
import sqlite3
import threading
import uuid
import gzip
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class PipelineRunRecord:
    run_id: str
    parent_run_id: str
    root_run_id: str
    task: str
    outline: str
    revision_notes: str
    iterations_requested: int
    iterations_used: int
    quality_score: int
    stop_reason: str
    draft: str
    review: str
    review_report: dict[str, object]
    research_sources: list[dict[str, object]]
    created_at: str
    duration_ms: int
    trace_id: str = ""
    prompt_version: str = "v1"
    generation_params: dict[str, object] = field(default_factory=dict)


@dataclass
class RunStats:
    total_runs: int
    avg_quality_score: float
    avg_duration_ms: float
    success_rate: float
    stop_reason_counts: dict[str, int]


@dataclass
class IdempotencyBinding:
    run_id: str
    request_fingerprint: str


@dataclass
class AlertEventRecord:
    event_id: str
    created_at: str
    tenant_id: str
    policy_version: str
    status: str
    violations: list[str]
    should_alert: bool
    suppressed: bool
    suppression_reason: str
    alert_fingerprint: str
    routed_channels: list[str]
    rendered_message: str


@dataclass
class AlertArchiveRecord:
    archive_id: str
    created_at: str
    tenant_id: str
    before_ts: str
    event_count: int
    compressed_bytes: int


@dataclass
class AlertRemediationTicket:
    ticket_id: str
    created_at: str
    tenant_id: str
    title: str
    severity: str
    status: str
    details: str


@dataclass
class AlertStrategyExperimentRecord:
    experiment_id: str
    created_at: str
    tenant_id: str
    days: int
    baseline_max_open_degraded_alerts: int
    candidate_max_open_degraded_alerts: int
    baseline_quality_score: float
    candidate_quality_score: float
    regression_delta: float
    min_allowed_delta: float
    guardrail_passed: bool
    recommend_promote_candidate: bool
    reasons: list[str]


class IdempotencyConflictError(ValueError):
    pass


class RunStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    parent_run_id TEXT NOT NULL DEFAULT '',
                    root_run_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    task TEXT NOT NULL DEFAULT '',
                    revision_notes TEXT NOT NULL DEFAULT '',
                    stop_reason TEXT NOT NULL DEFAULT '',
                    quality_score INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    trace_id TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT 'v1',
                    generation_params TEXT NOT NULL DEFAULT '{}',
                    payload TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    policy_version TEXT NOT NULL DEFAULT 'v1',
                    status TEXT NOT NULL DEFAULT 'no_data',
                    violations TEXT NOT NULL DEFAULT '[]',
                    should_alert INTEGER NOT NULL DEFAULT 0,
                    suppressed INTEGER NOT NULL DEFAULT 0,
                    suppression_reason TEXT NOT NULL DEFAULT '',
                    alert_fingerprint TEXT NOT NULL DEFAULT '',
                    routed_channels TEXT NOT NULL DEFAULT '[]',
                    rendered_message TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_event_archives (
                    archive_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    before_ts TEXT NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    compressed_payload BLOB NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_remediation_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    details TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_strategy_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    days INTEGER NOT NULL DEFAULT 7,
                    baseline_max_open_degraded_alerts INTEGER NOT NULL DEFAULT 0,
                    candidate_max_open_degraded_alerts INTEGER NOT NULL DEFAULT 0,
                    baseline_quality_score REAL NOT NULL DEFAULT 0.0,
                    candidate_quality_score REAL NOT NULL DEFAULT 0.0,
                    regression_delta REAL NOT NULL DEFAULT 0.0,
                    min_allowed_delta REAL NOT NULL DEFAULT -3.0,
                    guardrail_passed INTEGER NOT NULL DEFAULT 0,
                    recommend_promote_candidate INTEGER NOT NULL DEFAULT 0,
                    reasons TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            idempotency_columns = {
                row[1] for row in self.conn.execute("PRAGMA table_info(idempotency_keys)").fetchall()
            }
            if "request_fingerprint" not in idempotency_columns:
                self.conn.execute(
                    "ALTER TABLE idempotency_keys ADD COLUMN request_fingerprint TEXT NOT NULL DEFAULT ''"
                )

            columns = {
                row[1] for row in self.conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()
            }
            if "task" not in columns:
                self.conn.execute("ALTER TABLE pipeline_runs ADD COLUMN task TEXT NOT NULL DEFAULT ''")
            if "parent_run_id" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN parent_run_id TEXT NOT NULL DEFAULT ''"
                )
            if "root_run_id" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN root_run_id TEXT NOT NULL DEFAULT ''"
                )
            if "revision_notes" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN revision_notes TEXT NOT NULL DEFAULT ''"
                )
            if "stop_reason" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN stop_reason TEXT NOT NULL DEFAULT ''"
                )
            if "quality_score" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN quality_score INTEGER NOT NULL DEFAULT 0"
                )
            if "duration_ms" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0"
                )
            if "trace_id" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''"
                )
            if "prompt_version" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN prompt_version TEXT NOT NULL DEFAULT 'v1'"
                )
            if "generation_params" not in columns:
                self.conn.execute(
                    "ALTER TABLE pipeline_runs ADD COLUMN generation_params TEXT NOT NULL DEFAULT '{}'"
                )

            self.conn.execute(
                """
                UPDATE pipeline_runs
                SET
                    parent_run_id = COALESCE(json_extract(payload, '$.parent_run_id'), parent_run_id, ''),
                    root_run_id = COALESCE(json_extract(payload, '$.root_run_id'), root_run_id, ''),
                    task = COALESCE(json_extract(payload, '$.task'), task, ''),
                    revision_notes = COALESCE(json_extract(payload, '$.revision_notes'), revision_notes, ''),
                    stop_reason = COALESCE(json_extract(payload, '$.stop_reason'), stop_reason, ''),
                    quality_score = CAST(COALESCE(json_extract(payload, '$.quality_score'), quality_score, 0) AS INTEGER),
                    duration_ms = CAST(COALESCE(json_extract(payload, '$.duration_ms'), duration_ms, 0) AS INTEGER),
                    trace_id = COALESCE(json_extract(payload, '$.trace_id'), trace_id, ''),
                    prompt_version = COALESCE(json_extract(payload, '$.prompt_version'), prompt_version, 'v1'),
                    generation_params = COALESCE(json_extract(payload, '$.generation_params'), generation_params, '{}')
                """
            )

            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_stop_reason ON pipeline_runs(stop_reason)"
            )
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_task ON pipeline_runs(task)")
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_quality_score ON pipeline_runs(quality_score)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_duration_ms ON pipeline_runs(duration_ms)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_parent_run_id ON pipeline_runs(parent_run_id)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_root_run_id ON pipeline_runs(root_run_id)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_strategy_experiments_created_at ON alert_strategy_experiments(created_at DESC)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_strategy_experiments_tenant_id ON alert_strategy_experiments(tenant_id)"
            )
            self._backfill_root_run_ids()
            self.conn.commit()

    def _backfill_root_run_ids(self) -> None:
        rows = self.conn.execute(
            "SELECT run_id, parent_run_id, root_run_id FROM pipeline_runs"
        ).fetchall()
        parent_map = {str(run_id): str(parent_run_id or "") for run_id, parent_run_id, _ in rows}
        root_map = {str(run_id): str(root_run_id or "") for run_id, _, root_run_id in rows}

        def resolve_root(run_id: str) -> str:
            cached = root_map.get(run_id, "")
            if cached:
                return cached

            seen: set[str] = set()
            current = run_id
            while current and current not in seen:
                seen.add(current)
                cached_current = root_map.get(current, "")
                if cached_current:
                    root = cached_current
                    break
                parent = parent_map.get(current, "")
                if not parent or parent not in parent_map:
                    root = current
                    break
                current = parent
            else:
                root = run_id

            for seen_run_id in seen:
                root_map[seen_run_id] = root
            return root

        updates: list[tuple[str, str, str]] = []
        for run_id, _, _ in rows:
            normalized_run_id = str(run_id)
            root = resolve_root(normalized_run_id)
            if root_map.get(normalized_run_id, "") != root:
                root_map[normalized_run_id] = root
            updates.append((root, root, normalized_run_id))

        self.conn.executemany(
            """
            UPDATE pipeline_runs
            SET root_run_id = ?,
                payload = json_set(payload, '$.root_run_id', ?)
            WHERE run_id = ?
            """,
            updates,
        )

    def _normalize_payload(self, payload: str) -> PipelineRunRecord:
        data = json.loads(payload)
        if "parent_run_id" not in data:
            data["parent_run_id"] = ""
        if "root_run_id" not in data:
            data["root_run_id"] = data.get("run_id", "")
        if "revision_notes" not in data:
            data["revision_notes"] = ""
        if "review_report" not in data:
            data["review_report"] = {}
        if "research_sources" not in data:
            data["research_sources"] = []
        if "duration_ms" not in data:
            data["duration_ms"] = 0
        if "prompt_version" not in data:
            data["prompt_version"] = "v1"
        if "trace_id" not in data:
            data["trace_id"] = ""
        if "generation_params" not in data or not isinstance(data["generation_params"], dict):
            data["generation_params"] = {}
        return PipelineRunRecord(**data)

    def create(self, record: PipelineRunRecord) -> str:
        if not record.run_id:
            record.run_id = str(uuid.uuid4())
        if not record.created_at:
            record.created_at = datetime.now(timezone.utc).isoformat()
        if not record.root_run_id:
            record.root_run_id = record.run_id

        review_report = getattr(record, "review_report", {})
        research_sources = getattr(record, "research_sources", [])
        prompt_version = getattr(record, "prompt_version", "v1")
        generation_params = getattr(record, "generation_params", {})
        trace_id = getattr(record, "trace_id", "")
        if not isinstance(generation_params, dict):
            generation_params = {}
        payload_dict = dict(record.__dict__)
        payload_dict.setdefault("review_report", review_report)
        payload_dict.setdefault("research_sources", research_sources)
        payload_dict.setdefault("prompt_version", prompt_version)
        payload_dict.setdefault("trace_id", trace_id)
        payload_dict.setdefault("generation_params", generation_params)
        payload = json.dumps(payload_dict, ensure_ascii=False)
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO pipeline_runs(
                    run_id,
                    parent_run_id,
                    root_run_id,
                    created_at,
                    task,
                    revision_notes,
                    stop_reason,
                    quality_score,
                    duration_ms,
                    trace_id,
                    prompt_version,
                    generation_params,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.parent_run_id,
                    record.root_run_id,
                    record.created_at,
                    record.task,
                    record.revision_notes,
                    record.stop_reason,
                    record.quality_score,
                    record.duration_ms,
                    trace_id,
                    prompt_version,
                    json.dumps(generation_params, ensure_ascii=False),
                    payload,
                ),
            )
            self.conn.commit()
        return record.run_id

    def get(self, run_id: str) -> PipelineRunRecord | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT payload FROM pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return self._normalize_payload(row[0])

    def list_children(self, run_id: str) -> list[PipelineRunRecord]:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT payload FROM pipeline_runs
                WHERE parent_run_id = ?
                ORDER BY created_at DESC
                """,
                (run_id,),
            ).fetchall()
        return [self._normalize_payload(row[0]) for row in rows]

    def list_descendants(self, run_id: str) -> list[PipelineRunRecord]:
        descendants: list[PipelineRunRecord] = []
        queue = [run_id]
        seen = {run_id}

        while queue:
            current_run_id = queue.pop(0)
            children = self.list_children(current_run_id)
            for child in children:
                if child.run_id in seen:
                    continue
                seen.add(child.run_id)
                descendants.append(child)
                queue.append(child.run_id)

        return descendants

    def list_ancestors(self, run_id: str) -> list[PipelineRunRecord]:
        ancestors: list[PipelineRunRecord] = []
        seen = {run_id}
        current = self.get(run_id)

        while current is not None and current.parent_run_id:
            parent = self.get(current.parent_run_id)
            if parent is None or parent.run_id in seen:
                break
            seen.add(parent.run_id)
            ancestors.append(parent)
            current = parent

        return ancestors

    def bind_idempotency_key(self, idempotency_key: str, run_id: str, request_fingerprint: str) -> str:
        with self.lock:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO idempotency_keys(idempotency_key, run_id, request_fingerprint)
                VALUES (?, ?, ?)
                """,
                (idempotency_key, run_id, request_fingerprint),
            )
            row = self.conn.execute(
                """
                SELECT run_id, request_fingerprint
                FROM idempotency_keys
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            assert row is not None
            bound_run_id = str(row[0])
            bound_request_fingerprint = str(row[1] or "")
            if (
                bound_run_id != run_id
                and bound_request_fingerprint
                and bound_request_fingerprint != request_fingerprint
            ):
                self.conn.execute("DELETE FROM pipeline_runs WHERE run_id = ?", (run_id,))
                self.conn.commit()
                raise IdempotencyConflictError("idempotency key already used for a different request")
            if bound_run_id != run_id:
                self.conn.execute("DELETE FROM pipeline_runs WHERE run_id = ?", (run_id,))
            elif bound_request_fingerprint != request_fingerprint:
                self.conn.execute(
                    """
                    UPDATE idempotency_keys
                    SET request_fingerprint = ?
                    WHERE idempotency_key = ?
                    """,
                    (request_fingerprint, idempotency_key),
                )
            self.conn.commit()
        return bound_run_id

    def get_idempotency_binding(self, idempotency_key: str) -> IdempotencyBinding | None:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT run_id, request_fingerprint
                FROM idempotency_keys
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        if not row:
            return None
        return IdempotencyBinding(run_id=str(row[0]), request_fingerprint=str(row[1] or ""))

    def get_by_idempotency_key(self, idempotency_key: str) -> PipelineRunRecord | None:
        binding = self.get_idempotency_binding(idempotency_key)
        if binding is None:
            return None
        return self.get(binding.run_id)

    def _build_filter_clause(
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
    ) -> tuple[str, list[object]]:
        conditions: list[str] = []
        params: list[object] = []

        if stop_reason:
            conditions.append("stop_reason = ?")
            params.append(stop_reason)
        if parent_run_id is not None:
            conditions.append("parent_run_id = ?")
            params.append(parent_run_id)
        if root_run_id is not None:
            conditions.append("root_run_id = ?")
            params.append(root_run_id)
        if lineage_scope == "root":
            conditions.append("parent_run_id = ''")
        elif lineage_scope == "derived":
            conditions.append("parent_run_id != ''")
        if query:
            conditions.append("LOWER(task) LIKE ?")
            params.append(f"%{query.lower()}%")
        if created_after:
            conditions.append("created_at > ?")
            params.append(created_after)
        if created_before:
            conditions.append("created_at < ?")
            params.append(created_before)
        if min_quality_score is not None:
            conditions.append("quality_score >= ?")
            params.append(min_quality_score)
        if max_quality_score is not None:
            conditions.append("quality_score <= ?")
            params.append(max_quality_score)
        if min_duration_ms is not None:
            conditions.append("duration_ms >= ?")
            params.append(min_duration_ms)
        if max_duration_ms is not None:
            conditions.append("duration_ms <= ?")
            params.append(max_duration_ms)

        if not conditions:
            return "", params
        return f" WHERE {' AND '.join(conditions)}", params

    def list_recent(
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
        where_clause, params = self._build_filter_clause(
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
        order_column = "created_at"
        if sort_by == "quality_score":
            order_column = "quality_score"
        elif sort_by == "duration_ms":
            order_column = "duration_ms"
        order_direction = "ASC" if sort_order == "asc" else "DESC"

        sql = (
            "SELECT payload FROM pipeline_runs"
            f"{where_clause} "
            f"ORDER BY {order_column} {order_direction}, created_at {order_direction} LIMIT ? OFFSET ?"
        )

        with self.lock:
            rows = self.conn.execute(sql, (*params, limit, offset)).fetchall()

        return [self._normalize_payload(r[0]) for r in rows]

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
        where_clause, params = self._build_filter_clause(
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
        sql = f"SELECT COUNT(1) FROM pipeline_runs{where_clause}"

        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    def stats(
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
        where_clause, params = self._build_filter_clause(
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

        agg_sql = (
            "SELECT COUNT(1), "
            "AVG(quality_score), "
            "AVG(duration_ms), "
            "AVG(CASE WHEN stop_reason = 'failed' THEN 0.0 ELSE 1.0 END) "
            f"FROM pipeline_runs{where_clause}"
        )
        reason_sql = (
            "SELECT stop_reason, COUNT(1) "
            f"FROM pipeline_runs{where_clause} GROUP BY stop_reason"
        )

        with self.lock:
            row = self.conn.execute(agg_sql, params).fetchone()
            reason_rows = self.conn.execute(reason_sql, params).fetchall()

        total = int(row[0]) if row and row[0] is not None else 0
        if total == 0:
            return RunStats(
                total_runs=0,
                avg_quality_score=0.0,
                avg_duration_ms=0.0,
                success_rate=0.0,
                stop_reason_counts={},
            )

        avg_quality = float(row[1]) if row and row[1] is not None else 0.0
        avg_duration = float(row[2]) if row and row[2] is not None else 0.0
        success_rate = float(row[3]) if row and row[3] is not None else 0.0
        stop_reason_counts = {reason: int(count) for reason, count in reason_rows}

        return RunStats(
            total_runs=total,
            avg_quality_score=round(avg_quality, 2),
            avg_duration_ms=round(avg_duration, 2),
            success_rate=round(success_rate, 4),
            stop_reason_counts=stop_reason_counts,
        )

    def ping(self) -> bool:
        with self.lock:
            try:
                self.conn.execute("SELECT 1").fetchone()
                return True
            except sqlite3.Error:
                return False

    def create_alert_event(
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
        event_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO alert_events (
                    event_id, created_at, tenant_id, policy_version, status,
                    violations, should_alert, suppressed, suppression_reason,
                    alert_fingerprint, routed_channels, rendered_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    created_at,
                    tenant_id,
                    policy_version,
                    status,
                    json.dumps(violations, ensure_ascii=False),
                    1 if should_alert else 0,
                    1 if suppressed else 0,
                    suppression_reason or "",
                    alert_fingerprint or "",
                    json.dumps(routed_channels, ensure_ascii=False),
                    rendered_message,
                ),
            )
            self.conn.commit()
        return event_id

    def get_alert_event(self, event_id: str) -> AlertEventRecord | None:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT event_id, created_at, tenant_id, policy_version, status,
                       violations, should_alert, suppressed, suppression_reason,
                       alert_fingerprint, routed_channels, rendered_message
                FROM alert_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return AlertEventRecord(
            event_id=row[0],
            created_at=row[1],
            tenant_id=row[2],
            policy_version=row[3],
            status=row[4],
            violations=json.loads(row[5] or "[]"),
            should_alert=bool(row[6]),
            suppressed=bool(row[7]),
            suppression_reason=row[8] or "",
            alert_fingerprint=row[9] or "",
            routed_channels=json.loads(row[10] or "[]"),
            rendered_message=row[11] or "",
        )

    def list_alert_events(self, limit: int = 20, offset: int = 0, tenant_id: str | None = None) -> list[AlertEventRecord]:
        params: list[object] = []
        where_clause = ""
        if tenant_id:
            where_clause = " WHERE tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT event_id, created_at, tenant_id, policy_version, status,
                       violations, should_alert, suppressed, suppression_reason,
                       alert_fingerprint, routed_channels, rendered_message
                FROM alert_events
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return [
            AlertEventRecord(
                event_id=row[0],
                created_at=row[1],
                tenant_id=row[2],
                policy_version=row[3],
                status=row[4],
                violations=json.loads(row[5] or "[]"),
                should_alert=bool(row[6]),
                suppressed=bool(row[7]),
                suppression_reason=row[8] or "",
                alert_fingerprint=row[9] or "",
                routed_channels=json.loads(row[10] or "[]"),
                rendered_message=row[11] or "",
            )
            for row in rows
        ]

    def summarize_alert_events(self, created_after: str, tenant_id: str | None = None) -> dict[str, object]:
        params: list[object] = [created_after]
        tenant_clause = ""
        if tenant_id:
            tenant_clause = " AND tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT status, violations, suppressed
                FROM alert_events
                WHERE created_at >= ?{tenant_clause}
                """,
                tuple(params),
            ).fetchall()
        total_events = len(rows)
        status_counts: dict[str, int] = {}
        suppression_count = 0
        violation_counts: dict[str, int] = {}
        for status, violations_raw, suppressed_raw in rows:
            status_counts[status] = status_counts.get(status, 0) + 1
            suppression_count += int(bool(suppressed_raw))
            for violation in json.loads(violations_raw or "[]"):
                violation_counts[str(violation)] = violation_counts.get(str(violation), 0) + 1
        top_violations = sorted(
            [{"violation": key, "count": value} for key, value in violation_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:5]
        suppression_rate = (suppression_count / total_events) if total_events else 0.0
        return {
            "total_events": total_events,
            "status_counts": status_counts,
            "suppression_count": suppression_count,
            "suppression_rate": round(suppression_rate, 4),
            "top_violations": top_violations,
        }

    def archive_alert_events(self, before_ts: str, tenant_id: str | None = None) -> tuple[str, int, int]:
        params: list[object] = [before_ts]
        tenant_clause = ""
        if tenant_id:
            tenant_clause = " AND tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT event_id, created_at, tenant_id, policy_version, status,
                       violations, should_alert, suppressed, suppression_reason,
                       alert_fingerprint, routed_channels, rendered_message
                FROM alert_events
                WHERE created_at < ?{tenant_clause}
                ORDER BY created_at ASC
                """,
                tuple(params),
            ).fetchall()
            if not rows:
                return "", 0, 0
            payload = json.dumps(rows, ensure_ascii=False).encode("utf-8")
            compressed_payload = gzip.compress(payload)
            archive_id = str(uuid.uuid4())
            self.conn.execute(
                """
                INSERT INTO alert_event_archives (
                    archive_id, created_at, tenant_id, before_ts, event_count, compressed_payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    archive_id,
                    datetime.now(timezone.utc).isoformat(),
                    tenant_id or "",
                    before_ts,
                    len(rows),
                    compressed_payload,
                ),
            )
            ids = [(row[0],) for row in rows]
            self.conn.executemany("DELETE FROM alert_events WHERE event_id = ?", ids)
            self.conn.commit()
        return archive_id, len(rows), len(compressed_payload)

    def list_alert_archives(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertArchiveRecord]:
        params: list[object] = []
        where_clause = ""
        if tenant_id:
            where_clause = " WHERE tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT archive_id, created_at, tenant_id, before_ts, event_count, LENGTH(compressed_payload)
                FROM alert_event_archives
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return [
            AlertArchiveRecord(
                archive_id=row[0],
                created_at=row[1],
                tenant_id=row[2],
                before_ts=row[3],
                event_count=int(row[4]),
                compressed_bytes=int(row[5] or 0),
            )
            for row in rows
        ]

    def restore_alert_archive(self, archive_id: str) -> tuple[int, int]:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT compressed_payload
                FROM alert_event_archives
                WHERE archive_id = ?
                """,
                (archive_id,),
            ).fetchone()
            if row is None:
                return 0, 0
            compressed_payload = row[0]
            restored_rows = json.loads(gzip.decompress(compressed_payload).decode("utf-8"))
            attempted = len(restored_rows)
            restored = 0
            for payload_row in restored_rows:
                result = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO alert_events (
                        event_id, created_at, tenant_id, policy_version, status,
                        violations, should_alert, suppressed, suppression_reason,
                        alert_fingerprint, routed_channels, rendered_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(payload_row),
                )
                restored += int(result.rowcount)
            self.conn.commit()
        return restored, attempted

    def reconcile_alert_sla(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        params: list[object] = [created_after]
        tenant_clause = ""
        if tenant_id:
            tenant_clause = " AND tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            row = self.conn.execute(
                f"""
                SELECT
                    COUNT(1) AS total_events,
                    SUM(CASE WHEN status = 'degraded' THEN 1 ELSE 0 END) AS degraded_events,
                    SUM(CASE WHEN status = 'degraded' AND suppressed = 0 THEN 1 ELSE 0 END) AS open_degraded_events
                FROM alert_events
                WHERE created_at >= ?{tenant_clause}
                """,
                tuple(params),
            ).fetchone()
        total_events = int(row[0] or 0)
        degraded_events = int(row[1] or 0)
        open_degraded_events = int(row[2] or 0)
        return {
            "total_events": total_events,
            "degraded_events": degraded_events,
            "open_degraded_events": open_degraded_events,
        }

    def create_remediation_ticket(
        self,
        tenant_id: str,
        title: str,
        severity: str,
        details: str,
    ) -> AlertRemediationTicket:
        ticket = AlertRemediationTicket(
            ticket_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            title=title,
            severity=severity,
            status="open",
            details=details,
        )
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO alert_remediation_tickets (
                    ticket_id, created_at, tenant_id, title, severity, status, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.ticket_id,
                    ticket.created_at,
                    ticket.tenant_id,
                    ticket.title,
                    ticket.severity,
                    ticket.status,
                    ticket.details,
                ),
            )
            self.conn.commit()
        return ticket

    def list_remediation_tickets(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertRemediationTicket]:
        params: list[object] = []
        where_clause = ""
        if tenant_id:
            where_clause = " WHERE tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT ticket_id, created_at, tenant_id, title, severity, status, details
                FROM alert_remediation_tickets
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return [
            AlertRemediationTicket(
                ticket_id=row[0],
                created_at=row[1],
                tenant_id=row[2],
                title=row[3],
                severity=row[4],
                status=row[5],
                details=row[6],
            )
            for row in rows
        ]

    def close_remediation_ticket(self, ticket_id: str, resolution_note: str = "") -> AlertRemediationTicket | None:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT ticket_id, created_at, tenant_id, title, severity, status, details
                FROM alert_remediation_tickets
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            ).fetchone()
            if row is None:
                return None
            details = row[6] or ""
            if resolution_note:
                details = f"{details}\n[resolution] {resolution_note}".strip()
            self.conn.execute(
                """
                UPDATE alert_remediation_tickets
                SET status = 'closed', details = ?
                WHERE ticket_id = ?
                """,
                (details, ticket_id),
            )
            self.conn.commit()
        return AlertRemediationTicket(
            ticket_id=row[0],
            created_at=row[1],
            tenant_id=row[2],
            title=row[3],
            severity=row[4],
            status="closed",
            details=details,
        )

    def summarize_root_causes(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        params: list[object] = [created_after]
        tenant_clause = ""
        if tenant_id:
            tenant_clause = " AND tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT violations
                FROM alert_events
                WHERE created_at >= ?{tenant_clause}
                """,
                tuple(params),
            ).fetchall()
        counts = {"reliability": 0, "quality": 0, "latency": 0, "unknown": 0}
        for (violations_raw,) in rows:
            violations = json.loads(violations_raw or "[]")
            for violation in violations:
                if violation == "success_rate_below_threshold":
                    counts["reliability"] += 1
                elif violation == "avg_quality_below_threshold":
                    counts["quality"] += 1
                elif violation == "avg_duration_above_threshold":
                    counts["latency"] += 1
                else:
                    counts["unknown"] += 1
        return counts

    def summarize_ticket_status(self, created_after: str, tenant_id: str | None = None) -> dict[str, int]:
        params: list[object] = [created_after]
        tenant_clause = ""
        if tenant_id:
            tenant_clause = " AND tenant_id = ?"
            params.append(tenant_id)
        with self.lock:
            row = self.conn.execute(
                f"""
                SELECT
                    COUNT(1) AS total_tickets,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_tickets,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_tickets
                FROM alert_remediation_tickets
                WHERE created_at >= ?{tenant_clause}
                """,
                tuple(params),
            ).fetchone()
        return {
            "total_tickets": int(row[0] or 0),
            "closed_tickets": int(row[1] or 0),
            "open_tickets": int(row[2] or 0),
        }

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
        experiment_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO alert_strategy_experiments (
                    experiment_id, created_at, tenant_id, days,
                    baseline_max_open_degraded_alerts, candidate_max_open_degraded_alerts,
                    baseline_quality_score, candidate_quality_score, regression_delta, min_allowed_delta,
                    guardrail_passed, recommend_promote_candidate, reasons
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    created_at,
                    tenant_id,
                    int(days),
                    int(baseline_max_open_degraded_alerts),
                    int(candidate_max_open_degraded_alerts),
                    float(baseline_quality_score),
                    float(candidate_quality_score),
                    float(regression_delta),
                    float(min_allowed_delta),
                    int(guardrail_passed),
                    int(recommend_promote_candidate),
                    json.dumps(reasons),
                ),
            )
            self.conn.commit()
        return AlertStrategyExperimentRecord(
            experiment_id=experiment_id,
            created_at=created_at,
            tenant_id=tenant_id,
            days=int(days),
            baseline_max_open_degraded_alerts=int(baseline_max_open_degraded_alerts),
            candidate_max_open_degraded_alerts=int(candidate_max_open_degraded_alerts),
            baseline_quality_score=float(baseline_quality_score),
            candidate_quality_score=float(candidate_quality_score),
            regression_delta=float(regression_delta),
            min_allowed_delta=float(min_allowed_delta),
            guardrail_passed=bool(guardrail_passed),
            recommend_promote_candidate=bool(recommend_promote_candidate),
            reasons=list(reasons),
        )

    def list_strategy_experiments(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[AlertStrategyExperimentRecord]:
        where_parts = ["1=1"]
        params: list[object] = []
        if tenant_id:
            where_parts.append("tenant_id = ?")
            params.append(tenant_id)
        params.extend([int(limit), int(offset)])
        with self.lock:
            rows = self.conn.execute(
                f"""
                SELECT
                    experiment_id, created_at, tenant_id, days,
                    baseline_max_open_degraded_alerts, candidate_max_open_degraded_alerts,
                    baseline_quality_score, candidate_quality_score, regression_delta, min_allowed_delta,
                    guardrail_passed, recommend_promote_candidate, reasons
                FROM alert_strategy_experiments
                WHERE {' AND '.join(where_parts)}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [
            AlertStrategyExperimentRecord(
                experiment_id=row[0],
                created_at=row[1],
                tenant_id=row[2],
                days=int(row[3]),
                baseline_max_open_degraded_alerts=int(row[4]),
                candidate_max_open_degraded_alerts=int(row[5]),
                baseline_quality_score=float(row[6]),
                candidate_quality_score=float(row[7]),
                regression_delta=float(row[8]),
                min_allowed_delta=float(row[9]),
                guardrail_passed=bool(row[10]),
                recommend_promote_candidate=bool(row[11]),
                reasons=json.loads(row[12] or "[]"),
            )
            for row in rows
        ]

    def summarize_strategy_experiments(self, created_after: str, tenant_id: str | None = None) -> dict[str, float]:
        where_parts = ["created_at >= ?"]
        params: list[object] = [created_after]
        if tenant_id:
            where_parts.append("tenant_id = ?")
            params.append(tenant_id)
        with self.lock:
            row = self.conn.execute(
                f"""
                SELECT
                    COUNT(*),
                    AVG(regression_delta),
                    AVG(CASE WHEN guardrail_passed = 1 THEN 1.0 ELSE 0.0 END),
                    AVG(CASE WHEN recommend_promote_candidate = 1 THEN 1.0 ELSE 0.0 END)
                FROM alert_strategy_experiments
                WHERE {' AND '.join(where_parts)}
                """,
                params,
            ).fetchone()
        total, avg_delta, pass_rate, promotion_rate = row if row is not None else (0, 0.0, 0.0, 0.0)
        return {
            "total_experiments": int(total or 0),
            "avg_regression_delta": round(float(avg_delta or 0.0), 4),
            "guardrail_pass_rate": round(float(pass_rate or 0.0), 4),
            "promotion_rate": round(float(promotion_rate or 0.0), 4),
        }

    def purge_older_than_days(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        with self.lock:
            run_ids = [
                row[0]
                for row in self.conn.execute(
                    "SELECT run_id FROM pipeline_runs WHERE created_at < ?",
                    (cutoff_iso,),
                ).fetchall()
            ]
            if not run_ids:
                return 0

            self.conn.executemany(
                "DELETE FROM pipeline_runs WHERE run_id = ?",
                [(r,) for r in run_ids],
            )
            self.conn.executemany(
                "DELETE FROM idempotency_keys WHERE run_id = ?",
                [(r,) for r in run_ids],
            )
            self.conn.commit()

        return len(run_ids)

    def close(self) -> None:
        with self.lock:
            self.conn.close()
