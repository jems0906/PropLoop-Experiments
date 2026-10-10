from types import SimpleNamespace

import pytest

from app.outcomes import binary_confidence, computed_metrics, continuous_confidence


def test_empty_and_missing_measurements_do_not_fabricate_results():
    experiment = SimpleNamespace(assignments=[], observations=[])
    assert all(metric["baseline"] is None and metric["observed"] is None for metric in computed_metrics(experiment))
    experiment.assignments = [SimpleNamespace(subject_key="a", variant="control"), SimpleNamespace(subject_key="b", variant="treatment")]
    experiment.observations = [SimpleNamespace(subject_key="a", exposed=True, completed=True, errored=False, csat=None, duration_minutes=None)]
    metrics = computed_metrics(experiment)
    assert metrics[0]["baseline"] == 100 and metrics[0]["observed"] == 0
    assert metrics[1]["control_sample_size"] == 1 and metrics[1]["treatment_sample_size"] == 0
    assert metrics[2]["control_sample_size"] == 0
    assert metrics[3]["time_saved_minutes"] is None


def test_known_fisher_table_and_continuous_interval():
    result = binary_confidence([0] * 5, [1] * 5)
    assert result["p_value"] == pytest.approx(0.007937, abs=1e-6)
    assert result["significant"] is True
    result = continuous_confidence([40, 41, 42, 43, 44], [20, 21, 22, 23, 24])
    assert result["significant"] is True
    lo, hi = result["difference_interval_95"]
    assert lo < -20 < hi < 0
    assert not continuous_confidence([1], [2])["significant"]
    assert continuous_confidence([1, 1], [2, 2])["p_value"] is None
