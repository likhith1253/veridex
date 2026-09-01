"""Canonical benchmark registry for Sentinel evaluation datasets.

This project used to have multiple adversarial generators producing different logical
transaction namespaces. Only the canonical independent evaluator is authoritative for
record-level benchmark validation.
"""

from __future__ import annotations

from typing import Any, Iterable

CANONICAL_GROUND_TRUTH_PREFIXES = ("ADV_",)
LEGACY_GROUND_TRUTH_PREFIXES = ("EVAL_TXN_",)


def validate_ground_truth_namespace(ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Reject legacy benchmark namespaces and keep the canonical ADV_* ground truth.

    The current benchmark is defined by eval.independent_adversarial_eval.generate_adversarial_dataset(),
    which produces logical ids such as ADV_EXACT_01 and ADV_DELAYED_31. Any dataset using the legacy
    EVAL_TXN_* schema is not the canonical source of truth and must not be used to evaluate the
    current repository state.
    """
    if not isinstance(ground_truth, dict) or not ground_truth:
        raise ValueError("Benchmark ground truth is empty or invalid; canonical ADV_* dataset required.")

    keys = list(ground_truth.keys())
    canonical = any(str(key).startswith(prefix) for prefix in CANONICAL_GROUND_TRUTH_PREFIXES for key in keys)
    legacy = any(str(key).startswith(prefix) for prefix in LEGACY_GROUND_TRUTH_PREFIXES for key in keys)

    if canonical:
        return ground_truth

    if legacy:
        raise ValueError(
            "Legacy benchmark ground truth rejected: EVAL_TXN_* identifiers are not the canonical dataset. "
            "Use the ADV_* dataset from eval.independent_adversarial_eval.generate_adversarial_dataset()."
        )

    sample = next(iter(keys))
    raise ValueError(
        "Unrecognized benchmark ground truth namespace. Expected canonical ADV_* logical IDs, got "
        f"{sample!r}."
    )


def load_canonical_ground_truth(path: str = "private_ground_truth.json") -> dict[str, Any]:
    import json

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    return validate_ground_truth_namespace(data)
