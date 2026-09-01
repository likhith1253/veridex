import pytest

from eval.independent_adversarial_eval import generate_adversarial_dataset
from eval.benchmark_registry import validate_ground_truth_namespace


def test_independent_dataset_uses_canonical_adv_namespace():
    dataset = generate_adversarial_dataset()
    ground_truth = dataset["ground_truth"]

    assert ground_truth
    assert len(ground_truth) == 100
    assert sum(1 for item in ground_truth.values() if item.get("expected_exception")) == 46


def test_legacy_evaluation_dataset_is_rejected():
    legacy_ground_truth = {
        "EVAL_TXN_0000": {
            "logical_id": "EVAL_TXN_0000",
            "scenario": "exact_match",
            "expected_outcome": "exact_match",
        }
    }

    with pytest.raises(ValueError, match="legacy|ADV_"):
        validate_ground_truth_namespace(legacy_ground_truth)
