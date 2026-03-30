from __future__ import annotations

import re

INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
SECTION_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
REFERENCE_LINE_RE = re.compile(r"^\[(\d+)\]\s+", re.MULTILINE)


class StructureReviewSubAgent:
    def run(self, draft: str) -> str:
        headings = [heading.strip().lower() for heading in SECTION_HEADING_RE.findall(draft)]
        has_abstract = "abstract" in headings
        has_method = any("method" in heading for heading in headings)
        has_evaluation = any("eval" in heading or "result" in heading for heading in headings)
        has_conclusion = any("conclusion" in heading for heading in headings)
        if has_abstract and has_method and has_evaluation and has_conclusion:
            return "- Structure: aligned with outline and core academic sections are present."
        missing: list[str] = []
        if not has_abstract:
            missing.append("Abstract")
        if not has_method:
            missing.append("Method")
        if not has_evaluation:
            missing.append("Evaluation/Results")
        if not has_conclusion:
            missing.append("Conclusion")
        return f"- Structure: add explicit section transitions and missing sections ({', '.join(missing)})."


class EvidenceReviewSubAgent:
    def run(self, draft: str) -> str:
        inline_citation_count = len({match.group(1) for match in INLINE_CITATION_RE.finditer(draft)})
        if ("[RAG]" in draft or "evidence" in draft.lower()) and inline_citation_count >= 3:
            return "- Evidence: grounded with concrete support, but add claim-to-citation mapping table."
        if inline_citation_count >= 1:
            return "- Evidence: partially grounded; strengthen claim-to-evidence links in each major section."
        return "- Evidence: insufficient grounding, add retrieved support."


class CitationReviewSubAgent:
    def run(self, draft: str) -> str:
        inline_citations = {match.group(1) for match in INLINE_CITATION_RE.finditer(draft)}
        reference_ids = {match.group(1) for match in REFERENCE_LINE_RE.finditer(draft)}
        has_references = "[References]" in draft and bool(reference_ids)
        if has_references and len(inline_citations) >= 2:
            missing_references = sorted(inline_citations - reference_ids)
            unused_references = sorted(reference_ids - inline_citations)
            if not missing_references and not unused_references:
                return "- Citation: source-backed with inline markers; section-to-reference coverage is complete."
            if missing_references:
                return (
                    "- Citation: source-backed, but add reference entries for inline markers: "
                    + ", ".join(f"[{marker}]" for marker in missing_references)
                    + "."
                )
            return (
                "- Citation: source-backed, but remove or use unused references: "
                + ", ".join(f"[{marker}]" for marker in unused_references)
                + "."
            )
        if has_references:
            return "- Citation: references exist, but add more inline citation anchors in the body."
        return "- Citation: missing references section and inline citation support."


class LanguageReviewSubAgent:
    def run(self, draft: str) -> str:
        if len(draft) < 800:
            return "- Language: expand method and evaluation details."
        return "- Language: wording is clear; polish conciseness."
