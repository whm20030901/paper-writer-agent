from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ToolHandler = Callable[..., Any]


@dataclass
class MCPTool:
    name: str
    description: str
    handler: ToolHandler


class MCPRegistry:
    def __init__(self):
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool {name} not found")
        return self._tools[name].handler(**kwargs)


def build_default_registry() -> MCPRegistry:
    registry = MCPRegistry()

    def search_papers(query: str) -> list[str]:
        return [
            f"{query} - A Survey on Agentic Systems (2024)",
            f"{query} - Memory-Augmented LLM Agents (2023)",
        ]

    def lookup_repo(topic: str) -> list[str]:
        return [
            f"github.com/example/{topic}-agent",
            f"github.com/example/{topic}-rag-pipeline",
        ]

    registry.register(MCPTool("search_papers", "Search academic references", search_papers))
    registry.register(MCPTool("lookup_repo", "Search related code repositories", lookup_repo))
    return registry
