import gzip
from types import SimpleNamespace
from fastapi.testclient import TestClient

from paper_writer_agent.api.app import create_app
from paper_writer_agent.core.config import Settings
from paper_writer_agent.services.paper_service import PaperService




def test_index_page_available():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Paper Writer Agent" in response.text
    assert "Generate Paper" in response.text
    assert "Revision Notes" in response.text
    assert "Paper Preview" in response.text
    assert "Review Summary" in response.text
    assert "Download Latest Draft (.md)" in response.text
    assert "Run Detail" in response.text
    assert "Load Run into Editor" in response.text
    assert "Download Markdown" in response.text
    assert "Revision Plan" in response.text
    assert "Apply Selected Plan Items" in response.text
    assert "Draft Diff (vs Parent)" in response.text
    assert "Load Diff Against Parent" in response.text
    assert "Run Lineage" in response.text
    assert "Editing Workspace" in response.text
    assert "Load Latest Draft into Workspace" in response.text
    assert "Load Selected Run Draft" in response.text
    assert "Preview Workspace Draft" in response.text
    assert "Download Edited Draft (.md)" in response.text
    assert "Save Edited Draft as New Run" in response.text
    assert "Import Markdown File" in response.text
    assert "Clear Workspace" in response.text
    assert "Metrics" in response.text
    assert "Keyword (q)" in response.text
    assert "Export CSV" in response.text
    assert "Next Page" in response.text
    assert "Parent Run ID" in response.text
    assert "Root Run ID" in response.text
    assert "Lineage Scope" in response.text
    assert "Created After" in response.text
    assert "Created Before" in response.text
    assert "Min Quality" in response.text
    assert "Sort By" in response.text
    assert "Min Duration" in response.text
    assert "Clear Filters" in response.text
    assert "Page Size" in response.text
    assert "Total Runs" in response.text
    assert "Avg Quality" in response.text
    assert "Success Rate" in response.text
    assert '/static/app.css' in response.text
    assert '/static/app.js' in response.text


def test_frontend_static_assets_available():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    css_response = client.get("/static/app.css")
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".metrics-grid" in css_response.text

    js_response = client.get("/static/app.js")
    assert js_response.status_code == 200
    assert "javascript" in js_response.headers["content-type"]
    assert "generatePaper" in js_response.text
    assert "renderPaperMarkup" in js_response.text
    assert "renderRunSummary" in js_response.text
    assert "renderRunLineage" in js_response.text
    assert "loadRunLineage" in js_response.text
    assert "parentRunFilter" in js_response.text
    assert "rootRunFilter" in js_response.text
    assert "lineageScopeFilter" in js_response.text
    assert "prefillEditorFromRun" in js_response.text
    assert "setDraftDownloadLink" in js_response.text
    assert "previewWorkspaceDraft" in js_response.text
    assert "downloadWorkspaceDraft" in js_response.text
    assert "restoreWorkspaceDraft" in js_response.text
    assert "importWorkspaceFile" in js_response.text
    assert "saveWorkspaceDraftAsRun" in js_response.text
    assert "loadRevisionPlan" in js_response.text
    assert "applySelectedPlanItems" in js_response.text
    assert "loadDiffAgainstParent" in js_response.text

def test_health_and_ready_endpoint():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert "x-request-id" in health.headers
    assert health.headers["x-request-id"]

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert "x-request-id" in ready.headers
    assert ready.headers["x-request-id"]


def test_request_id_header_is_normalized_when_blank():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "   "})
    assert response.status_code == 200
    assert response.headers["x-request-id"].strip()
    assert response.headers["x-request-id"] != "   "


def test_ready_returns_503_when_dependency_unavailable():
    original = PaperService.is_ready
    try:
        PaperService.is_ready = lambda self: False
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 503
    finally:
        PaperService.is_ready = original


def test_startup_auto_purge_called_when_enabled():
    calls = {"count": 0}
    original = PaperService.purge_runs
    try:
        def fake_purge(self, retention_days: int) -> int:
            calls["count"] += 1
            return 0

        PaperService.purge_runs = fake_purge
        app = create_app(
            Settings(
                app_env="test",
                memory_db_path=":memory:",
                run_db_path=":memory:",
                auto_purge_on_startup=True,
            )
        )
        with TestClient(app):
            pass
        assert calls["count"] == 1
    finally:
        PaperService.purge_runs = original


def test_startup_auto_alert_archive_called_when_enabled():
    calls = {"count": 0}
    original = PaperService.archive_alert_events
    try:
        def fake_archive(self, before_ts: str, tenant_id: str | None = None):
            calls["count"] += 1
            return ("archive-startup", 0, 0)

        PaperService.archive_alert_events = fake_archive
        app = create_app(
            Settings(
                app_env="test",
                memory_db_path=":memory:",
                run_db_path=":memory:",
                slo_alert_auto_archive_on_startup=True,
                slo_alert_auto_archive_days=14,
            )
        )
        with TestClient(app):
            pass
        assert calls["count"] == 1
    finally:
        PaperService.archive_alert_events = original


