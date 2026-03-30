from paper_writer_agent.core.config import Settings
from paper_writer_agent.main import bootstrap_pipeline
from paper_writer_agent.agents import (
    PaperPipeline,
    PaperReviewerAgent,
    ResearchSource,
    ReviewReport,
    WriterOutput,
)
from paper_writer_agent.context_engineering import ContextBuilder
from paper_writer_agent.mcp_registry import build_default_registry
from paper_writer_agent.memory import LongTermMemory, MemoryManager, WorkingMemory
from paper_writer_agent.rag import RAGEngine
from paper_writer_agent.skills import build_default_skills


def test_pipeline_generates_draft_review_and_metrics():
    pipeline = bootstrap_pipeline()
    result = pipeline.run(
        task="AI agent for paper writing",
        outline="Intro, Method, Eval, Conclusion",
        iterations=2,
    )
    assert result.draft.startswith("# AI agent for paper writing")
    assert "## Abstract" in result.draft
    assert "## Revision Focus" in result.draft
    assert "## Intro, Method, Eval, Conclusion" in result.draft or "## Conclusion" in result.draft
    assert "[References]" in result.draft
    assert "[1]" in result.draft
    assert "Local knowledge base: agent_survey" in result.draft
    assert result.research_sources
    assert any(source.title == "Local knowledge base: agent_survey" for source in result.research_sources)
    assert "- Structure:" in result.review
    assert "- Evidence:" in result.review
    assert "- Citation:" in result.review
    assert "- Language:" in result.review
    assert "- Quality Score:" in result.review
    assert "- Revision Plan:" in result.review
    assert "claim-to-citation mappings" in result.review
    assert result.review_report
    assert result.review_report["score"] == result.quality_score
    assert result.review_report["revision_plan"]
    assert result.iterations_used >= 1
    assert 0 <= result.quality_score <= 10
    assert result.stop_reason in {"quality_threshold_reached", "max_iterations_reached"}


def test_pipeline_uses_llm_when_configured(monkeypatch):
    def _fake_generate_draft(self, **kwargs):
        assert kwargs["task"] == "AI agent for paper writing"
        return "# LLM Draft\nGenerated from provider\n\n[References]\n[999] Provider-supplied reference"

    monkeypatch.setattr("paper_writer_agent.llm.LLMClient.generate_draft", _fake_generate_draft)

    pipeline = bootstrap_pipeline(
        Settings(
            memory_db_path=":memory:",
            llm_api_key="test-key",
            llm_model="test-model",
            llm_base_url="https://example-llm.local",
            llm_timeout_s=5,
        )
    )
    result = pipeline.run(
        task="AI agent for paper writing",
        outline="Intro, Method, Eval, Conclusion",
        iterations=1,
    )

    assert result.draft.startswith("# LLM Draft")
    assert "[References]" in result.draft
    assert "Provider-supplied reference" not in result.draft
    assert "Local knowledge base: agent_survey" in result.draft


def test_pipeline_falls_back_when_llm_call_fails(monkeypatch):
    def _fake_generate_draft(self, **kwargs):
        raise RuntimeError("provider timeout")

    monkeypatch.setattr("paper_writer_agent.llm.LLMClient.generate_draft", _fake_generate_draft)

    pipeline = bootstrap_pipeline(
        Settings(
            memory_db_path=":memory:",
            llm_api_key="test-key",
            llm_model="test-model",
        )
    )

    result = pipeline.run(
        task="AI agent for paper writing",
        outline="Intro, Method, Eval, Conclusion",
        iterations=1,
    )

    assert result.draft.startswith("# AI agent for paper writing")
    assert "## Abstract" in result.draft
    assert "## Revision Focus" in result.draft
    assert "[References]" in result.draft
    assert "Academic paper" in result.draft


def test_pipeline_includes_revision_notes_in_local_draft():
    pipeline = bootstrap_pipeline(Settings(memory_db_path=":memory:"))
    result = pipeline.run(
        task="AI agent for paper writing",
        outline="Intro, Method, Eval, Conclusion",
        iterations=1,
        revision_notes="Strengthen the evaluation section and make the conclusion more concise.",
    )

    assert "Strengthen the evaluation section" in result.draft
    assert "[References]" in result.draft


def test_reviewer_scores_high_for_structured_and_cited_draft():
    reviewer = PaperReviewerAgent()
    draft = (
        "# Demo\n\n"
        "## Abstract\n"
        "Summary with evidence [1] [2].\n\n"
        "## Method\n"
        "Method details grounded by retrieved evidence [1].\n\n"
        "## Evaluation\n"
        "Evaluation results compare baselines and ablations [2] [3].\n\n"
        "## Conclusion\n"
        "Conclusion synthesizes findings and limitations.\n\n"
        "[References]\n"
        "[1] Source A.\n"
        "[2] Source B.\n"
        "[3] Source C.\n"
    )
    report = reviewer.review(draft)
    assert report.score >= 8
    assert "aligned" in report.structure_feedback
    assert "grounded" in report.evidence_feedback
    assert "coverage is complete" in report.citation_feedback


def test_reviewer_returns_actionable_plan_for_weak_draft():
    reviewer = PaperReviewerAgent()
    weak_draft = "# Demo\n\nA short paragraph without citations."
    report = reviewer.review(weak_draft)
    assert report.score <= 6
    assert "missing sections" in report.structure_feedback
    assert "insufficient grounding" in report.evidence_feedback
    assert "missing references section" in report.citation_feedback
    assert any("inline citations" in item.lower() for item in report.revision_plan)


def test_pipeline_supports_injected_agent_interfaces():
    class FakeWriter:
        def write(self, task: str, outline: str, revision_notes: str, **kwargs):
            return WriterOutput(
                draft=f"# {task}\n\n## Draft\nInjected writer output.",
                research_sources=[
                    ResearchSource(
                        citation_id=1,
                        title="Injected Source",
                        source_type="test",
                        locator="unit-test",
                        excerpt="injected",
                    )
                ],
            )

    class FakeReviewer:
        def review(self, draft: str):
            return ReviewReport(
                structure_feedback="- Structure: aligned with outline.",
                evidence_feedback="- Evidence: grounded in provided sources.",
                citation_feedback="- Citation: source-backed with complete coverage.",
                language_feedback="- Language: clear and concise.",
                score=9,
                revision_plan=["No-op"],
            )

    class FakeGate:
        def should_stop(self, score: int, threshold: int = 8) -> bool:
            return score >= threshold

    rag = RAGEngine()
    rag.add_document("doc", "test chunk")
    pipeline = PaperPipeline(
        rag=rag,
        memory=MemoryManager(working=WorkingMemory(), long_term=LongTermMemory(":memory:")),
        mcp=build_default_registry(),
        skills=build_default_skills(),
        context_builder=ContextBuilder(max_chars=2000),
        writer=FakeWriter(),
        reviewer=FakeReviewer(),
        quality_gate=FakeGate(),
    )

    result = pipeline.run(task="Injected task", outline="Intro", iterations=3)
    assert result.draft.startswith("# Injected task")
    assert result.quality_score == 9
    assert result.stop_reason == "quality_threshold_reached"
