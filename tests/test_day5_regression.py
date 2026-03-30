from fastapi.testclient import TestClient

from paper_writer_agent.agents import PaperPipeline, PaperReviewerAgent, PaperWriterAgent
from paper_writer_agent.api.app import create_app
from paper_writer_agent.core.config import Settings
from paper_writer_agent.main import bootstrap_pipeline
from paper_writer_agent.subagents_research import ResearchSubAgent
from paper_writer_agent.subagents_review import StructureReviewSubAgent
from paper_writer_agent.subagents_writing import DraftingSubAgent


def test_modular_routes_are_registered_and_legacy_paths_remain_compatible():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    paths = {route.path for route in app.routes}

    expected = {
        "/v1/papers/generate",
        "/v1/papers/runs",
        "/v1/papers/runs/export.csv",
        "/v1/papers/runs/{run_id}",
        "/v1/papers/runs/{run_id}/insights",
        "/v1/papers/runs/{run_id}/save-edited",
        "/v1/papers/metrics",
    }
    assert expected.issubset(paths)


def test_pipeline_orchestration_uses_split_subagent_modules():
    pipeline = bootstrap_pipeline(Settings(memory_db_path=":memory:", run_db_path=":memory:"))

    assert isinstance(pipeline, PaperPipeline)
    assert isinstance(pipeline.writer, PaperWriterAgent)
    assert isinstance(pipeline.reviewer, PaperReviewerAgent)

    assert isinstance(pipeline.writer.research_agent, ResearchSubAgent)
    assert isinstance(pipeline.writer.drafting_agent, DraftingSubAgent)
    assert isinstance(pipeline.reviewer.structure_reviewer, StructureReviewSubAgent)


def test_generate_mainline_still_works_after_day4_split():
    app = create_app(Settings(app_env="test", memory_db_path=":memory:", run_db_path=":memory:"))
    client = TestClient(app)

    response = client.post(
        "/v1/papers/generate",
        json={
            "task": "Day5 regression check",
            "outline": "Intro, Method, Eval, Conclusion",
            "iterations": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["draft"].startswith("# Day5 regression check")
    assert "[References]" in payload["draft"]
    assert payload["review_report"]["revision_plan"]
    assert payload["stop_reason"] in {"quality_threshold_reached", "max_iterations_reached"}