def test_generate_get_run_list_and_metrics_endpoint():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    response = client.post(
        "/v1/papers/generate",
        headers={"X-Request-ID": "req-123"},
        json={
            "task": "AI agent framework for writing",
            "outline": "Intro, Method, Evaluation, Conclusion",
            "revision_notes": "Emphasize evidence-backed claims and tighten the conclusion.",
            "paper_type": "empirical",
            "tone": "neutral",
            "citation_style": "apa",
            "target_venue": "NeurIPS Workshop",
            "iterations": 2,
        },
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-123"

    body = response.json()
    assert body["idempotent_replay"] is False
    assert body["trace_id"]
    assert body["prompt_version"] == "v1"
    assert body["generation_params"]["paper_type"] == "empirical"
    assert body["generation_params"]["tone"] == "neutral"
    assert body["generation_params"]["citation_style"] == "apa"
    assert isinstance(body["duration_ms"], int)
    assert body["review_report"]["score"] == body["quality_score"]
    assert body["review_report"]["revision_plan"]
    assert body["research_sources"]
    assert any(source["title"] == "Local knowledge base: agent_survey" for source in body["research_sources"])

    run_response = client.get(f"/v1/papers/runs/{body['run_id']}")
    assert run_response.status_code == 200
    assert run_response.json()["trace_id"]
    assert run_response.json()["prompt_version"] == "v1"
    assert run_response.json()["generation_params"]["target_venue"] == "NeurIPS Workshop"
    assert isinstance(run_response.json()["duration_ms"], int)
    assert run_response.json()["parent_run_id"] == ""
    assert run_response.json()["root_run_id"] == body["run_id"]
    assert "Emphasize evidence-backed claims and tighten the conclusion." in run_response.json()["revision_notes"]
    assert "Paper Type: empirical" in run_response.json()["revision_notes"]
    assert "Tone: neutral" in run_response.json()["revision_notes"]
    assert "Citation Style: apa" in run_response.json()["revision_notes"]
    assert "Target Venue: NeurIPS Workshop" in run_response.json()["revision_notes"]
    assert run_response.json()["review_report"] == body["review_report"]
    assert run_response.json()["research_sources"] == body["research_sources"]
    assert "Revision Focus" in run_response.json()["draft"]

    sources_response = client.get(f"/v1/papers/runs/{body['run_id']}/sources")
    assert sources_response.status_code == 200
    sources_body = sources_response.json()
    assert sources_body["run_id"] == body["run_id"]
    assert sources_body["source_count"] == len(body["research_sources"])
    assert sources_body["sources"] == body["research_sources"]

    references_response = client.get(f"/v1/papers/runs/{body['run_id']}/references?style=mla")
    assert references_response.status_code == 200
    references_body = references_response.json()
    assert references_body["run_id"] == body["run_id"]
    assert references_body["style"] == "mla"
    assert references_body["source_count"] == len(body["research_sources"])
    assert references_body["references"]

    review_report_response = client.get(f"/v1/papers/runs/{body['run_id']}/review-report")
    assert review_report_response.status_code == 200
    review_report_body = review_report_response.json()
    assert review_report_body["run_id"] == body["run_id"]
    assert review_report_body["review_report"] == body["review_report"]

    quality_breakdown_response = client.get(f"/v1/papers/runs/{body['run_id']}/quality-breakdown")
    assert quality_breakdown_response.status_code == 200
    quality_breakdown_body = quality_breakdown_response.json()
    assert quality_breakdown_body["run_id"] == body["run_id"]
    assert quality_breakdown_body["overall_score"] == body["quality_score"]
    assert 0 <= quality_breakdown_body["structure_score"] <= 10
    assert 0 <= quality_breakdown_body["evidence_score"] <= 10
    assert 0 <= quality_breakdown_body["citation_score"] <= 10
    assert 0 <= quality_breakdown_body["language_score"] <= 10
    assert isinstance(quality_breakdown_body["recommendations"], list)

    revision_plan_response = client.get(f"/v1/papers/runs/{body['run_id']}/revision-plan")
    assert revision_plan_response.status_code == 200
    revision_plan_body = revision_plan_response.json()
    assert revision_plan_body["run_id"] == body["run_id"]
    assert revision_plan_body["total_items"] >= 1
    assert revision_plan_body["items"]

    apply_revision_plan_response = client.post(
        f"/v1/papers/runs/{body['run_id']}/revision-plan/apply",
        json={"selected_items": [revision_plan_body["items"][0]], "mode": "patch"},
    )
    assert apply_revision_plan_response.status_code == 200
    apply_revision_plan_body = apply_revision_plan_response.json()
    assert apply_revision_plan_body["run_id"] != body["run_id"]
    assert "Applied Revision Plan" in apply_revision_plan_body["draft"]

    citation_audit_response = client.get(f"/v1/papers/runs/{body['run_id']}/citation-audit")
    assert citation_audit_response.status_code == 200
    citation_audit_body = citation_audit_response.json()
    assert citation_audit_body["run_id"] == body["run_id"]
    assert citation_audit_body["inline_markers"]
    assert citation_audit_body["reference_markers"]
    assert citation_audit_body["missing_reference_entries"] == []
    assert citation_audit_body["unused_reference_entries"] == []
    assert 0 <= citation_audit_body["coverage_score"] <= 1

    insights_response = client.get(f"/v1/papers/runs/{body['run_id']}/insights")
    assert insights_response.status_code == 200
    insights_body = insights_response.json()
    assert insights_body["run_id"] == body["run_id"]
    assert insights_body["quality_score"] == body["quality_score"]
    assert insights_body["source_count"] == len(body["research_sources"])
    assert insights_body["inline_citation_count"] >= 1
    assert insights_body["revision_plan_items"] >= 1
    assert insights_body["evidence_linked_source_count"] >= 1
    assert 0 <= insights_body["citation_coverage_score"] <= 1

    markdown_response = client.get(f"/v1/papers/runs/{body['run_id']}/draft.md")
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert body["draft"] == markdown_response.text
    assert f'{body["run_id"]}.md' in markdown_response.headers["content-disposition"]

    rewrite_section_response = client.post(
        f"/v1/papers/runs/{body['run_id']}/rewrite-section",
        json={
            "section_title": "Conclusion",
            "rewrite_goal": "Strengthen contribution statement and future work section.",
            "keep_citations": True,
            "max_tokens": 300,
        },
    )
    assert rewrite_section_response.status_code == 200
    rewrite_section_body = rewrite_section_response.json()
    assert rewrite_section_body["run_id"] == body["run_id"]
    assert rewrite_section_body["section_title"] == "Conclusion"
    assert rewrite_section_body["updated_section_markdown"].startswith("## Conclusion")
    assert 0 <= rewrite_section_body["quality_delta_estimate"] <= 1

    save_response = client.post(
        f"/v1/papers/runs/{body['run_id']}/save-edited",
        json={
            "draft": body["draft"] + "\n\n## Manual Touch-up\nAdded from workspace.",
            "review": "Manual edit saved from workspace.",
            "revision_notes": "Add a short manual touch-up section.",
        },
    )
    assert save_response.status_code == 200
    saved_body = save_response.json()
    assert saved_body["run_id"] != body["run_id"]
    assert saved_body["stop_reason"] == "manual_edit"
    assert "Manual Touch-up" in saved_body["draft"]
    saved_detail = client.get(f"/v1/papers/runs/{saved_body['run_id']}")
    assert saved_detail.status_code == 200
    assert saved_detail.json()["parent_run_id"] == body["run_id"]
    assert saved_detail.json()["root_run_id"] == body["run_id"]
    diff_response = client.get(f"/v1/papers/runs/{saved_body['run_id']}/diff", params={"against": body["run_id"]})
    assert diff_response.status_code == 200
    diff_body = diff_response.json()
    assert diff_body["run_id"] == saved_body["run_id"]
    assert diff_body["against_run_id"] == body["run_id"]
    assert diff_body["changed"] is True
    assert diff_body["added_lines"] >= 1
    assert diff_body["removed_lines"] >= 0
    assert "run:" in diff_body["diff_preview"]

    grandchild_response = client.post(
        f"/v1/papers/runs/{saved_body['run_id']}/save-edited",
        json={
            "draft": saved_body["draft"] + "\n\n## Second Manual Touch-up\nAdded from second workspace pass.",
            "review": "Manual edit saved from workspace.",
            "revision_notes": "Add a second manual touch-up section.",
        },
    )
    assert grandchild_response.status_code == 200
    grandchild_body = grandchild_response.json()
    assert grandchild_body["run_id"] not in {body["run_id"], saved_body["run_id"]}
    rollback_response = client.post(
        f"/v1/papers/runs/{grandchild_body['run_id']}/rollback",
        json={"to_run_id": body["run_id"], "reason": "Restore original baseline before branch edits."},
    )
    assert rollback_response.status_code == 200
    rollback_body = rollback_response.json()
    assert rollback_body["run_id"] not in {body["run_id"], saved_body["run_id"], grandchild_body["run_id"]}
    assert rollback_body["draft"] == body["draft"]
    assert "Rollback" in rollback_body["review"]

    lineage_response = client.get(f"/v1/papers/runs/{body['run_id']}/lineage")
    assert lineage_response.status_code == 200
    lineage_body = lineage_response.json()
    assert lineage_body["run"]["run_id"] == body["run_id"]
    assert lineage_body["parent"] is None
    assert lineage_body["ancestors"] == []
    assert lineage_body["children"][0]["source_count"] >= 1
    assert isinstance(lineage_body["children"][0]["has_review_report"], bool)
    assert lineage_body["children"][0]["inline_citation_count"] >= 1
    assert lineage_body["children"][0]["revision_plan_items"] >= 1
    child_ids = [child["run_id"] for child in lineage_body["children"]]
    descendant_ids = [descendant["run_id"] for descendant in lineage_body["descendants"]]
    assert saved_body["run_id"] in child_ids
    assert grandchild_body["run_id"] in descendant_ids

    child_lineage = client.get(f"/v1/papers/runs/{saved_body['run_id']}/lineage")
    assert child_lineage.status_code == 200
    child_lineage_body = child_lineage.json()
    assert child_lineage_body["parent"]["run_id"] == body["run_id"]
    assert [ancestor["run_id"] for ancestor in child_lineage_body["ancestors"]] == [body["run_id"]]
    child_descendant_ids = [descendant["run_id"] for descendant in child_lineage_body["descendants"]]
    assert grandchild_body["run_id"] in child_descendant_ids

    grandchild_lineage = client.get(f"/v1/papers/runs/{grandchild_body['run_id']}/lineage")
    assert grandchild_lineage.status_code == 200
    grandchild_lineage_body = grandchild_lineage.json()
    assert [ancestor["run_id"] for ancestor in grandchild_lineage_body["ancestors"]] == [saved_body["run_id"], body["run_id"]]
    grandchild_descendant_ids = [descendant["run_id"] for descendant in grandchild_lineage_body["descendants"]]
    assert rollback_body["run_id"] in grandchild_descendant_ids

    not_found = client.get("/v1/papers/runs/not-exist")
    assert not_found.status_code == 404
    not_found_sources = client.get("/v1/papers/runs/not-exist/sources")
    assert not_found_sources.status_code == 404
    not_found_references = client.get("/v1/papers/runs/not-exist/references?style=apa")
    assert not_found_references.status_code == 404
    not_found_review_report = client.get("/v1/papers/runs/not-exist/review-report")
    assert not_found_review_report.status_code == 404
    not_found_breakdown = client.get("/v1/papers/runs/not-exist/quality-breakdown")
    assert not_found_breakdown.status_code == 404
    not_found_rollback_base = client.post(
        "/v1/papers/runs/not-exist/rollback",
        json={"to_run_id": body["run_id"]},
    )
    assert not_found_rollback_base.status_code == 404
    not_found_rollback_target = client.post(
        f"/v1/papers/runs/{body['run_id']}/rollback",
        json={"to_run_id": "not-exist"},
    )
    assert not_found_rollback_target.status_code == 404
    not_found_diff = client.get(f"/v1/papers/runs/{body['run_id']}/diff", params={"against": "not-exist"})
    assert not_found_diff.status_code == 404
    not_found_revision_plan = client.get("/v1/papers/runs/not-exist/revision-plan")
    assert not_found_revision_plan.status_code == 404
    not_found_apply_plan = client.post(
        "/v1/papers/runs/not-exist/revision-plan/apply",
        json={"selected_items": ["item"], "mode": "patch"},
    )
    assert not_found_apply_plan.status_code == 404
    not_found_citation_audit = client.get("/v1/papers/runs/not-exist/citation-audit")
    assert not_found_citation_audit.status_code == 404
    not_found_rewrite = client.post(
        "/v1/papers/runs/not-exist/rewrite-section",
        json={"section_title": "Conclusion", "rewrite_goal": "Improve summary"},
    )
    assert not_found_rewrite.status_code == 404
    not_found_insights = client.get("/v1/papers/runs/not-exist/insights")
    assert not_found_insights.status_code == 404

    list_response = client.get("/v1/papers/runs?limit=10&offset=0")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] >= 1
    assert "parent_run_id" in list_body["items"][0]
    assert "root_run_id" in list_body["items"][0]
    assert "source_count" in list_body["items"][0]
    assert "has_review_report" in list_body["items"][0]
    assert "inline_citation_count" in list_body["items"][0]
    assert "revision_plan_items" in list_body["items"][0]
    assert "trace_id" in list_body["items"][0]
    assert isinstance(list_body["has_more"], bool)
    assert (list_body["next_offset"] is None) or isinstance(list_body["next_offset"], int)
    assert any(item["run_id"] == body["run_id"] for item in list_body["items"])
    assert isinstance(list_body["items"][0]["duration_ms"], int)

    metrics = client.get("/v1/papers/metrics")
    assert metrics.status_code == 200
    metrics_body = metrics.json()
    assert metrics_body["total_runs"] >= 1
    assert isinstance(metrics_body["avg_quality_score"], float)
    assert isinstance(metrics_body["avg_duration_ms"], float)
    assert 0 <= metrics_body["success_rate"] <= 1

    slo = client.get("/v1/papers/slo")
    assert slo.status_code == 200
    slo_body = slo.json()
    assert slo_body["status"] in {"ok", "degraded", "no_data"}
    assert "thresholds" in slo_body
    assert "violations" in slo_body

    slo_history = client.get("/v1/papers/slo/history?days=30&interval=day")
    assert slo_history.status_code == 200
    slo_history_body = slo_history.json()
    assert slo_history_body["interval"] == "day"
    assert slo_history_body["days"] == 30
    assert isinstance(slo_history_body["points"], list)

    slo_alerts = client.post("/v1/papers/slo/alerts/check")
    assert slo_alerts.status_code == 200
    slo_alerts_body = slo_alerts.json()
    assert slo_alerts_body["status"] in {"ok", "degraded", "no_data"}
    assert slo_alerts_body["tenant_id"] == "default"
    assert slo_alerts_body["policy_version"]
    assert isinstance(slo_alerts_body["violations"], list)
    assert isinstance(slo_alerts_body["routed_channels"], list)
    assert isinstance(slo_alerts_body["rendered_message"], str)
    assert isinstance(slo_alerts_body["channels"], list)

    alert_events = client.get("/v1/papers/slo/alerts/events?limit=10&offset=0")
    assert alert_events.status_code == 200
    alert_events_body = alert_events.json()
    assert isinstance(alert_events_body["items"], list)
    if alert_events_body["items"]:
        event_id = alert_events_body["items"][0]["event_id"]
        replay = client.post(f"/v1/papers/slo/alerts/replay/{event_id}")
        assert replay.status_code == 200
        replay_body = replay.json()
        assert replay_body["event"]["event_id"] == event_id
        assert isinstance(replay_body["replay_message"], str)

    dashboard = client.get("/v1/papers/slo/alerts/dashboard?days=30")
    assert dashboard.status_code == 200
    dashboard_body = dashboard.json()
    assert dashboard_body["days"] == 30
    assert "total_events" in dashboard_body
    assert "top_violations" in dashboard_body

    insights_list = client.get("/v1/papers/insights?limit=10&offset=0")
    assert insights_list.status_code == 200
    insights_list_body = insights_list.json()
    assert insights_list_body["total"] >= 1
    assert insights_list_body["items"][0]["source_count"] >= 1
    assert "inline_citation_count" in insights_list_body["items"][0]
    assert "revision_plan_items" in insights_list_body["items"][0]
    assert "evidence_linked_source_count" in insights_list_body["items"][0]
    assert "citation_coverage_score" in insights_list_body["items"][0]

    insights_metrics = client.get("/v1/papers/insights/metrics")
    assert insights_metrics.status_code == 200
    insights_metrics_body = insights_metrics.json()
    assert insights_metrics_body["total_runs"] >= 1
    assert insights_metrics_body["runs_with_review_report"] >= 1
    assert insights_metrics_body["avg_source_count"] >= 1
    assert insights_metrics_body["avg_inline_citation_count"] >= 1
    assert insights_metrics_body["avg_revision_plan_items"] >= 1
    assert 0 <= insights_metrics_body["avg_citation_coverage_score"] <= 1

    insights_trends = client.get("/v1/papers/insights/trends?interval=day")
    assert insights_trends.status_code == 200
    insights_trends_body = insights_trends.json()
    assert insights_trends_body["interval"] == "day"
    assert insights_trends_body["group_by"] == "all"
    assert isinstance(insights_trends_body["points"], list)
    assert insights_trends_body["points"][0]["total_runs"] >= 1

    top_tasks = client.get("/v1/papers/insights/top-tasks?limit=5")
    assert top_tasks.status_code == 200
    top_tasks_body = top_tasks.json()
    assert top_tasks_body["total_tasks"] >= 1
    assert top_tasks_body["limit"] == 5
    assert top_tasks_body["items"][0]["run_count"] >= 1
    assert top_tasks_body["items"][0]["avg_quality_score"] >= 0


