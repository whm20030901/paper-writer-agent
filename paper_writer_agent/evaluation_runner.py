from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .eval_samples import BASELINE_EVAL_SAMPLES, EvalSample
from .main import bootstrap_pipeline


@dataclass
class EvalRunResult:
    sample_id: str
    quality_score: int
    stop_reason: str
    iterations_used: int


@dataclass
class EvalSummary:
    total_samples: int
    success_rate: float
    avg_quality_score: float
    avg_iterations_used: float
    results: list[EvalRunResult]


def run_baseline_evaluation(samples: list[EvalSample] | None = None) -> EvalSummary:
    eval_samples = samples or BASELINE_EVAL_SAMPLES
    pipeline = bootstrap_pipeline()
    try:
        results: list[EvalRunResult] = []
        for sample in eval_samples:
            run = pipeline.run(task=sample.task, outline=sample.outline, iterations=sample.iterations)
            results.append(
                EvalRunResult(
                    sample_id=sample.sample_id,
                    quality_score=run.quality_score,
                    stop_reason=run.stop_reason,
                    iterations_used=run.iterations_used,
                )
            )

        total = len(results)
        if total == 0:
            return EvalSummary(total_samples=0, success_rate=0.0, avg_quality_score=0.0, avg_iterations_used=0.0, results=[])

        success_count = sum(1 for item in results if item.stop_reason != "failed")
        avg_quality = sum(item.quality_score for item in results) / total
        avg_iterations = sum(item.iterations_used for item in results) / total
        return EvalSummary(
            total_samples=total,
            success_rate=round(success_count / total, 4),
            avg_quality_score=round(avg_quality, 2),
            avg_iterations_used=round(avg_iterations, 2),
            results=results,
        )
    finally:
        pipeline.close()


def main() -> None:
    summary = run_baseline_evaluation()
    print(json.dumps({**asdict(summary), "results": [asdict(item) for item in summary.results]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
