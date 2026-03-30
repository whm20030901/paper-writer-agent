import json
import sqlite3
from types import SimpleNamespace

import pytest

from paper_writer_agent.services.paper_service import PaperService
from paper_writer_agent.services.run_store import IdempotencyConflictError, RunStore


def test_run_store_migrates_legacy_rows_and_backfills_derived_columns(tmp_path):
    db_path = tmp_path / "legacy_runs.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE pipeline_runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            task TEXT NOT NULL DEFAULT '',
            stop_reason TEXT NOT NULL DEFAULT '',
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE idempotency_keys (
            idempotency_key TEXT PRIMARY KEY,
            run_id TEXT NOT NULL
        )
        """
    )
    payload = {
        "run_id": "legacy-1",
        "parent_run_id": "",
        "root_run_id": "legacy-1",
        "task": "Legacy task",
        "outline": "Intro",
        "revision_notes": "Tighten evidence alignment.",
        "iterations_requested": 2,
        "iterations_used": 2,
        "quality_score": 7,
        "stop_reason": "done",
        "draft": "draft",
        "review": "review",
        "created_at": "2026-01-01T00:00:00+00:00",
        "duration_ms": 123,
        "prompt_version": "legacy-v0",
        "generation_params": {"paper_type": "review", "iterations": 2},
    }
    conn.execute(
        "INSERT INTO pipeline_runs(run_id, created_at, task, stop_reason, payload) VALUES (?, ?, ?, ?, ?)",
        ("legacy-1", payload["created_at"], "", "", json.dumps(payload)),
    )
    conn.commit()
    conn.close()

    store = RunStore(str(db_path))
    try:
        rows = store.list_recent(sort_by="quality_score", sort_order="desc")
        assert len(rows) == 1
        assert rows[0].run_id == "legacy-1"
        assert rows[0].root_run_id == "legacy-1"
        assert rows[0].revision_notes == "Tighten evidence alignment."
        assert rows[0].quality_score == 7
        assert rows[0].duration_ms == 123
        assert rows[0].prompt_version == "legacy-v0"
        assert rows[0].generation_params["paper_type"] == "review"

        stats = store.stats(min_quality_score=7, max_duration_ms=200)
        assert stats.total_runs == 1
        assert stats.avg_quality_score == 7.0
        assert stats.avg_duration_ms == 123.0
        assert stats.success_rate == 1.0

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT task, stop_reason, quality_score, duration_ms, prompt_version FROM pipeline_runs WHERE run_id = ?",
            ("legacy-1",),
        ).fetchone()
        conn.close()
        assert row == ("Legacy task", "done", 7, 123, "legacy-v0")
    finally:
        store.close()


def test_bind_idempotency_key_returns_existing_run_and_removes_losing_duplicate(tmp_path):
    db_path = tmp_path / "idempotency.db"
    store = RunStore(str(db_path))
    try:
        first_run_id = store.create(
            SimpleNamespace(
                run_id="first-run",
                parent_run_id="",
                root_run_id="",
                task="Task A",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=8,
                stop_reason="done",
                draft="draft-a",
                review="review-a",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=11,
            )
        )
        assert first_run_id == "first-run"
        assert store.bind_idempotency_key("idem-1", first_run_id, "fingerprint-a") == first_run_id

        second_run_id = store.create(
            SimpleNamespace(
                run_id="second-run",
                parent_run_id="",
                root_run_id="",
                task="Task B",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=5,
                stop_reason="done",
                draft="draft-b",
                review="review-b",
                created_at="2026-01-01T00:01:00+00:00",
                duration_ms=22,
            )
        )
        assert second_run_id == "second-run"

        bound_run_id = store.bind_idempotency_key("idem-1", second_run_id, "fingerprint-a")
        assert bound_run_id == "first-run"
        assert store.get("first-run") is not None
        assert store.get("second-run") is None
    finally:
        store.close()


def test_bind_idempotency_key_rejects_conflicting_request_fingerprint(tmp_path):
    db_path = tmp_path / "idempotency_conflict.db"
    store = RunStore(str(db_path))
    try:
        first_run_id = store.create(
            SimpleNamespace(
                run_id="first-run",
                parent_run_id="",
                root_run_id="",
                task="Task A",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=8,
                stop_reason="done",
                draft="draft-a",
                review="review-a",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=11,
            )
        )
        second_run_id = store.create(
            SimpleNamespace(
                run_id="second-run",
                parent_run_id="",
                root_run_id="",
                task="Task B",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=5,
                stop_reason="done",
                draft="draft-b",
                review="review-b",
                created_at="2026-01-01T00:01:00+00:00",
                duration_ms=22,
            )
        )

        assert store.bind_idempotency_key("idem-1", first_run_id, "fingerprint-a") == first_run_id
        with pytest.raises(IdempotencyConflictError):
            store.bind_idempotency_key("idem-1", second_run_id, "fingerprint-b")

        assert store.get(second_run_id) is None
    finally:
        store.close()


def test_paper_service_returns_existing_run_when_bind_loses_idempotency_race(tmp_path):
    class FakePipeline:
        def __init__(self):
            self.calls = 0

        def run(self, task: str, outline: str, iterations: int, revision_notes: str = ""):
            self.calls += 1
            return SimpleNamespace(
                draft=f"draft-{self.calls}",
                review=f"review-{self.calls}",
                iterations_used=iterations,
                quality_score=8 - self.calls,
                stop_reason="done",
            )

        def close(self):
            return None

    store = RunStore(str(tmp_path / "service_idem.db"))
    service = PaperService(pipeline=FakePipeline(), run_store=store)
    try:
        first = service.generate("Task", "Outline", 1, idempotency_key="idem-race")
        original_lookup = store.get_idempotency_binding
        store.get_idempotency_binding = lambda _: None
        try:
            replay = service.generate("Task", "Outline", 1, idempotency_key="idem-race")
        finally:
            store.get_idempotency_binding = original_lookup

        assert replay.run_id == first.run_id
        assert replay.idempotent_replay is True
        assert replay.draft == first.draft
        assert store.count_runs() == 1
    finally:
        service.close()


def test_list_recent_respects_requested_sort_direction_for_tiebreakers(tmp_path):
    store = RunStore(str(tmp_path / "sort_tiebreak.db"))
    try:
        shared_score = 7
        store.create(
            SimpleNamespace(
                run_id="older",
                parent_run_id="",
                root_run_id="",
                task="Older task",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=shared_score,
                stop_reason="done",
                draft="draft-older",
                review="review-older",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=10,
            )
        )
        store.create(
            SimpleNamespace(
                run_id="newer",
                parent_run_id="",
                root_run_id="",
                task="Newer task",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=shared_score,
                stop_reason="done",
                draft="draft-newer",
                review="review-newer",
                created_at="2026-01-01T00:05:00+00:00",
                duration_ms=20,
            )
        )

        asc_rows = store.list_recent(sort_by="quality_score", sort_order="asc")
        desc_rows = store.list_recent(sort_by="quality_score", sort_order="desc")

        assert [row.run_id for row in asc_rows] == ["older", "newer"]
        assert [row.run_id for row in desc_rows] == ["newer", "older"]
    finally:
        store.close()



def test_run_store_lists_direct_children(tmp_path):
    store = RunStore(str(tmp_path / "lineage_children.db"))
    try:
        store.create(
            SimpleNamespace(
                run_id="root",
                parent_run_id="",
                root_run_id="",
                task="Root task",
                outline="Outline",
                revision_notes="",
                iterations_requested=1,
                iterations_used=1,
                quality_score=8,
                stop_reason="done",
                draft="draft-root",
                review="review-root",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=10,
            )
        )
        store.create(
            SimpleNamespace(
                run_id="child-1",
                parent_run_id="root",
                root_run_id="root",
                task="Root task",
                outline="Outline",
                revision_notes="First manual revision",
                iterations_requested=1,
                iterations_used=1,
                quality_score=8,
                stop_reason="manual_edit",
                draft="draft-child-1",
                review="review-child-1",
                created_at="2026-01-01T00:05:00+00:00",
                duration_ms=0,
            )
        )
        store.create(
            SimpleNamespace(
                run_id="child-2",
                parent_run_id="root",
                root_run_id="root",
                task="Root task",
                outline="Outline",
                revision_notes="Second manual revision",
                iterations_requested=1,
                iterations_used=1,
                quality_score=9,
                stop_reason="manual_edit",
                draft="draft-child-2",
                review="review-child-2",
                created_at="2026-01-01T00:10:00+00:00",
                duration_ms=0,
            )
        )

        store.create(
            SimpleNamespace(
                run_id="grandchild",
                parent_run_id="child-2",
                root_run_id="root",
                task="Root task",
                outline="Outline",
                revision_notes="Third manual revision",
                iterations_requested=1,
                iterations_used=1,
                quality_score=9,
                stop_reason="manual_edit",
                draft="draft-grandchild",
                review="review-grandchild",
                created_at="2026-01-01T00:15:00+00:00",
                duration_ms=0,
            )
        )

        children = store.list_children("root")
        assert [child.run_id for child in children] == ["child-2", "child-1"]

        descendants = store.list_descendants("root")
        assert [record.run_id for record in descendants] == ["child-2", "child-1", "grandchild"]

        ancestors = store.list_ancestors("grandchild")
        assert [record.run_id for record in ancestors] == ["child-2", "root"]
    finally:
        store.close()