def test_slo_alerts_support_cooldown_and_force_override():
    original_get_stats = PaperService.get_stats

    def fake_get_stats(self, **kwargs):
        return SimpleNamespace(
            total_runs=3,
            success_rate=0.2,
            avg_quality_score=4.0,
            avg_duration_ms=9000.0,
            stop_reason_counts={"failed": 2, "accepted": 1},
        )

    app = create_app(
        Settings(
            app_env="test",
            memory_db_path=":memory:",
            run_db_path=":memory:",
            slo_alert_channels=["log"],
            slo_alert_cooldown_seconds=3600,
            slo_alert_dedupe_window_seconds=3600,
        )
    )
    try:
        PaperService.get_stats = fake_get_stats
        client = TestClient(app)

        first = client.post("/v1/papers/slo/alerts/check")
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["status"] == "degraded"
        assert first_body["tenant_id"] == "default"
        assert first_body["should_alert"] is True
        assert first_body["suppressed"] is False
        assert first_body["routed_channels"] == ["log"]

        second = client.post("/v1/papers/slo/alerts/check")
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["should_alert"] is True
        assert second_body["suppressed"] is True
        assert second_body["suppression_reason"] in {"cooldown_active", "duplicate_within_dedupe_window"}

        forced = client.post("/v1/papers/slo/alerts/check?force=true")
        assert forced.status_code == 200
        forced_body = forced.json()
        assert forced_body["should_alert"] is True
        assert forced_body["suppressed"] is False
    finally:
        PaperService.get_stats = original_get_stats


def test_slo_alerts_route_by_group_override():
    original_get_stats = PaperService.get_stats

    def fake_get_stats(self, **kwargs):
        return SimpleNamespace(
            total_runs=5,
            success_rate=1.0,
            avg_quality_score=4.5,
            avg_duration_ms=1000.0,
            stop_reason_counts={"accepted": 5},
        )

    app = create_app(
        Settings(
            app_env="test",
            memory_db_path=":memory:",
            run_db_path=":memory:",
            slo_alert_channels=["log", "webhook"],
            slo_alert_route_overrides={"quality": ["log"]},
        )
    )
    try:
        PaperService.get_stats = fake_get_stats
        client = TestClient(app)
        response = client.post("/v1/papers/slo/alerts/check")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["should_alert"] is True
        assert body["routed_channels"] == ["log"]
        assert body["channels"][0]["channel"] == "log"
        assert "degraded" in body["rendered_message"]
    finally:
        PaperService.get_stats = original_get_stats


