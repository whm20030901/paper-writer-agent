from __future__ import annotations

import logging

from .agent_types import ResearchSource
from .llm import LLMClient

logger = logging.getLogger(__name__)


class OutlineSubAgent:
    def run(self, task: str, outline: str) -> str:
        return f"Task={task}\nPlanned Outline={outline}"


class DraftingSubAgent:
    def _parse_outline_sections(self, outline: str) -> list[str]:
        sections: list[str] = []
        for raw_line in outline.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ". " in line:
                _, maybe_title = line.split(". ", 1)
                line = maybe_title.strip() or line
            if "," in line and not line.startswith("["):
                sections.extend([part.strip() for part in line.split(",") if part.strip()])
            else:
                sections.append(line)
        return sections or ["Introduction", "Method", "Evaluation", "Conclusion"]

    def _build_local_section_body(
        self,
        *,
        task: str,
        section_title: str,
        context: str,
        sources: list[ResearchSource],
        skills_summary: str,
        reviewer_feedback: str,
        revision_notes: str,
    ) -> str:
        evidence_lines = [
            line.strip("- ").strip()
            for line in context.splitlines()
            if "score=" in line or "memory" in line.lower() or "agent" in line.lower()
        ]
        evidence_snippet = "; ".join(evidence_lines[:2]) or "Ground the argument in retrieved evidence and prior review history."
        reviewer_note = (
            reviewer_feedback[:140]
            if reviewer_feedback and reviewer_feedback != "N/A"
            else "No reviewer concerns have been raised yet."
        )
        section_sources = self._select_section_sources(section_title=section_title, sources=sources)
        inline_citations = " ".join(source.inline_citation() for source in section_sources)
        return (
            f"This section advances the paper objective: {task}. "
            f"It focuses on {section_title.lower()} and connects the claim to concrete evidence. "
            f"Evidence basis: {evidence_snippet}. {inline_citations} "
            f"Writing skills applied: {skills_summary.splitlines()[0] if skills_summary else 'structured drafting'}. "
            f"Reviewer note: {reviewer_note}. "
            f"Revision intent: {revision_notes or 'Preserve the strongest parts of the current draft while improving clarity.'}"
        )

    def _select_section_sources(
        self,
        *,
        section_title: str,
        sources: list[ResearchSource],
        max_sources: int = 2,
    ) -> list[ResearchSource]:
        if not sources:
            return []

        section_terms = {term.lower() for term in section_title.replace("/", " ").split() if term.strip()}
        ranked = sorted(
            sources,
            key=lambda source: (
                sum(term in f"{source.title} {source.excerpt}".lower() for term in section_terms),
                -source.citation_id,
            ),
            reverse=True,
        )
        selected = [source for source in ranked[:max_sources] if source]
        return selected or sources[:max_sources]

    def run(
        self,
        *,
        task: str,
        outline: str,
        context: str,
        sources: list[ResearchSource],
        skills_summary: str,
        reviewer_feedback: str,
        revision_notes: str,
        llm: LLMClient | None,
    ) -> str:
        if llm is not None and llm.enabled:
            try:
                return llm.generate_draft(
                    task=task,
                    outline=outline,
                    context=f"{context}\n\n[Revision Notes]\n{revision_notes or 'N/A'}",
                    skills_summary=skills_summary,
                    reviewer_feedback=reviewer_feedback,
                )
            except Exception as exc:  # pragma: no cover - network/provider failure fallback
                logger.warning("llm generation failed, fallback to local drafting", extra={"error": str(exc)})

        sections = self._parse_outline_sections(outline)
        lead_sources = self._select_section_sources(section_title="abstract", sources=sources)
        lead_citations = " ".join(source.inline_citation() for source in lead_sources)
        abstract = (
            f"This draft addresses '{task}' through an agent-oriented writing workflow. "
            f"It synthesizes retrieved evidence, memory, and reviewer feedback into a concise paper scaffold. {lead_citations}"
        )
        rendered_sections = "\n\n".join(
            [
                f"## {section_title}\n"
                f"{self._build_local_section_body(task=task, section_title=section_title, context=context, sources=sources, skills_summary=skills_summary, reviewer_feedback=reviewer_feedback, revision_notes=revision_notes)}"
                for section_title in sections
            ]
        )
        return (
            f"# {task}\n\n"
            "## Abstract\n"
            f"{abstract}\n\n"
            "## Revision Focus\n"
            f"{revision_notes or 'No explicit revision notes were provided for this pass.'}\n\n"
            "## Evidence Snapshot\n"
            f"{context[:800]}\n\n"
            f"{rendered_sections}\n\n"
            "## Conclusion\n"
            "The paper draft is ready for another review pass focused on evidence alignment, clarity, and citation completeness."
        )


class RevisionSubAgent:
    def run(self, draft: str, reviewer_feedback: str) -> str:
        if reviewer_feedback == "N/A":
            return draft
        return draft + f"\n\n[Revision Notes]\nAddressed feedback:\n{reviewer_feedback[:400]}"


class CitationSubAgent:
    def run(self, draft: str, sources: list[ResearchSource]) -> str:
        body, _, _ = draft.partition("\n[References]\n")
        normalized_draft = body.rstrip()
        if not sources:
            return normalized_draft
        evidence_lines = "\n".join(
            f"- {source.inline_citation()} {source.excerpt or source.title}"
            for source in sources
        )
        reference_lines = "\n".join(source.to_reference_line() for source in sources)
        return (
            f"{normalized_draft}\n\n"
            "## Evidence-Citation Map\n"
            f"{evidence_lines}\n\n"
            "[References]\n"
            f"{reference_lines}"
        )
