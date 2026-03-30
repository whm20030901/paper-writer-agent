from paper_writer_agent.eval_samples import BASELINE_EVAL_SAMPLES


def test_day8_baseline_eval_samples_are_stable_and_minimal():
    assert len(BASELINE_EVAL_SAMPLES) >= 5
    sample_ids = {sample.sample_id for sample in BASELINE_EVAL_SAMPLES}
    assert len(sample_ids) == len(BASELINE_EVAL_SAMPLES)
    for sample in BASELINE_EVAL_SAMPLES:
        assert sample.task.strip()
        assert sample.outline.strip()
        assert sample.iterations >= 1