def test_slo_alerts_cooldown_isolated_by_tenant():
    original_get_stats = PaperService.get_stats

    def fake_get_stats(self, **kwargs):
        return SimpleNamespace(
            total_runs=4,
            success_rate=0.25,
            avg_quality_score=5.0,
            avg_duration_ms=6000.0,
            stop_reason_counts={"failed": 3, "accepted": 1},
        )

    app = create_app(
        Settings(
            app_env="test",
            memory_db_path=":memory:",
            run_db_path=":memory:",
            slo_alert_channels=["log"],
            slo_alert_cooldown_seconds=3600,
            slo_alert_policy_version="v2",
        )
    )
    try:
        PaperService.get_stats = fake_get_stats
        client = TestClient(app)

        first_tenant_a = client.post("/v1/papers/slo/alerts/check", headers={"X-Tenant-ID": "tenant-a"})
        assert first_tenant_a.status_code == 200
        body_a1 = first_tenant_a.json()
        assert body_a1["tenant_id"] == "tenant-a"
        assert body_a1["policy_version"] == "v2"
        assert body_a1["suppressed"] is False

        second_tenant_a = client.post("/v1/papers/slo/alerts/check", headers={"X-Tenant-ID": "tenant-a"})
        assert second_tenant_a.status_code == 200
        body_a2 = second_tenant_a.json()
        assert body_a2["suppressed"] is True

        first_tenant_b = client.post("/v1/papers/slo/alerts/check", headers={"X-Tenant-ID": "tenant-b"})
        assert first_tenant_b.status_code == 200
        body_b1 = first_tenant_b.json()
        assert body_b1["tenant_id"] == "tenant-b"
        assert body_b1["suppressed"] is False

        events_a = client.get("/v1/papers/slo/alerts/events?tenant_id=tenant-a")
        assert events_a.status_code == 200
        events_a_body = events_a.json()
        assert all(item["tenant_id"] == "tenant-a" for item in events_a_body["items"])

        dashboard_a = client.get("/v1/papers/slo/alerts/dashboard?days=7&tenant_id=tenant-a")
        assert dashboard_a.status_code == 200
        dashboard_a_body = dashboard_a.json()
        assert dashboard_a_body["tenant_id"] == "tenant-a"
        assert dashboard_a_body["total_events"] >= 1

        archive_a = client.post("/v1/papers/slo/alerts/archive?before_days=0&tenant_id=tenant-a")
        assert archive_a.status_code == 200
        archive_a_body = archive_a.json()
        assert archive_a_body["tenant_id"] == "tenant-a"
        assert archive_a_body["archived_events"] >= 1
        assert archive_a_body["compressed_bytes"] >= 1

        archive_id = archive_a_body["archive_id"]
        archives = client.get("/v1/papers/slo/alerts/archives?tenant_id=tenant-a")
        assert archives.status_code == 200
        archives_body = archives.json()
        assert any(item["archive_id"] == archive_id for item in archives_body["items"])

        restore = client.post(f"/v1/papers/slo/alerts/archives/{archive_id}/restore")
        assert restore.status_code == 200
        restore_body = restore.json()
        assert restore_body["archive_id"] == archive_id
        assert restore_body["attempted_events"] >= restore_body["restored_events"] >= 1

        lifecycle = client.post("/v1/papers/slo/alerts/lifecycle/run?before_days=0&tenant_id=tenant-a")
        assert lifecycle.status_code == 200
        lifecycle_body = lifecycle.json()
        assert lifecycle_body["tenant_id"] == "tenant-a"
        assert lifecycle_body["before_days"] == 0
        assert "archive_id" in lifecycle_body

        sla = client.get("/v1/papers/slo/alerts/sla-reconcile?days=7&tenant_id=tenant-a")
        assert sla.status_code == 200
        sla_body = sla.json()
        assert sla_body["tenant_id"] == "tenant-a"
        assert "breach" in sla_body

        ticket = client.post(
            "/v1/papers/slo/alerts/remediation-tickets"
            "?tenant_id=tenant-a&title=Fix%20SLO%20breach&severity=high&details=followup"
        )
        assert ticket.status_code == 200
        ticket_body = ticket.json()
        assert ticket_body["tenant_id"] == "tenant-a"
        assert ticket_body["severity"] == "high"

        tickets = client.get("/v1/papers/slo/alerts/remediation-tickets?tenant_id=tenant-a")
        assert tickets.status_code == 200
        tickets_body = tickets.json()
        assert any(item["ticket_id"] == ticket_body["ticket_id"] for item in tickets_body["items"])

        close_ticket = client.post(
            f"/v1/papers/slo/alerts/remediation-tickets/{ticket_body['ticket_id']}/close"
            "?resolution_note=fixed"
        )
        assert close_ticket.status_code == 200
        close_ticket_body = close_ticket.json()
        assert close_ticket_body["status"] == "closed"

        root_causes = client.get("/v1/papers/slo/alerts/root-causes?days=7&tenant_id=tenant-a")
        assert root_causes.status_code == 200
        root_causes_body = root_causes.json()
        assert root_causes_body["tenant_id"] == "tenant-a"
        assert isinstance(root_causes_body["causes"], dict)

        quality_score = client.get("/v1/papers/slo/alerts/quality-score?days=7&tenant_id=tenant-a")
        assert quality_score.status_code == 200
        quality_score_body = quality_score.json()
        assert quality_score_body["tenant_id"] == "tenant-a"
        assert 0 <= quality_score_body["score"] <= 100

        strategy_tune = client.post("/v1/papers/slo/alerts/strategy-tune?days=7&tenant_id=tenant-a")
        assert strategy_tune.status_code == 200
        strategy_tune_body = strategy_tune.json()
        assert strategy_tune_body["tenant_id"] == "tenant-a"
        assert "reasons" in strategy_tune_body

        strategy_experiment = client.get(
            "/v1/papers/slo/alerts/strategy-experiments"
            "?days=7&tenant_id=tenant-a&candidate_max_open_degraded_alerts=3"
        )
        assert strategy_experiment.status_code == 200
        strategy_experiment_body = strategy_experiment.json()
        assert strategy_experiment_body["tenant_id"] == "tenant-a"
        assert "guardrail_passed" in strategy_experiment_body
        assert "recommend_promote_candidate" in strategy_experiment_body
        assert isinstance(strategy_experiment_body["reasons"], list)

        strategy_experiment_run = client.post(
            "/v1/papers/slo/alerts/strategy-experiments/run"
            "?days=7&tenant_id=tenant-a&candidate_max_open_degraded_alerts=2"
        )
        assert strategy_experiment_run.status_code == 200
        strategy_experiment_run_body = strategy_experiment_run.json()
        assert strategy_experiment_run_body["tenant_id"] == "tenant-a"
        assert "experiment_id" in strategy_experiment_run_body

        strategy_experiment_dashboard = client.get(
            "/v1/papers/slo/alerts/strategy-experiments/dashboard?days=7&tenant_id=tenant-a"
        )
        assert strategy_experiment_dashboard.status_code == 200
        strategy_experiment_dashboard_body = strategy_experiment_dashboard.json()
        assert strategy_experiment_dashboard_body["tenant_id"] == "tenant-a"
        assert strategy_experiment_dashboard_body["total_experiments"] >= 1
        assert isinstance(strategy_experiment_dashboard_body["recent_experiments"], list)

        strategy_replay = client.post("/v1/papers/slo/alerts/strategy-experiments/auto-replay?days=7&tenant_id=tenant-a")
        assert strategy_replay.status_code == 200
        strategy_replay_body = strategy_replay.json()
        assert strategy_replay_body["tenant_id"] == "tenant-a"
        assert "recommended_canary_ratio" in strategy_replay_body

        canary_status = client.get("/v1/papers/slo/alerts/strategy-canary/status?days=7&tenant_id=tenant-a")
        assert canary_status.status_code == 200
        canary_status_body = canary_status.json()
        assert canary_status_body["tenant_id"] == "tenant-a"
        assert "canary_recommended" in canary_status_body

        disable_canary = client.post("/v1/papers/slo/alerts/strategy-canary/toggle?tenant_id=tenant-a&enabled=false")
        assert disable_canary.status_code == 200
        disable_body = disable_canary.json()
        assert disable_body["canary_enabled"] is False

        canary_status_after_disable = client.get("/v1/papers/slo/alerts/strategy-canary/status?days=7&tenant_id=tenant-a")
        assert canary_status_after_disable.status_code == 200
        canary_status_after_disable_body = canary_status_after_disable.json()
        assert canary_status_after_disable_body["canary_enabled"] is False

        enable_canary = client.post("/v1/papers/slo/alerts/strategy-canary/toggle?tenant_id=tenant-a&enabled=true")
        assert enable_canary.status_code == 200
        enable_body = enable_canary.json()
        assert enable_body["canary_enabled"] is True

        readiness = client.get("/v1/papers/demo/readiness")
        assert readiness.status_code == 200
        readiness_body = readiness.json()
        assert "overall_ready" in readiness_body
        assert "evidence" in readiness_body

        rehearsal = client.post("/v1/papers/demo/rehearsal?days=7&tenant_id=tenant-a")
        assert rehearsal.status_code == 200
        rehearsal_body = rehearsal.json()
        assert "checks" in rehearsal_body
        assert rehearsal_body["duration_ms"] >= 0

        final_report = client.post("/v1/papers/demo/final-report?days=7&tenant_id=tenant-a")
        assert final_report.status_code == 200
        final_report_body = final_report.json()
        assert "release_recommended" in final_report_body
        assert "release_notes" in final_report_body

        post_release_monitor = client.get("/v1/papers/demo/post-release-monitor?days=7&tenant_id=tenant-a")
        assert post_release_monitor.status_code == 200
        post_release_monitor_body = post_release_monitor.json()
        assert "risk_level" in post_release_monitor_body
        assert "checks" in post_release_monitor_body

        rollback_advice = client.get("/v1/papers/demo/rollback-advice?days=7&tenant_id=tenant-a")
        assert rollback_advice.status_code == 200
        rollback_advice_body = rollback_advice.json()
        assert "should_rollback" in rollback_advice_body
        assert "reasons" in rollback_advice_body

        ops_scorecard = client.get("/v1/papers/demo/ops-scorecard?days=7&tenant_id=tenant-a")
        assert ops_scorecard.status_code == 200
        ops_scorecard_body = ops_scorecard.json()
        assert "operations_score" in ops_scorecard_body
        assert "grade" in ops_scorecard_body

        release_gate = client.get("/v1/papers/demo/release-gate?days=7&tenant_id=tenant-a&target_env=staging")
        assert release_gate.status_code == 200
        release_gate_body = release_gate.json()
        assert "gate_passed" in release_gate_body
        assert "reasons" in release_gate_body

        release_plan = client.post("/v1/papers/demo/release-plan?days=7&tenant_id=tenant-a&target_env=staging")
        assert release_plan.status_code == 200
        release_plan_body = release_plan.json()
        assert "steps" in release_plan_body
        assert "blocker_reasons" in release_plan_body

        roadmap_status = client.get("/v1/papers/demo/roadmap-status")
        assert roadmap_status.status_code == 200
        roadmap_status_body = roadmap_status.json()
        assert roadmap_status_body["current_day"] >= 1
        assert isinstance(roadmap_status_body["next_actions"], list)

        cicd_webhook = client.post("/v1/papers/demo/cicd/webhook?days=7&tenant_id=tenant-a&target_env=staging")
        assert cicd_webhook.status_code == 200
        cicd_webhook_body = cicd_webhook.json()
        assert "pipeline_id" in cicd_webhook_body
        assert "accepted" in cicd_webhook_body

        acceptance_gate = client.post(
            "/v1/papers/demo/cicd/acceptance-gate?days=7&tenant_id=tenant-a&target_env=staging"
        )
        assert acceptance_gate.status_code == 200
        acceptance_gate_body = acceptance_gate.json()
        assert "gate_passed" in acceptance_gate_body
        assert "failed_checks" in acceptance_gate_body

        rollout_runbook = client.get("/v1/papers/demo/rollout-runbook?days=7&tenant_id=tenant-a&target_env=production")
        assert rollout_runbook.status_code == 200
        rollout_runbook_body = rollout_runbook.json()
        assert "steps" in rollout_runbook_body
        assert "rollback_plan" in rollout_runbook_body

        operations_audit = client.get("/v1/papers/demo/operations-audit?days=7&tenant_id=tenant-a&target_env=production")
        assert operations_audit.status_code == 200
        operations_audit_body = operations_audit.json()
        assert "passed" in operations_audit_body
        assert "missing_controls" in operations_audit_body

        approval_request = client.post(
            "/v1/papers/demo/release-approvals/request?target_env=production&requested_by=qa&note=ready"
        )
        assert approval_request.status_code == 200
        approval_request_body = approval_request.json()
        assert approval_request_body["status"] in {"pending", "auto_approved"}
        approval_id = approval_request_body["approval_id"]

        approval_decision = client.post(
            f"/v1/papers/demo/release-approvals/{approval_id}/decision?approved=true&note=looks_good"
        )
        assert approval_decision.status_code == 200
        approval_decision_body = approval_decision.json()
        assert approval_decision_body["status"] == "approved"

        approvals_list = client.get("/v1/papers/demo/release-approvals?limit=10&offset=0")
        assert approvals_list.status_code == 200
        approvals_list_body = approvals_list.json()
        assert approvals_list_body["items"]

        approval_sync = client.post(f"/v1/papers/demo/release-approvals/{approval_id}/sync")
        assert approval_sync.status_code == 200
        approval_sync_body = approval_sync.json()
        assert approval_sync_body["synced"] is True
        assert approval_sync_body["sync_target"]

        audit_report = client.get("/v1/papers/demo/audit-report?days=7&tenant_id=tenant-a&target_env=production")
        assert audit_report.status_code == 200
        audit_report_body = audit_report.json()
        assert "report_status" in audit_report_body
        assert "approval_sync_rate" in audit_report_body

        generated_report = client.post(
            "/v1/papers/demo/audit-report/generate?days=7&tenant_id=tenant-a&target_env=production"
        )
        assert generated_report.status_code == 200
        generated_report_body = generated_report.json()
        assert generated_report_body["report_id"]
        assert generated_report_body["tenant_id"] == "tenant-a"

        audit_report_history = client.get(
            "/v1/papers/demo/audit-report/history?limit=10&offset=0&target_env=production&tenant_id=tenant-a"
        )
        assert audit_report_history.status_code == 200
        audit_report_history_body = audit_report_history.json()
        assert audit_report_history_body["items"]

        audit_report_history_csv = client.get(
            "/v1/papers/demo/audit-report/history/export.csv?target_env=production&tenant_id=tenant-a"
        )
        assert audit_report_history_csv.status_code == 200
        assert audit_report_history_csv.headers["content-type"].startswith("text/csv")
        assert "report_id" in audit_report_history_csv.text

        audit_report_trend = client.get("/v1/papers/demo/audit-report/trend?days=30&target_env=production&tenant_id=tenant-a")
        assert audit_report_trend.status_code == 200
        audit_report_trend_body = audit_report_trend.json()
        assert "points" in audit_report_trend_body

        audit_report_trend_summary = client.get(
            "/v1/papers/demo/audit-report/trend/summary?days=30&target_env=production&tenant_id=tenant-a"
        )
        assert audit_report_trend_summary.status_code == 200
        audit_report_trend_summary_body = audit_report_trend_summary.json()
        assert "status" in audit_report_trend_summary_body

        audit_report_trend_notify = client.post(
            "/v1/papers/demo/audit-report/trend/summary/notify?days=30&target_env=production&tenant_id=tenant-a"
        )
        assert audit_report_trend_notify.status_code == 200
        audit_report_trend_notify_body = audit_report_trend_notify.json()
        assert audit_report_trend_notify_body["sent"] is True
        assert audit_report_trend_notify_body["channel"]

        audit_report_trend_notifications = client.get("/v1/papers/demo/audit-report/trend/notifications?limit=10&offset=0")
        assert audit_report_trend_notifications.status_code == 200
        audit_report_trend_notifications_body = audit_report_trend_notifications.json()
        assert audit_report_trend_notifications_body["items"]
        notification_id = audit_report_trend_notifications_body["items"][0]["notification_id"]

        replay_notification = client.post(
            f"/v1/papers/demo/audit-report/trend/notifications/{notification_id}/replay"
        )
        assert replay_notification.status_code == 200
        replay_notification_body = replay_notification.json()
        assert replay_notification_body["replayed"] is True

        replay_failed_notifications = client.post("/v1/papers/demo/audit-report/trend/notifications/replay-failed?limit=10")
        assert replay_failed_notifications.status_code == 200
        replay_failed_notifications_body = replay_failed_notifications.json()
        assert "replayed_count" in replay_failed_notifications_body

        replay_plan = client.get("/v1/papers/demo/audit-report/trend/notifications/replay-plan")
        assert replay_plan.status_code == 200
        replay_plan_body = replay_plan.json()
        assert "recommended_batch_size" in replay_plan_body

        replay_run = client.post("/v1/papers/demo/audit-report/trend/notifications/replay-run?limit=10")
        assert replay_run.status_code == 200
        replay_run_body = replay_run.json()
        assert "replayed_count" in replay_run_body

        notification_metrics = client.get("/v1/papers/demo/audit-report/trend/notifications/metrics")
        assert notification_metrics.status_code == 200
        notification_metrics_body = notification_metrics.json()
        assert "success_rate" in notification_metrics_body

        notification_drill = client.post("/v1/papers/demo/audit-report/trend/notifications/drill?failures=2&auto_replay=true")
        assert notification_drill.status_code == 200
        notification_drill_body = notification_drill.json()
        assert notification_drill_body["created_failures"] == 2

        notification_drills = client.get("/v1/papers/demo/audit-report/trend/notifications/drills?limit=10&offset=0")
        assert notification_drills.status_code == 200
        notification_drills_body = notification_drills.json()
        assert notification_drills_body["items"]

        notification_drills_summary = client.get("/v1/papers/demo/audit-report/trend/notifications/drills/summary")
        assert notification_drills_summary.status_code == 200
        notification_drills_summary_body = notification_drills_summary.json()
        assert "auto_replay_rate" in notification_drills_summary_body

        notification_drills_export = client.get("/v1/papers/demo/audit-report/trend/notifications/drills/export.csv")
        assert notification_drills_export.status_code == 200
        assert notification_drills_export.headers["content-type"].startswith("text/csv")
        assert "drill_id" in notification_drills_export.text

        notification_drills_report = client.get("/v1/papers/demo/audit-report/trend/notifications/drills/report")
        assert notification_drills_report.status_code == 200
        notification_drills_report_body = notification_drills_report.json()
        assert "recommendations" in notification_drills_report_body

        create_drill_report_snapshot = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots"
        )
        assert create_drill_report_snapshot.status_code == 200
        create_drill_report_snapshot_body = create_drill_report_snapshot.json()
        assert create_drill_report_snapshot_body["total_drills"] >= 1
        assert "snapshot_id" in create_drill_report_snapshot_body
        first_snapshot_id = create_drill_report_snapshot_body["snapshot_id"]

        second_notification_drill = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drill?failures=1&auto_replay=true"
        )
        assert second_notification_drill.status_code == 200

        create_second_drill_report_snapshot = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots"
        )
        assert create_second_drill_report_snapshot.status_code == 200
        second_snapshot_id = create_second_drill_report_snapshot.json()["snapshot_id"]

        list_drill_report_snapshots = client.get(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots?limit=10&offset=0"
        )
        assert list_drill_report_snapshots.status_code == 200
        list_drill_report_snapshots_body = list_drill_report_snapshots.json()
        assert len(list_drill_report_snapshots_body["items"]) >= 1

        export_drill_report_snapshots = client.get(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/export.csv?limit=10&offset=0"
        )
        assert export_drill_report_snapshots.status_code == 200
        assert export_drill_report_snapshots.headers["content-type"].startswith("text/csv")
        assert "snapshot_id" in export_drill_report_snapshots.text

        get_drill_report_snapshot = client.get(
            f"/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/{first_snapshot_id}"
        )
        assert get_drill_report_snapshot.status_code == 200
        assert get_drill_report_snapshot.json()["snapshot_id"] == first_snapshot_id

        compare_drill_report_snapshots = client.get(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/compare"
            f"?snapshot_id_a={first_snapshot_id}&snapshot_id_b={second_snapshot_id}"
        )
        assert compare_drill_report_snapshots.status_code == 200
        compare_drill_report_snapshots_body = compare_drill_report_snapshots.json()
        assert compare_drill_report_snapshots_body["trend"] in {"improved", "regressed", "stable"}

        drill_report_snapshot_retention_plan = client.get(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-plan?keep=1"
        )
        assert drill_report_snapshot_retention_plan.status_code == 200
        drill_report_snapshot_retention_plan_body = drill_report_snapshot_retention_plan.json()
        assert drill_report_snapshot_retention_plan_body["keep"] == 1
        assert drill_report_snapshot_retention_plan_body["would_delete"] >= 1

        drill_report_snapshot_retention_run_preview = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-run?keep=1&dry_run=true"
        )
        assert drill_report_snapshot_retention_run_preview.status_code == 200
        drill_report_snapshot_retention_run_preview_body = drill_report_snapshot_retention_run_preview.json()
        assert drill_report_snapshot_retention_run_preview_body["executed"] is False
        assert drill_report_snapshot_retention_run_preview_body["deleted_snapshots"] >= 1

        cleanup_drill_report_snapshots = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/cleanup?keep=1"
        )
        assert cleanup_drill_report_snapshots.status_code == 200
        cleanup_drill_report_snapshots_body = cleanup_drill_report_snapshots.json()
        assert cleanup_drill_report_snapshots_body["kept_snapshots"] == 1
        assert cleanup_drill_report_snapshots_body["deleted_snapshots"] >= 0

        drill_report_snapshot_retention_run = client.post(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-run?keep=1&dry_run=false"
        )
        assert drill_report_snapshot_retention_run.status_code == 200
        drill_report_snapshot_retention_run_body = drill_report_snapshot_retention_run.json()
        assert drill_report_snapshot_retention_run_body["executed"] is True
        assert drill_report_snapshot_retention_run_body["kept_snapshots"] == 1

        drill_report_snapshot_retention_runs = client.get(
            "/v1/papers/demo/audit-report/trend/notifications/drills/report/snapshots/retention-runs?limit=10&offset=0"
        )
        assert drill_report_snapshot_retention_runs.status_code == 200
        drill_report_snapshot_retention_runs_body = drill_report_snapshot_retention_runs.json()
        assert len(drill_report_snapshot_retention_runs_body["items"]) >= 2
    finally:
        PaperService.get_stats = original_get_stats


