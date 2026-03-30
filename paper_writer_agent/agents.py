from __future__ import annotations

from dataclasses import asdict
from typing import TypedDict

from .agent_interfaces import QualityGateInterface, ReviewerAgentInterface, WriterAgentInterface
from .agent_types import DraftPackage, ResearchSource, ReviewReport, WriterOutput
from .context_engineering import ContextBuilder, ContextInput
from .llm import LLMClient
from .memory import MemoryManager
from .mcp_registry import MCPRegistry
from .rag import RAGEngine
from .skills import SkillManager
from .subagents_research import ResearchSubAgent
from .subagents_review import (
    CitationReviewSubAgent,
    EvidenceReviewSubAgent,
    LanguageReviewSubAgent,
    StructureReviewSubAgent,
)
from .subagents_writing import CitationSubAgent, DraftingSubAgent, OutlineSubAgent, RevisionSubAgent

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional dependency fallback
    END = None
    StateGraph = None


class QualityGateSubAgent(QualityGateInterface):
    def should_stop(self, score: int, threshold: int = 8) -> bool:
        return score >= threshold

    def run(self, report: ReviewReport, threshold: int = 8) -> tuple[bool, str]:
        should_stop = self.should_stop(report.score, threshold)
        if should_stop:
            return True, "quality_threshold_reached"
        return False, "needs_more_revision"


class PaperWriterAgent(WriterAgentInterface):
    def __init__(self):
        self.research_agent = ResearchSubAgent()
        self.outline_agent = OutlineSubAgent()
        self.drafting_agent = DraftingSubAgent()
        self.revision_agent = RevisionSubAgent()
        self.citation_agent = CitationSubAgent()

    def write(
        self,
        task: str,
        outline: str,
        rag: RAGEngine,
        mcp: MCPRegistry,
        memory: MemoryManager,
        context_builder: ContextBuilder,
        reviewer_feedback: str,
        skills_summary: str,
        revision_notes: str,
        llm: LLMClient | None,
    ) -> WriterOutput:
        research_packet = self.research_agent.run(task=task, rag=rag, mcp=mcp, memory=memory)
        planning_report = self.outline_agent.run(task=task, outline=outline)

        context = context_builder.build(
            ContextInput(
                task=task,
                outline=planning_report,
                revision_notes=revision_notes,
                retrieved=rag.retrieve(task, top_k=3),
                memory_summary=memory.build_memory_summary(),
                reviewer_feedback=reviewer_feedback,
            )
        )
        draft = self.drafting_agent.run(
            task=task,
            outline=outline,
            context=f"{research_packet.summary}\n\n{context}",
            sources=research_packet.sources,
            skills_summary=skills_summary,
            reviewer_feedback=reviewer_feedback,
            revision_notes=revision_notes,
            llm=llm,
        )
        revised_draft = self.revision_agent.run(draft, reviewer_feedback)
        return WriterOutput(
            draft=self.citation_agent.run(revised_draft, research_packet.sources),
            research_sources=research_packet.sources,
        )


class PaperReviewerAgent(ReviewerAgentInterface):
    def __init__(self):
        self.structure_reviewer = StructureReviewSubAgent()
        self.evidence_reviewer = EvidenceReviewSubAgent()
        self.citation_reviewer = CitationReviewSubAgent()
        self.language_reviewer = LanguageReviewSubAgent()

    def review(self, draft: str) -> ReviewReport:
        structure = self.structure_reviewer.run(draft)
        evidence = self.evidence_reviewer.run(draft)
        citation = self.citation_reviewer.run(draft)
        language = self.language_reviewer.run(draft)

        score = 5
        if "aligned" in structure:
            score += 2
        if "grounded" in evidence:
            score += 2
        elif "partially grounded" in evidence:
            score += 1
        if "source-backed" in citation:
            score += 1
        if "coverage is complete" in citation:
            score += 1
        if "clear" in language:
            score += 1
        score = min(score, 10)
        revision_plan = self._build_revision_plan(structure, evidence, citation, language)

        return ReviewReport(
            structure_feedback=structure,
            evidence_feedback=evidence,
            citation_feedback=citation,
            language_feedback=language,
            score=score,
            revision_plan=revision_plan,
        )

    def _build_revision_plan(
        self,
        structure: str,
        evidence: str,
        citation: str,
        language: str,
    ) -> list[str]:
        plan: list[str] = []
        if "aligned" not in structure:
            plan.append("Reshape the draft so each outline section has a clearer transition and conclusion.")
        if "grounded" not in evidence:
            plan.append("Add stronger retrieved evidence and explicitly connect claims to supporting material.")
        else:
            plan.append("Convert the strongest evidence claims into explicit claim-to-citation mappings.")
        if "source-backed" not in citation:
            plan.append("Insert inline citations throughout the body and ensure every major section maps to a reference.")
        else:
            plan.append("Audit inline citations so each section cites the most relevant source rather than repeating the same marker.")
        if "clear" not in language:
            plan.append("Expand underdeveloped sections with clearer method and evaluation details.")
        else:
            plan.append("Tighten wording and remove redundant explanation in the strongest sections.")
        return plan


