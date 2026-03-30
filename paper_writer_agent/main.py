from __future__ import annotations

import logging

from .agents import PaperPipeline
from .context_engineering import ContextBuilder
from .core.config import Settings
from .core.logging import setup_logging
from .llm import LLMClient, LLMSettings
from .memory import LongTermMemory, MemoryManager, WorkingMemory
from .mcp_registry import build_default_registry
from .rag import RAGEngine
from .skills import build_default_skills

logger = logging.getLogger(__name__)


def bootstrap_pipeline(settings: Settings | None = None) -> PaperPipeline:
    cfg = settings or Settings.from_env()

    rag = RAGEngine(chunk_size=80)
    rag.add_document(
        "agent_survey",
        "Agent systems rely on planning, tool usage, memory, and feedback loops. "
        "In writing tasks, evidence grounding and iterative review significantly improve quality.",
    )
    rag.add_document(
        "memory_paper",
        "Memory-augmented agents combine short-term dialogue state and long-term stores. "
        "A memory manager should include retention, retrieval, and pruning strategies.",
    )

    memory = MemoryManager(WorkingMemory(12), LongTermMemory(cfg.memory_db_path))
    mcp = build_default_registry()
    skills = build_default_skills()
    context_builder = ContextBuilder(max_chars=3200)
    llm = LLMClient(
        LLMSettings(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            timeout_s=cfg.llm_timeout_s,
            max_retries=cfg.llm_max_retries,
            retry_backoff_s=cfg.llm_retry_backoff_s,
            retry_jitter_s=cfg.llm_retry_jitter_s,
            retry_max_delay_s=cfg.llm_retry_max_delay_s,
            retry_backoff_multiplier=cfg.llm_retry_backoff_multiplier,
        )
    )
    return PaperPipeline(rag, memory, mcp, skills, context_builder, llm=llm)


def main() -> None:
    cfg = Settings.from_env()
    setup_logging("INFO")
    logger.info("starting local cli demo", extra={"env": cfg.app_env})

    pipeline = bootstrap_pipeline(cfg)
    result = pipeline.run(
        task="Design an AI agent framework for academic writing",
        outline="1. Intro 2. Related Work 3. Method 4. Evaluation 5. Conclusion",
        iterations=cfg.default_iterations,
    )

    print("=== FINAL DRAFT ===")
    print(result.draft)
    print("\n=== FINAL REVIEW ===")
    print(result.review)
    print("\n=== PIPELINE METRICS ===")
    print(f"iterations_used={result.iterations_used}")
    print(f"quality_score={result.quality_score}")
    print(f"stop_reason={result.stop_reason}")


if __name__ == "__main__":
    main()