def test_top_task_insights_aggregates_across_all_pages():
    original_count_runs = PaperService.count_runs
    original_list_runs = PaperService.list_runs
    calls: list[tuple[int, int]] = []
    total_runs = 5205

    def fake_count_runs(self, **kwargs):
        return total_runs

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        calls.append((offset, limit))
        if offset >= total_runs:
            return []
        end = min(offset + limit, total_runs)
        runs = []
        for idx in range(offset, end):
            task = "task-major" if idx < 5050 else "task-minor"
            runs.append(
                SimpleNamespace(
                    task=task,
                    quality_score=9 if task == "task-major" else 4,
                    research_sources=[{"title": "source"}] if task == "task-major" else [],
                )
            )
        return runs

    try:
        PaperService.count_runs = fake_count_runs
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/top-tasks?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total_tasks"] == 2
        assert body["items"][0]["task"] == "task-major"
        assert body["items"][0]["run_count"] == 5050
        assert body["items"][1]["task"] == "task-minor"
        assert body["items"][1]["run_count"] == 155
        assert any(offset >= 5000 for offset, _ in calls)
    finally:
        PaperService.count_runs = original_count_runs
        PaperService.list_runs = original_list_runs


def test_run_insights_metrics_aggregates_across_all_pages():
    original_count_runs = PaperService.count_runs
    original_list_runs = PaperService.list_runs
    calls: list[tuple[int, int]] = []
    total_runs = 5205

    def fake_count_runs(self, **kwargs):
        return total_runs

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        calls.append((offset, limit))
        if offset >= total_runs:
            return []
        end = min(offset + limit, total_runs)
        runs = []
        for idx in range(offset, end):
            if idx < 5000:
                quality_score = 10
                research_sources = [{"title": "s1"}, {"title": "s2"}]
                review_report = {"revision_plan": ["a", "b", "c"]}
                draft = "Body [1] [2]"
            else:
                quality_score = 2
                research_sources = []
                review_report = None
                draft = "Body"
            runs.append(
                SimpleNamespace(
                    run_id=f"run-{idx}",
                    task="metrics",
                    outline="o",
                    draft=draft,
                    review="r",
                    quality_score=quality_score,
                    stop_reason="max_iterations",
                    created_at="2026-01-01T00:00:00+00:00",
                    duration_ms=1000,
                    research_sources=research_sources,
                    review_report=review_report,
                    parent_run_id="",
                    root_run_id=f"run-{idx}",
                    revision_notes="",
                )
            )
        return runs

    try:
        PaperService.count_runs = fake_count_runs
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/metrics")
        assert response.status_code == 200
        body = response.json()
        assert body["total_runs"] == 5205
        assert body["runs_with_review_report"] == 5000
        assert round(body["avg_source_count"], 4) == round((5000 * 2) / 5205, 4)
        assert round(body["avg_inline_citation_count"], 4) == round((5000 * 2) / 5205, 4)
        assert round(body["avg_revision_plan_items"], 4) == round((5000 * 3) / 5205, 4)
        assert any(offset >= 5000 for offset, _ in calls)
    finally:
        PaperService.count_runs = original_count_runs
        PaperService.list_runs = original_list_runs


def test_top_task_insights_does_not_require_count_query():
    original_count_runs = PaperService.count_runs
    original_list_runs = PaperService.list_runs

    def fail_count_runs(self, **kwargs):
        raise AssertionError("count_runs should not be called for top-task aggregation pagination")

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        if offset > 0:
            return []
        return [
            SimpleNamespace(task="task-a", quality_score=8, research_sources=[{"title": "s1"}]),
            SimpleNamespace(task="task-a", quality_score=6, research_sources=[{"title": "s2"}]),
            SimpleNamespace(task="task-b", quality_score=9, research_sources=[]),
        ]

    try:
        PaperService.count_runs = fail_count_runs
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/top-tasks?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total_tasks"] == 2
        assert body["items"][0]["task"] == "task-a"
        assert body["items"][0]["run_count"] == 2
        assert body["items"][0]["avg_quality_score"] == 7.0
        assert body["items"][1]["task"] == "task-b"
    finally:
        PaperService.count_runs = original_count_runs
        PaperService.list_runs = original_list_runs


def test_run_insights_metrics_uses_single_count_query():
    original_count_runs = PaperService.count_runs
    original_list_runs = PaperService.list_runs
    counter = {"count_calls": 0}

    def fake_count_runs(self, **kwargs):
        counter["count_calls"] += 1
        return 3

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        if offset > 0:
            return []
        return [
            SimpleNamespace(
                run_id="r1",
                task="task-a",
                outline="o",
                draft="Body [1]",
                review="r",
                quality_score=8,
                stop_reason="max_iterations",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=1000,
                research_sources=[{"title": "s1"}],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r1",
                revision_notes="",
            ),
            SimpleNamespace(
                run_id="r2",
                task="task-b",
                outline="o",
                draft="Body",
                review="r",
                quality_score=6,
                stop_reason="max_iterations",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=1000,
                research_sources=[],
                review_report=None,
                parent_run_id="",
                root_run_id="r2",
                revision_notes="",
            ),
            SimpleNamespace(
                run_id="r3",
                task="task-c",
                outline="o",
                draft="Body [1] [2]",
                review="r",
                quality_score=7,
                stop_reason="max_iterations",
                created_at="2026-01-01T00:00:00+00:00",
                duration_ms=1000,
                research_sources=[{"title": "s1"}, {"title": "s2"}],
                review_report={"revision_plan": ["a", "b"]},
                parent_run_id="",
                root_run_id="r3",
                revision_notes="",
            ),
        ]

    try:
        PaperService.count_runs = fake_count_runs
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/metrics")
        assert response.status_code == 200
        assert counter["count_calls"] == 1
    finally:
        PaperService.count_runs = original_count_runs
        PaperService.list_runs = original_list_runs


