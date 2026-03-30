from types import SimpleNamespace

from paper_writer_agent.eval_samples import EvalSample
from paper_writer_agent.evaluation_runner import run_baseline_evaluation


def test_run_baseline_evaluation_aggregates_summary(monkeypatch):
    class FakePipeline:
        def __init__(self):
            self.calls = 0

        def run(self, task: str, outline: str, iterations: int):
            self.calls += 1
            return SimpleNamespace(
                quality_score=7 + (self.calls % 2),
                stop_reason="quality_threshold_reached" if self.calls == 1 else "max_iterations_reached",
                iterations_used=iterations,
            )

        def close(self):
            return None

    monkeypatch.setattr("paper_writer_agent.evaluation_runner.bootstrap_pipeline", lambda: FakePipeline())

    samples = [
        EvalSample(sample_id="s1", task="t1", outline="o1", iterations=2),
        EvalSample(sample_id="s2", task="t2", outline="o2", iterations=3),
    ]
    summary = run_baseline_evaluation(samples)

    assert summary.total_samples == 2
    assert summary.success_rate == 1.0
    assert 0 <= summary.avg_quality_score <= 10
    assert summary.avg_iterations_used == 2.5
    assert [item.sample_id for item in summary.results] == ["s1", "s2"]
