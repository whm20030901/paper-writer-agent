from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewReport:
    structure_feedback: str
    evidence_feedback: str
    citation_feedback: str
    language_feedback: str
    score: int
    revision_plan: list[str]

    def to_text(self) -> str:
        lines = [
            self.structure_feedback,
            self.evidence_feedback,
            self.citation_feedback,
            self.language_feedback,
            f"- Quality Score: {self.score}/10",
            "- Revision Plan:",
        ]
        lines.extend([f"  - {item}" for item in self.revision_plan])
        return "\n".join(lines)


@dataclass
class DraftPackage:
    draft: str
    review: str
    review_report: dict[str, object]
    iterations_used: int
    quality_score: int
    stop_reason: str
    research_sources: list[ResearchSource]


@dataclass
class WriterOutput:
    draft: str
    research_sources: list[ResearchSource]


@dataclass(frozen=True)
class ResearchSource:
    citation_id: int
    title: str
    source_type: str
    locator: str
    excerpt: str

    def inline_citation(self) -> str:
        return f"[{self.citation_id}]"

    def to_reference_line(self) -> str:
        detail = f" {self.locator}." if self.locator else ""
        excerpt = f" Evidence: {self.excerpt}" if self.excerpt else ""
        return f"[{self.citation_id}] {self.title}. {self.source_type}.{detail}{excerpt}".strip()


@dataclass(frozen=True)
class ResearchPacket:
    summary: str
    sources: list[ResearchSource]
