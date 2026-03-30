from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalSample:
    sample_id: str
    task: str
    outline: str
    iterations: int = 2


BASELINE_EVAL_SAMPLES: list[EvalSample] = [
    EvalSample(
        sample_id="baseline-agent-memory",
        task="Design a memory-augmented multi-agent workflow for academic writing",
        outline="Introduction, System Design, Memory Strategy, Evaluation, Conclusion",
    ),
    EvalSample(
        sample_id="baseline-rag-citation",
        task="Write an evidence-grounded paper plan for RAG citation quality control",
        outline="Background, Problem Statement, Method, Experiments, Risks, Conclusion",
    ),
    EvalSample(
        sample_id="baseline-llm-reliability",
        task="Analyze retry and fallback strategies for LLM-dependent writing pipelines",
        outline="Motivation, Reliability Design, Failure Modes, Benchmark, Conclusion",
    ),
    EvalSample(
        sample_id="baseline-eval-metrics",
        task="Propose a metrics framework for iterative paper drafting agents",
        outline="Goals, Metrics Definition, Data Collection, Dashboard, Conclusion",
    ),
    EvalSample(
        sample_id="baseline-review-loop",
        task="Compare reviewer-guided revision loops with single-pass drafting",
        outline="Hypothesis, Methodology, Results, Discussion, Conclusion",
    ),
]