def test_idempotency_key_replay():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    payload = {"task": "AI agent framework", "outline": "Intro,Method", "iterations": 1}
    first = client.post("/v1/papers/generate", headers={"X-Idempotency-Key": "idem-1"}, json=payload)
    second = client.post("/v1/papers/generate", headers={"X-Idempotency-Key": "idem-1"}, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    b1 = first.json()
    b2 = second.json()
    assert b1["run_id"] == b2["run_id"]
    assert b1["idempotent_replay"] is False
    assert b2["idempotent_replay"] is True


def test_citation_audit_reports_missing_and_unused_markers():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id != "run-audit":
            return None
        return SimpleNamespace(
            run_id="run-audit",
            draft=(
                "# Draft\n\n"
                "Claim one [1]. Claim two [3].\n\n"
                "[References]\n"
                "[1] Source one.\n"
                "[2] Source two.\n"
            ),
        )

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/runs/run-audit/citation-audit")
        assert response.status_code == 200
        body = response.json()
        assert body["inline_markers"] == [1, 3]
        assert body["reference_markers"] == [1, 2]
        assert body["missing_reference_entries"] == [3]
        assert body["unused_reference_entries"] == [2]
        assert body["coverage_score"] == 0.3333
    finally:
        PaperService.get_run = original_get_run


def test_rewrite_section_rejects_missing_section():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id != "run-rewrite":
            return None
        return SimpleNamespace(
            run_id="run-rewrite",
            draft="# Draft\n\nNo markdown headings in this document.",
        )

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.post(
            "/v1/papers/runs/run-rewrite/rewrite-section",
            json={
                "section_title": "Conclusion",
                "rewrite_goal": "Tighten final takeaway and practical implications.",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "section not found in draft"
    finally:
        PaperService.get_run = original_get_run


def test_insights_trends_groups_by_week():
    original_list_runs = PaperService.list_runs

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        if offset > 0:
            return []
        return [
            SimpleNamespace(
                run_id="r1",
                task="t",
                outline="o",
                draft="Text [1]",
                review="r",
                quality_score=8,
                stop_reason="max_iterations",
                created_at="2026-01-05T00:00:00+00:00",  # Monday
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r1",
                revision_notes="",
            ),
            SimpleNamespace(
                run_id="r2",
                task="t",
                outline="o",
                draft="Text [1] [2]",
                review="r",
                quality_score=6,
                stop_reason="max_iterations",
                created_at="2026-01-06T00:00:00+00:00",  # same week
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r2",
                revision_notes="",
            ),
        ]

    try:
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/trends?interval=week")
        assert response.status_code == 200
        body = response.json()
        assert body["interval"] == "week"
        assert body["group_by"] == "all"
        assert len(body["points"]) == 1
        assert body["points"][0]["bucket_start"] == "2026-01-05"
        assert body["points"][0]["total_runs"] == 2
        assert body["points"][0]["avg_quality_score"] == 7.0
    finally:
        PaperService.list_runs = original_list_runs


def test_insights_trends_supports_group_by_task():
    original_list_runs = PaperService.list_runs

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        if offset > 0:
            return []
        return [
            SimpleNamespace(
                run_id="r1",
                task="task-a",
                outline="o",
                draft="Text [1]",
                review="r",
                quality_score=8,
                stop_reason="max_iterations",
                created_at="2026-01-05T00:00:00+00:00",
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r1",
                revision_notes="",
            ),
            SimpleNamespace(
                run_id="r2",
                task="task-b",
                outline="o",
                draft="Text [1]",
                review="r",
                quality_score=6,
                stop_reason="max_iterations",
                created_at="2026-01-05T00:00:00+00:00",
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r2",
                revision_notes="",
            ),
        ]

    try:
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/trends?interval=day&group_by=task")
        assert response.status_code == 200
        body = response.json()
        assert body["group_by"] == "task"
        keys = {point["group_key"] for point in body["points"]}
        assert keys == {"task-a", "task-b"}
    finally:
        PaperService.list_runs = original_list_runs


def test_insights_trends_supports_group_by_paper_type():
    original_list_runs = PaperService.list_runs

    def fake_list_runs(self, *, limit=20, offset=0, **kwargs):
        if offset > 0:
            return []
        return [
            SimpleNamespace(
                run_id="r1",
                task="task-a",
                outline="o",
                draft="Text [1]",
                review="r",
                quality_score=8,
                stop_reason="max_iterations",
                created_at="2026-01-05T00:00:00+00:00",
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r1",
                revision_notes="Paper Type: empirical",
            ),
            SimpleNamespace(
                run_id="r2",
                task="task-b",
                outline="o",
                draft="Text [1]",
                review="r",
                quality_score=6,
                stop_reason="max_iterations",
                created_at="2026-01-05T00:00:00+00:00",
                duration_ms=100,
                research_sources=[],
                review_report={"revision_plan": ["a"]},
                parent_run_id="",
                root_run_id="r2",
                revision_notes="",
            ),
        ]

    try:
        PaperService.list_runs = fake_list_runs
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/insights/trends?interval=day&group_by=paper_type")
        assert response.status_code == 200
        body = response.json()
        assert body["group_by"] == "paper_type"
        keys = {point["group_key"] for point in body["points"]}
        assert keys == {"empirical", "unknown"}
    finally:
        PaperService.list_runs = original_list_runs


def test_apply_revision_plan_rejects_empty_selection():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id != "run-plan":
            return None
        return SimpleNamespace(
            run_id="run-plan",
            draft="# Draft\n\n## Conclusion\nFinal notes.",
            review_report={"revision_plan": ["Improve conclusion focus"]},
        )

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.post(
            "/v1/papers/runs/run-plan/revision-plan/apply",
            json={"selected_items": ["   "], "mode": "patch"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "selected_items must not be empty"
    finally:
        PaperService.get_run = original_get_run


def test_run_diff_reports_no_change_for_identical_drafts():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id not in {"run-a", "run-b"}:
            return None
        return SimpleNamespace(run_id=run_id, draft="# Draft\n\nSame content.")

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/runs/run-a/diff", params={"against": "run-b"})
        assert response.status_code == 200
        body = response.json()
        assert body["changed"] is False
        assert body["added_lines"] == 0
        assert body["removed_lines"] == 0
        assert body["diff_preview"] == ""
    finally:
        PaperService.get_run = original_get_run


def test_references_endpoint_formats_styles():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id != "run-ref":
            return None
        return SimpleNamespace(
            run_id="run-ref",
            research_sources=[
                SimpleNamespace(citation_id=1, title="Source A", source_type="Academic paper", locator="DOI:10.1"),
            ],
        )

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        gbt = client.get("/v1/papers/runs/run-ref/references?style=gbt7714")
        assert gbt.status_code == 200
        assert "[A]" in gbt.json()["references"][0]
        apa = client.get("/v1/papers/runs/run-ref/references?style=apa")
        assert apa.status_code == 200
        assert "(Academic paper)" in apa.json()["references"][0]
    finally:
        PaperService.get_run = original_get_run


def test_quality_breakdown_uses_review_report_feedback():
    original_get_run = PaperService.get_run

    def fake_get_run(self, run_id: str):
        if run_id != "run-q":
            return None
        return SimpleNamespace(
            run_id="run-q",
            quality_score=7,
            review_report={
                "score": 8,
                "structure_feedback": "- Structure: aligned with outline and core academic sections are present.",
                "evidence_feedback": "- Evidence: partially grounded; strengthen claim-to-evidence links.",
                "citation_feedback": "- Citation: missing references section and inline citation support.",
                "language_feedback": "- Language: wording is clear; polish conciseness.",
                "revision_plan": ["Add references", "Tighten evidence links"],
            },
        )

    try:
        PaperService.get_run = fake_get_run
        app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
        client = TestClient(app)
        response = client.get("/v1/papers/runs/run-q/quality-breakdown")
        assert response.status_code == 200
        body = response.json()
        assert body["overall_score"] == 8
        assert body["structure_score"] > body["citation_score"]
        assert body["language_score"] >= 6
        assert body["recommendations"] == ["Add references", "Tighten evidence links"]
    finally:
        PaperService.get_run = original_get_run


def test_idempotency_key_rejects_different_payload():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    first = client.post(
        "/v1/papers/generate",
        headers={"X-Idempotency-Key": "idem-1"},
        json={"task": "AI agent framework", "outline": "Intro,Method", "iterations": 1},
    )
    second = client.post(
        "/v1/papers/generate",
        headers={"X-Idempotency-Key": "idem-1"},
        json={"task": "Different task", "outline": "Intro,Method", "iterations": 1},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json() == {"detail": "idempotency key already used for a different request"}


def test_api_key_protection_and_purge():
    app = create_app(
        Settings(
            app_env="test",
            memory_db_path=":memory:",
            run_db_path=":memory:",
            api_key="secret",
            run_retention_days=0,
        )
    )
    client = TestClient(app)

    no_key = client.post(
        "/v1/papers/generate",
        json={"task": "AI agent framework", "outline": "Intro,Method", "iterations": 1},
    )
    assert no_key.status_code == 401

    ok = client.post(
        "/v1/papers/generate",
        headers={"X-API-Key": "secret"},
        json={"task": "AI agent framework", "outline": "Intro,Method", "revision_notes": "Improve structure", "iterations": 1},
    )
    assert ok.status_code == 200

    purge_no_key = client.post("/v1/papers/maintenance/purge")
    assert purge_no_key.status_code == 401

    run_id = ok.json()["run_id"]
    markdown_no_key = client.get(f"/v1/papers/runs/{run_id}/draft.md")
    assert markdown_no_key.status_code == 401

    markdown_with_key = client.get(f"/v1/papers/runs/{run_id}/draft.md", headers={"X-API-Key": "secret"})
    assert markdown_with_key.status_code == 200

    save_no_key = client.post(
        f"/v1/papers/runs/{run_id}/save-edited",
        json={"draft": "x" * 30},
    )
    assert save_no_key.status_code == 401

    save_with_key = client.post(
        f"/v1/papers/runs/{run_id}/save-edited",
        headers={"X-API-Key": "secret"},
        json={"draft": "x" * 30, "review": "saved manually"},
    )
    assert save_with_key.status_code == 200
    assert save_with_key.json()["stop_reason"] == "manual_edit"

    purge_with_key = client.post("/v1/papers/maintenance/purge", headers={"X-API-Key": "secret"})
    assert purge_with_key.status_code == 200
    assert "deleted_runs" in purge_with_key.json()

    purge_with_override = client.post(
        "/v1/papers/maintenance/purge?retention_days=10",
        headers={"X-API-Key": "secret"},
    )
    assert purge_with_override.status_code == 200
    assert purge_with_override.json()["retention_days"] == 10


def test_rate_limit_on_generate_endpoint():
    app = create_app(
        Settings(
            app_env="test",
            memory_db_path=":memory:",
            run_db_path=":memory:",
            rate_limit_per_minute=1,
        )
    )
    client = TestClient(app)

    first = client.post(
        "/v1/papers/generate",
        json={"task": "AI agent framework", "outline": "Intro,Method", "iterations": 1},
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/papers/generate",
        json={"task": "AI agent framework", "outline": "Intro,Method", "iterations": 1},
    )
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"






def test_runs_list_supports_root_run_id_filter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    root = client.post(
        "/v1/papers/generate",
        json={"task": "Root chain task", "outline": "Intro,Method", "iterations": 1},
    )
    child = client.post(
        f"/v1/papers/runs/{root.json()['run_id']}/save-edited",
        json={"draft": root.json()["draft"] + "\n\n## Child\nChain child.", "review": "saved manually"},
    )
    grandchild = client.post(
        f"/v1/papers/runs/{child.json()['run_id']}/save-edited",
        json={"draft": child.json()["draft"] + "\n\n## Grandchild\nChain grandchild.", "review": "saved manually"},
    )
    other_root = client.post(
        "/v1/papers/generate",
        json={"task": "Other root task", "outline": "Intro,Method", "iterations": 1},
    )

    response = client.get(f"/v1/papers/runs?root_run_id={root.json()['run_id']}&limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert {item["run_id"] for item in body["items"]} == {root.json()["run_id"], child.json()["run_id"], grandchild.json()["run_id"]}
    assert all(item["root_run_id"] == root.json()["run_id"] for item in body["items"])

    metrics = client.get(f"/v1/papers/metrics?root_run_id={root.json()['run_id']}")
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] == 3

    export_response = client.get(
        f"/v1/papers/runs/export.csv?root_run_id={root.json()['run_id']}&fields=run_id,root_run_id,parent_run_id"
    )
    assert export_response.status_code == 200
    assert export_response.headers["x-export-root-run-id"] == root.json()["run_id"]
    assert root.json()["run_id"] in export_response.text
    assert other_root.json()["run_id"] not in export_response.text

def test_runs_list_supports_parent_run_id_filter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    root = client.post(
        "/v1/papers/generate",
        json={"task": "Root lineage task", "outline": "Intro,Method", "iterations": 1},
    )
    child = client.post(
        f"/v1/papers/runs/{root.json()['run_id']}/save-edited",
        json={"draft": root.json()["draft"] + "\n\n## Child\nLineage child.", "review": "saved manually"},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "Unrelated task", "outline": "Intro,Method", "iterations": 1},
    )

    response = client.get(f"/v1/papers/runs?parent_run_id={root.json()['run_id']}&limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["run_id"] for item in body["items"]] == [child.json()["run_id"]]
    assert body["items"][0]["parent_run_id"] == root.json()["run_id"]

    metrics = client.get(f"/v1/papers/metrics?parent_run_id={root.json()['run_id']}")
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] == 1

    export_response = client.get(
        f"/v1/papers/runs/export.csv?parent_run_id={root.json()['run_id']}&fields=run_id,parent_run_id,task"
    )
    assert export_response.status_code == 200
    assert "parent_run_id" in export_response.text.splitlines()[0]
    assert root.json()["run_id"] in export_response.text
    assert export_response.headers["x-export-parent-run-id"] == root.json()["run_id"]



def test_runs_list_supports_lineage_scope_filter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    root = client.post(
        "/v1/papers/generate",
        json={"task": "Scope root task", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        f"/v1/papers/runs/{root.json()['run_id']}/save-edited",
        json={"draft": root.json()["draft"] + "\n\n## Derived\nScope child.", "review": "saved manually"},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "Another root task", "outline": "Intro,Method", "iterations": 1},
    )

    root_runs = client.get("/v1/papers/runs", params={"lineage_scope": "root", "limit": 10, "offset": 0})
    assert root_runs.status_code == 200
    root_body = root_runs.json()
    assert root_body["total"] >= 2
    assert all(item["parent_run_id"] == "" for item in root_body["items"])

    derived_runs = client.get("/v1/papers/runs", params={"lineage_scope": "derived", "limit": 10, "offset": 0})
    assert derived_runs.status_code == 200
    derived_body = derived_runs.json()
    assert derived_body["total"] >= 1
    assert all(item["parent_run_id"] != "" for item in derived_body["items"])

    metrics = client.get("/v1/papers/metrics", params={"lineage_scope": "derived"})
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] >= 1

    export_response = client.get("/v1/papers/runs/export.csv", params={"lineage_scope": "derived", "limit": 10})
    assert export_response.status_code == 200
    assert export_response.headers["x-export-lineage-scope"] == "derived"

def test_runs_list_supports_stop_reason_and_query_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    first = client.post(
        "/v1/papers/generate",
        json={"task": "Graph agents for paper writing", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "RAG memory design", "outline": "Intro,Method", "iterations": 2},
    )

    by_query = client.get("/v1/papers/runs?q=graph&limit=10&offset=0")
    assert by_query.status_code == 200
    query_body = by_query.json()
    assert query_body["total"] >= 1
    assert all("graph" in item["task"].lower() for item in query_body["items"])

    stop_reason = first.json()["stop_reason"]
    by_reason = client.get(f"/v1/papers/runs?stop_reason={stop_reason}&limit=10&offset=0")
    assert by_reason.status_code == 200
    reason_body = by_reason.json()
    assert reason_body["total"] >= 1
    assert all(item["stop_reason"] == stop_reason for item in reason_body["items"])


def test_runs_list_supports_time_range_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    first = client.post(
        "/v1/papers/generate",
        json={"task": "First timed run", "outline": "Intro,Method", "iterations": 1},
    )
    second = client.post(
        "/v1/papers/generate",
        json={"task": "Second timed run", "outline": "Intro,Method", "iterations": 1},
    )

    first_created = first.json()["created_at"]
    second_created = second.json()["created_at"]

    after_first = client.get(
        "/v1/papers/runs",
        params={"created_after": first_created, "limit": 10, "offset": 0},
    )
    assert after_first.status_code == 200
    after_body = after_first.json()
    assert all(item["run_id"] != first.json()["run_id"] for item in after_body["items"])

    before_second = client.get(
        "/v1/papers/runs",
        params={"created_before": second_created, "limit": 10, "offset": 0},
    )
    assert before_second.status_code == 200
    before_body = before_second.json()
    assert any(item["run_id"] == first.json()["run_id"] for item in before_body["items"])


def test_runs_list_rejects_invalid_time_window():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get(
        "/v1/papers/runs",
        params={
            "created_after": "2026-01-01T00:00:00+00:00",
            "created_before": "2025-01-01T00:00:00+00:00",
        },
    )
    assert resp.status_code == 422
    assert "created_after" in resp.json()["detail"]


def test_runs_list_supports_quality_score_range_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    first = client.post(
        "/v1/papers/generate",
        json={"task": "Quality low bound", "outline": "Intro,Method", "iterations": 1},
    )
    second = client.post(
        "/v1/papers/generate",
        json={"task": "Quality high bound", "outline": "Intro,Method", "iterations": 2},
    )

    first_score = first.json()["quality_score"]
    second_score = second.json()["quality_score"]
    min_score = min(first_score, second_score)
    max_score = max(first_score, second_score)

    ranged = client.get(
        "/v1/papers/runs",
        params={"min_quality_score": min_score, "max_quality_score": max_score, "limit": 10, "offset": 0},
    )
    assert ranged.status_code == 200
    body = ranged.json()
    assert body["total"] >= 2
    assert all(min_score <= item["quality_score"] <= max_score for item in body["items"])


def test_runs_list_rejects_invalid_quality_score_range():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get(
        "/v1/papers/runs",
        params={"min_quality_score": 9, "max_quality_score": 3},
    )
    assert resp.status_code == 422
    assert "min_quality_score" in resp.json()["detail"]


def test_runs_list_supports_sorting_by_quality_score():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "Sort run one", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "Sort run two", "outline": "Intro,Method", "iterations": 2},
    )

    desc_resp = client.get(
        "/v1/papers/runs",
        params={"sort_by": "quality_score", "sort_order": "desc", "limit": 10, "offset": 0},
    )
    assert desc_resp.status_code == 200
    desc_scores = [item["quality_score"] for item in desc_resp.json()["items"]]
    assert desc_scores == sorted(desc_scores, reverse=True)

    asc_resp = client.get(
        "/v1/papers/runs",
        params={"sort_by": "quality_score", "sort_order": "asc", "limit": 10, "offset": 0},
    )
    assert asc_resp.status_code == 200
    asc_scores = [item["quality_score"] for item in asc_resp.json()["items"]]
    assert asc_scores == sorted(asc_scores)


def test_metrics_supports_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    r1 = client.post(
        "/v1/papers/generate",
        json={"task": "metrics graph task", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "other task", "outline": "Intro,Method", "iterations": 2},
    )

    target_stop_reason = r1.json()["stop_reason"]

    filtered = client.get(
        "/v1/papers/metrics",
        params={"q": "graph", "stop_reason": target_stop_reason},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total_runs"] >= 1
    assert set(body["stop_reason_counts"].keys()) <= {target_stop_reason}


def test_metrics_rejects_invalid_filter_windows():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    bad_time = client.get(
        "/v1/papers/metrics",
        params={
            "created_after": "2026-01-01T00:00:00+00:00",
            "created_before": "2025-01-01T00:00:00+00:00",
        },
    )
    assert bad_time.status_code == 422

    bad_quality = client.get("/v1/papers/metrics", params={"min_quality_score": 9, "max_quality_score": 3})
    assert bad_quality.status_code == 422


def test_runs_list_supports_duration_range_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "Duration run one", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "Duration run two", "outline": "Intro,Method", "iterations": 2},
    )

    ranged = client.get(
        "/v1/papers/runs",
        params={"min_duration_ms": 0, "max_duration_ms": 100000, "limit": 10, "offset": 0},
    )
    assert ranged.status_code == 200
    body = ranged.json()
    assert body["total"] >= 2
    assert all(0 <= item["duration_ms"] <= 100000 for item in body["items"])


def test_runs_list_rejects_invalid_duration_range():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs", params={"min_duration_ms": 100, "max_duration_ms": 10})
    assert resp.status_code == 422
    assert "min_duration_ms" in resp.json()["detail"]


def test_metrics_supports_duration_filters():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "metrics duration one", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get("/v1/papers/metrics", params={"min_duration_ms": 0, "max_duration_ms": 100000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_runs"] >= 1


def test_metrics_rejects_invalid_duration_range():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/metrics", params={"min_duration_ms": 100, "max_duration_ms": 10})
    assert resp.status_code == 422
    assert "min_duration_ms" in resp.json()["detail"]


def test_runs_export_csv_endpoint():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "export graph run", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "export other run", "outline": "Intro,Method", "iterations": 2},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"sort_by": "created_at", "sort_order": "desc", "limit": 1, "offset": 0},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=runs_export.csv" == resp.headers["content-disposition"]
    assert resp.headers["x-export-limit"] == "1"
    assert resp.headers["x-export-offset"] == "0"
    assert resp.headers["x-export-returned"] == "1"
    assert resp.headers["x-export-has-data"] == "true"
    assert resp.headers["x-export-offset-end"] == "1"
    assert resp.headers["x-export-remaining"] == "1"
    assert resp.headers["x-export-limit-reached"] == "true"
    assert resp.headers["x-export-page-index"] == "1"
    assert int(resp.headers["x-export-total-pages"]) >= 2
    assert resp.headers["x-export-next-page-index"] == "2"
    assert resp.headers["x-export-is-last-page"] == "false"
    assert int(resp.headers["x-export-total"]) >= 2
    assert resp.headers["x-export-has-more"] == "true"
    assert resp.headers["x-export-next-offset"] == "1"
    assert resp.headers["x-export-has-filters"] == "false"
    assert resp.headers["x-export-filter-count"] == "0"
    assert resp.headers["x-export-filter-keys"] == ""
    assert resp.headers["x-export-delimiter"] == "comma"
    assert resp.headers["x-export-quote-all"] == "false"
    assert resp.headers["x-export-quote-char"] == "double"
    assert resp.headers["x-export-include-header"] == "true"
    assert resp.headers["x-export-line-ending"] == "lf"
    assert resp.headers["x-export-null-value"] == ""
    assert resp.headers["x-export-trim-strings"] == "false"
    assert resp.headers["x-export-empty-as-null"] == "false"
    assert resp.headers["x-export-sanitize-cells"] == "true"
    assert resp.headers["x-export-include-bom"] == "false"
    assert resp.headers["x-export-compressed"] == "false"
    assert resp.headers["x-export-fields"] == "run_id,task,quality_score,stop_reason,iterations_used,duration_ms,created_at"
    assert resp.headers["x-export-field-count"] == "7"
    assert resp.headers["x-export-default-fields"] == "true"
    assert resp.headers["x-export-sort-by"] == "created_at"
    assert resp.headers["x-export-sort-order"] == "desc"
    assert resp.headers["x-export-stop-reason"] == ""
    assert resp.headers["x-export-query"] == ""
    assert resp.headers["x-export-created-after"] == ""
    assert resp.headers["x-export-created-before"] == ""
    assert resp.headers["x-export-min-quality-score"] == ""
    assert resp.headers["x-export-max-quality-score"] == ""
    assert resp.headers["x-export-min-duration-ms"] == ""
    assert resp.headers["x-export-max-duration-ms"] == ""
    assert resp.headers["x-export-escape-style"] == "double"
    assert resp.headers["x-export-max-cell-length"] == ""
    assert "x-export-generated-at" in resp.headers

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "run_id,task,quality_score,stop_reason,iterations_used,duration_ms,created_at"
    assert len(lines) == 2
    assert "export other run" in lines[1]

    resp_offset = client.get(
        "/v1/papers/runs/export.csv",
        params={"sort_by": "created_at", "sort_order": "desc", "limit": 1, "offset": 1},
    )
    assert resp_offset.status_code == 200
    assert resp_offset.headers["x-export-offset"] == "1"
    assert resp_offset.headers["x-export-offset-end"] == "2"
    assert resp_offset.headers["x-export-remaining"] == "0"
    assert resp_offset.headers["x-export-limit-reached"] == "true"
    assert resp_offset.headers["x-export-page-index"] == "2"
    assert int(resp_offset.headers["x-export-total-pages"]) >= 2
    assert resp_offset.headers["x-export-next-page-index"] == ""
    assert resp_offset.headers["x-export-is-last-page"] == "true"
    assert resp_offset.headers["x-export-has-more"] == "false"
    assert resp_offset.headers["x-export-next-offset"] == ""
    offset_lines = [line for line in resp_offset.text.strip().splitlines() if line]
    assert len(offset_lines) == 2
    assert "export graph run" in offset_lines[1]


def test_runs_export_csv_route_precedence_over_run_detail():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "route precedence task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get("/v1/papers/runs/export.csv", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_modular_routes_register_core_paths():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    route_paths = {route.path for route in app.routes}
    expected_paths = {
        "/v1/papers/generate",
        "/v1/papers/runs",
        "/v1/papers/runs/{run_id}",
        "/v1/papers/runs/export.csv",
        "/v1/papers/metrics",
        "/v1/papers/insights",
        "/v1/papers/insights/metrics",
        "/v1/papers/insights/trends",
        "/v1/papers/insights/top-tasks",
        "/v1/papers/runs/{run_id}/save-edited",
        "/v1/papers/runs/{run_id}/revision-plan",
        "/v1/papers/runs/{run_id}/rewrite-section",
    }
    assert expected_paths.issubset(route_paths)




def test_runs_export_csv_includes_filter_metadata_headers():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "filter header task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"stop_reason": "max_iterations", "q": "filter", "limit": 10, "offset": 0},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-stop-reason"] == "max_iterations"
    assert resp.headers["x-export-query"] == "filter"
    assert resp.headers["x-export-has-filters"] == "true"
    assert resp.headers["x-export-filter-count"] == "2"
    assert resp.headers["x-export-filter-keys"] == "stop_reason,q"
    assert resp.headers["x-export-created-after"] == ""
    assert resp.headers["x-export-created-before"] == ""



