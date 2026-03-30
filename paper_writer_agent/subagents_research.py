from __future__ import annotations

from .agent_types import ResearchPacket, ResearchSource
from .memory import MemoryManager
from .mcp_registry import MCPRegistry
from .rag import RAGEngine


class ResearchSubAgent:
    """Collect grounded evidence from MCP tools and local RAG store."""

    def run(self, task: str, rag: RAGEngine, mcp: MCPRegistry, memory: MemoryManager) -> ResearchPacket:
        papers = mcp.call("search_papers", query=task)
        repos = mcp.call("lookup_repo", topic="paper-writing")
        rag_hits = rag.retrieve(task, top_k=3)

        memory.remember_turn("research", f"papers={papers}")
        memory.remember_turn("research", f"repos={repos}")

        sources: list[ResearchSource] = []
        for paper in papers:
            sources.append(
                ResearchSource(
                    citation_id=len(sources) + 1,
                    title=paper,
                    source_type="Academic paper",
                    locator="MCP search result",
                    excerpt=f"Retrieved for task '{task}'.",
                )
            )
        for item in rag_hits:
            sources.append(
                ResearchSource(
                    citation_id=len(sources) + 1,
                    title=f"Local knowledge base: {item.chunk.doc_id}",
                    source_type="RAG chunk",
                    locator=f"chunk={item.chunk.chunk_id}, score={item.score:.2f}",
                    excerpt=item.chunk.text[:180],
                )
            )
        for repo in repos:
            sources.append(
                ResearchSource(
                    citation_id=len(sources) + 1,
                    title=repo,
                    source_type="Implementation reference",
                    locator="MCP repository lookup",
                    excerpt="Repository surfaced as implementation context for the writing workflow.",
                )
            )

        source_text = "\n".join(
            [
                f"- {source.inline_citation()} {source.title} ({source.source_type}; {source.locator})"
                for source in sources
            ]
        )
        summary = f"[MCP Papers]\n{papers}\n[MCP Repos]\n{repos}\n[RAG]\n{source_text}"
        return ResearchPacket(summary=summary, sources=sources)
