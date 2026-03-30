from __future__ import annotations

from dataclasses import dataclass

from .rag import RetrievalResult


@dataclass
class ContextInput:
    task: str
    outline: str
    revision_notes: str
    retrieved: list[RetrievalResult]
    memory_summary: str
    reviewer_feedback: str


class ContextBuilder:
    def __init__(self, max_chars: int = 3500):
        self.max_chars = max_chars

    def _render_retrieval(self, retrieved: list[RetrievalResult]) -> str:
        lines = []
        for item in retrieved:
            lines.append(
                f"- [doc={item.chunk.doc_id} chunk={item.chunk.chunk_id} score={item.score:.2f}] {item.chunk.text[:180]}"
            )
        return "\n".join(lines)

    def build(self, data: ContextInput) -> str:
        context = f"""
[Task]
{data.task}

[Outline]
{data.outline}

[Revision Notes]
{data.revision_notes or 'N/A'}

[Evidence from RAG]
{self._render_retrieval(data.retrieved)}

[Reviewer Feedback]
{data.reviewer_feedback}

[Memory]
{data.memory_summary}
""".strip()
        return context[: self.max_chars]