def test_runs_export_csv_includes_created_range_metadata_headers():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "created range task", "outline": "Intro,Method", "iterations": 1},
    )

    created_after = "2025-01-01T00:00:00+00:00"
    created_before = "2030-01-01T00:00:00+00:00"
    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"created_after": created_after, "created_before": created_before, "limit": 10, "offset": 0},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-created-after"] == created_after
    assert resp.headers["x-export-created-before"] == created_before
    assert resp.headers["x-export-has-filters"] == "true"
    assert resp.headers["x-export-filter-count"] == "2"
    assert resp.headers["x-export-filter-keys"] == "created_after,created_before"
    assert resp.headers["x-export-min-quality-score"] == ""
    assert resp.headers["x-export-max-quality-score"] == ""
    assert resp.headers["x-export-min-duration-ms"] == ""
    assert resp.headers["x-export-max-duration-ms"] == ""



def test_runs_export_csv_includes_quality_and_duration_range_metadata_headers():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "score duration range task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={
            "min_quality_score": 3,
            "max_quality_score": 9,
            "min_duration_ms": 0,
            "max_duration_ms": 5000,
            "limit": 10,
            "offset": 0,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-min-quality-score"] == "3"
    assert resp.headers["x-export-max-quality-score"] == "9"
    assert resp.headers["x-export-min-duration-ms"] == "0"
    assert resp.headers["x-export-max-duration-ms"] == "5000"
    assert resp.headers["x-export-filter-count"] == "4"
    assert resp.headers["x-export-filter-keys"] == "min_quality_score,max_quality_score,min_duration_ms,max_duration_ms"