class PipelineState(TypedDict):
    task: str
    outline: str
    revision_notes: str
    iterations: int
    round_id: int
    last_review: str
    last_review_report: dict[str, object]
    draft: str
    research_sources: list[ResearchSource]
    quality_score: int
    stop_reason: str


class PaperPipeline:
    def __init__(
        self,
        rag: RAGEngine,
        memory: MemoryManager,
        mcp: MCPRegistry,
        skills: SkillManager,
        context_builder: ContextBuilder,
        llm: LLMClient | None = None,
        writer: WriterAgentInterface | None = None,
        reviewer: ReviewerAgentInterface | None = None,
        quality_gate: QualityGateInterface | None = None,
    ):
        self.rag = rag
        self.memory = memory
        self.mcp = mcp
        self.skills = skills
        self.context_builder = context_builder
        self.llm = llm
        self.writer = writer if writer is not None else PaperWriterAgent()
        self.reviewer = reviewer if reviewer is not None else PaperReviewerAgent()
        self.quality_gate = quality_gate if quality_gate is not None else QualityGateSubAgent()

    def _writer_step(self, state: PipelineState) -> PipelineState:
        writer_output = self.writer.write(
            task=state["task"],
            outline=state["outline"],
            revision_notes=state["revision_notes"],
            rag=self.rag,
            mcp=self.mcp,
            memory=self.memory,
            context_builder=self.context_builder,
            reviewer_feedback=state["last_review"],
            skills_summary=self.skills.describe(),
            llm=self.llm,
        )
        state["draft"] = writer_output.draft
        state["research_sources"] = writer_output.research_sources
        return state

    def _reviewer_step(self, state: PipelineState) -> PipelineState:
        report = self.reviewer.review(state["draft"])
        review_text = report.to_text()
        self.memory.remember_turn("reviewer", review_text, tag="review")
        state["last_review"] = review_text
        state["last_review_report"] = asdict(report)
        state["quality_score"] = report.score
        state["round_id"] += 1
        return state

    def _gate_step(self, state: PipelineState) -> PipelineState:
        should_stop = self.quality_gate.should_stop(score=state["quality_score"], threshold=8)
        reason = "quality_threshold_reached" if should_stop else "needs_more_revision"
        if should_stop:
            state["stop_reason"] = reason
        return state

    def _route_step(self, state: PipelineState) -> str:
        if state["stop_reason"] == "quality_threshold_reached":
            return END
        return "writer" if state["round_id"] < state["iterations"] else END

    def _run_with_langgraph(self, state: PipelineState) -> PipelineState:
        graph = StateGraph(PipelineState)
        graph.add_node("writer", self._writer_step)
        graph.add_node("reviewer", self._reviewer_step)
        graph.add_node("gate", self._gate_step)

        graph.set_entry_point("writer")
        graph.add_edge("writer", "reviewer")
        graph.add_edge("reviewer", "gate")
        graph.add_conditional_edges("gate", self._route_step, {"writer": "writer", END: END})

        app = graph.compile()
        return app.invoke(state)

    def _run_sequential(self, state: PipelineState) -> PipelineState:
        while state["round_id"] < state["iterations"]:
            state = self._writer_step(state)
            state = self._reviewer_step(state)
            state = self._gate_step(state)
            if state["stop_reason"] == "quality_threshold_reached":
                break

        if state["stop_reason"] == "not_finished":
            state["stop_reason"] = "max_iterations_reached"
        return state

    def run(
        self,
        task: str,
        outline: str,
        iterations: int = 2,
        revision_notes: str = "",
    ) -> DraftPackage:
        state: PipelineState = {
            "task": task,
            "outline": outline,
            "revision_notes": revision_notes,
            "iterations": iterations,
            "round_id": 0,
            "last_review": "N/A",
            "last_review_report": {},
            "draft": "",
            "research_sources": [],
            "quality_score": 0,
            "stop_reason": "not_finished",
        }

        if StateGraph is not None and END is not None:
            final_state = self._run_with_langgraph(state)
            if final_state["stop_reason"] == "not_finished":
                final_state["stop_reason"] = "max_iterations_reached"
        else:
            final_state = self._run_sequential(state)

        return DraftPackage(
            draft=final_state["draft"],
            review=final_state["last_review"],
            review_report=final_state["last_review_report"],
            iterations_used=final_state["round_id"],
            quality_score=final_state["quality_score"],
            stop_reason=final_state["stop_reason"],
            research_sources=final_state["research_sources"],
        )

    def close(self) -> None:
        self.memory.close()