def test_runs_export_csv_has_data_header_false_for_empty_dataset():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    assert resp.headers["x-export-returned"] == "0"
    assert resp.headers["x-export-has-data"] == "false"
    assert resp.headers["x-export-remaining"] == "0"

def test_runs_export_csv_rejects_invalid_duration_range():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"min_duration_ms": 100, "max_duration_ms": 10})
    assert resp.status_code == 422
    assert "min_duration_ms" in resp.json()["detail"]


def test_runs_list_supports_sorting_by_duration_ms():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "Duration sort one", "outline": "Intro,Method", "iterations": 1},
    )
    client.post(
        "/v1/papers/generate",
        json={"task": "Duration sort two", "outline": "Intro,Method", "iterations": 2},
    )

    desc_resp = client.get(
        "/v1/papers/runs",
        params={"sort_by": "duration_ms", "sort_order": "desc", "limit": 10, "offset": 0},
    )
    assert desc_resp.status_code == 200
    desc_values = [item["duration_ms"] for item in desc_resp.json()["items"]]
    assert desc_values == sorted(desc_values, reverse=True)

    csv_resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"sort_by": "duration_ms", "sort_order": "asc", "limit": 10, "offset": 0},
    )
    assert csv_resp.status_code == 200


def test_runs_export_csv_supports_field_selection():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "export selected fields", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={
            "fields": "run_id,quality_score,duration_ms",
            "sort_by": "duration_ms",
            "sort_order": "asc",
            "limit": 10,
            "offset": 0,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-limit-reached"] == "false"
    assert resp.headers["x-export-fields"] == "run_id,quality_score,duration_ms"
    assert resp.headers["x-export-field-count"] == "3"
    assert resp.headers["x-export-default-fields"] == "false"
    assert resp.headers["x-export-sort-by"] == "duration_ms"
    assert resp.headers["x-export-sort-order"] == "asc"
    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "run_id,quality_score,duration_ms"


def test_runs_export_csv_rejects_invalid_field_selection():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"fields": "run_id,unknown_col"})
    assert resp.status_code == 422
    assert "unsupported export fields" in resp.json()["detail"]


def test_runs_export_csv_supports_utf8_bom():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "导出中文任务", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get("/v1/papers/runs/export.csv", params={"include_bom": True, "limit": 10})
    assert resp.status_code == 200
    assert resp.headers["x-export-include-bom"] == "true"
    assert resp.headers["x-export-compressed"] == "false"
    assert resp.content.startswith("﻿".encode("utf-8"))


def test_runs_export_csv_supports_gzip_compression():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "gzip export task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get("/v1/papers/runs/export.csv", params={"compress": True, "limit": 10})
    assert resp.status_code == 200
    assert resp.headers["x-export-include-bom"] == "false"
    assert resp.headers["x-export-compressed"] == "true"
    assert resp.headers.get("content-encoding") is None
    assert "filename=runs_export.csv.gz" in (resp.headers.get("content-disposition") or "")
    assert resp.headers.get("content-type", "").startswith("application/gzip")

    body_bytes = resp.content
    assert body_bytes.startswith(b"\x1f\x8b")
    text = gzip.decompress(body_bytes).decode("utf-8")
    assert "run_id" in text
    assert "gzip export task" in text


def test_runs_export_csv_supports_gzip_with_bom():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "gzip bom task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"compress": True, "include_bom": True, "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-include-bom"] == "true"
    assert resp.headers["x-export-compressed"] == "true"
    body_bytes = resp.content
    assert body_bytes.startswith(b"\x1f\x8b")

    csv_bytes = gzip.decompress(body_bytes)
    assert csv_bytes.startswith("﻿".encode("utf-8"))
    text = csv_bytes.decode("utf-8")
    assert "run_id" in text
    assert "gzip bom task" in text


def test_runs_export_csv_sanitizes_formula_like_cells():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "=HYPERLINK(\"http://example.com\",\"x\")", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get("/v1/papers/runs/export.csv", params={"fields": "task", "limit": 10})
    assert resp.status_code == 200
    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "task"
    assert lines[1].startswith('"\'=HYPERLINK(')


def test_runs_export_csv_can_disable_formula_sanitization():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "=SUM(1,2)", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "task", "limit": 10, "sanitize_cells": False},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-sanitize-cells"] == "false"
    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "task"
    assert lines[1] == '"=SUM(1,2)"'


def test_runs_export_csv_supports_tab_delimiter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "tab delimiter task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "delimiter": "tab", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-delimiter"] == "tab"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "run_id	task"
    assert "	tab delimiter task" in lines[1]


def test_runs_export_csv_supports_semicolon_delimiter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "semicolon delimiter task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "delimiter": "semicolon", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-delimiter"] == "semicolon"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == "run_id;task"
    assert ";semicolon delimiter task" in lines[1]


def test_runs_export_csv_rejects_invalid_delimiter():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"delimiter": "colon"})
    assert resp.status_code == 422


def test_runs_export_csv_supports_quote_all():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "quote all task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "quote_all": True, "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-quote-all"] == "true"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == '"run_id","task"'
    assert '"quote all task"' in lines[1]


def test_runs_export_csv_can_skip_header_row():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "no header task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "include_header": False, "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-include-header"] == "false"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert len(lines) == 1
    assert "no header task" in lines[0]
    assert "run_id,task" not in lines[0]


def test_runs_export_csv_supports_crlf_line_ending():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "crlf task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "line_ending": "crlf", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-line-ending"] == "crlf"
    assert "\r\n" in resp.text


def test_runs_export_csv_rejects_invalid_line_ending():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"line_ending": "cr"})
    assert resp.status_code == 422


def test_runs_export_csv_supports_null_value_replacement():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    original_list_runs = PaperService.list_runs
    original_count_runs = PaperService.count_runs
    try:
        PaperService.list_runs = lambda self, **kwargs: [
            SimpleNamespace(
                run_id="manual-run",
                task=None,
                quality_score=8,
                stop_reason=None,
                iterations_used=1,
                duration_ms=12,
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        PaperService.count_runs = lambda self, **kwargs: 1

        resp = client.get(
            "/v1/papers/runs/export.csv",
            params={"fields": "task,stop_reason", "null_value": "NULL", "limit": 10},
        )
        assert resp.status_code == 200
        assert resp.headers["x-export-null-value"] == "NULL"
        lines = [line for line in resp.text.strip().splitlines() if line]
        assert lines[0] == "task,stop_reason"
        assert lines[1] == "NULL,NULL"
    finally:
        PaperService.list_runs = original_list_runs
        PaperService.count_runs = original_count_runs


def test_runs_export_csv_supports_single_quote_char():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": "quote char task", "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "run_id,task", "quote_all": True, "quote_char": "single", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-quote-char"] == "single"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0].startswith("'run_id','task'")


def test_runs_export_csv_rejects_invalid_quote_char():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"quote_char": "backtick"})
    assert resp.status_code == 422


def test_runs_export_csv_supports_trim_strings():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    original_list_runs = PaperService.list_runs
    original_count_runs = PaperService.count_runs
    try:
        PaperService.list_runs = lambda self, **kwargs: [
            SimpleNamespace(
                run_id="trim-run",
                task="  padded task  ",
                quality_score=8,
                stop_reason="  good  ",
                iterations_used=1,
                duration_ms=12,
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        PaperService.count_runs = lambda self, **kwargs: 1

        resp = client.get(
            "/v1/papers/runs/export.csv",
            params={"fields": "task,stop_reason", "trim_strings": True, "limit": 10},
        )
        assert resp.status_code == 200
        assert resp.headers["x-export-trim-strings"] == "true"
        lines = [line for line in resp.text.strip().splitlines() if line]
        assert lines[0] == "task,stop_reason"
        assert lines[1] == "padded task,good"
    finally:
        PaperService.list_runs = original_list_runs
        PaperService.count_runs = original_count_runs




def test_runs_export_csv_supports_empty_as_null():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    original_list_runs = PaperService.list_runs
    original_count_runs = PaperService.count_runs
    try:
        PaperService.list_runs = lambda self, **kwargs: [
            SimpleNamespace(
                run_id="empty-as-null-run",
                task="   ",
                quality_score=8,
                stop_reason="",
                iterations_used=1,
                duration_ms=12,
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        PaperService.count_runs = lambda self, **kwargs: 1

        resp = client.get(
            "/v1/papers/runs/export.csv",
            params={
                "fields": "task,stop_reason",
                "trim_strings": True,
                "empty_as_null": True,
                "null_value": "NULL",
                "limit": 10,
            },
        )
        assert resp.status_code == 200
        assert resp.headers["x-export-empty-as-null"] == "true"
        lines = [line for line in resp.text.strip().splitlines() if line]
        assert lines[0] == "task,stop_reason"
        assert lines[1] == "NULL,NULL"
    finally:
        PaperService.list_runs = original_list_runs
        PaperService.count_runs = original_count_runs
def test_runs_export_csv_supports_backslash_escape_style():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    client.post(
        "/v1/papers/generate",
        json={"task": 'He said "hello"', "outline": "Intro,Method", "iterations": 1},
    )

    resp = client.get(
        "/v1/papers/runs/export.csv",
        params={"fields": "task", "quote_all": True, "escape_style": "backslash", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.headers["x-export-escape-style"] == "backslash"

    lines = [line for line in resp.text.strip().splitlines() if line]
    assert lines[0] == '"task"'
    assert '\\"hello\\"' in lines[1]


def test_runs_export_csv_rejects_invalid_escape_style():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    resp = client.get("/v1/papers/runs/export.csv", params={"escape_style": "none"})
    assert resp.status_code == 422


def test_runs_export_csv_supports_max_cell_length_truncation():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    original_list_runs = PaperService.list_runs
    original_count_runs = PaperService.count_runs
    try:
        PaperService.list_runs = lambda self, **kwargs: [
            SimpleNamespace(
                run_id="truncate-run",
                task="abcdefghijklmnopqrstuvwxyz",
                quality_score=8,
                stop_reason="ok",
                iterations_used=1,
                duration_ms=12,
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        PaperService.count_runs = lambda self, **kwargs: 1

        resp = client.get(
            "/v1/papers/runs/export.csv",
            params={"fields": "task", "max_cell_length": 5, "limit": 10},
        )
        assert resp.status_code == 200
        assert resp.headers["x-export-max-cell-length"] == "5"
        lines = [line for line in resp.text.strip().splitlines() if line]
        assert lines[0] == "task"
        assert lines[1] == "abcde"
    finally:
        PaperService.list_runs = original_list_runs
        PaperService.count_runs = original_count_runs
