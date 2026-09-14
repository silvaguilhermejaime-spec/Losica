"""Generated participant-reference and agreement partitions."""
from __future__ import annotations

import random

from .semantic_core import meaning_cell_id, meaning_partition_id


def _cell(cell_id: str, *, speaker: str, addressee: str, cardinality: dict) -> dict:
    return {
        "cell_id": cell_id,
        "condition": {
            "speaker_membership": speaker,
            "addressee_membership": addressee,
            "cardinality": cardinality,
        },
    }


def _partition(system_id: str, cells: list[dict], kind: str) -> dict:
    partition_id = meaning_partition_id(f"{kind}-{system_id}")
    normalized = []
    for index, cell in enumerate(cells):
        normalized.append({
            **cell,
            "cell_id": meaning_cell_id(f"{kind}-{system_id}-{index:04d}"),
            "partition_id": partition_id,
        })
    return {"system_id": system_id, "partition_id": partition_id, "cells": normalized}


def _three_by_two() -> list[dict]:
    return [
        _cell("R0", speaker="required", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R1", speaker="forbidden", addressee="required", cardinality={"exact": 1}),
        _cell("R2", speaker="forbidden", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R3", speaker="required", addressee="unconstrained", cardinality={"minimum": 2}),
        _cell("R4", speaker="forbidden", addressee="required", cardinality={"minimum": 2}),
        _cell("R5", speaker="forbidden", addressee="forbidden", cardinality={"minimum": 2}),
    ]


def _clusive() -> list[dict]:
    return [
        _cell("R0", speaker="required", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R1", speaker="forbidden", addressee="required", cardinality={"exact": 1}),
        _cell("R2", speaker="forbidden", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R3", speaker="required", addressee="required", cardinality={"minimum": 2}),
        _cell("R4", speaker="required", addressee="forbidden", cardinality={"minimum": 2}),
        _cell("R5", speaker="forbidden", addressee="required", cardinality={"minimum": 2}),
        _cell("R6", speaker="forbidden", addressee="forbidden", cardinality={"minimum": 2}),
    ]


def _number_neutral() -> list[dict]:
    return [
        _cell("R0", speaker="required", addressee="forbidden", cardinality={"minimum": 1}),
        _cell("R1", speaker="forbidden", addressee="required", cardinality={"minimum": 1}),
        _cell("R2", speaker="forbidden", addressee="forbidden", cardinality={"minimum": 1}),
    ]


def _dual_clusive() -> list[dict]:
    cells = [
        _cell("R0", speaker="required", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R1", speaker="forbidden", addressee="required", cardinality={"exact": 1}),
        _cell("R2", speaker="forbidden", addressee="forbidden", cardinality={"exact": 1}),
        _cell("R3", speaker="required", addressee="required", cardinality={"exact": 2}),
        _cell("R4", speaker="required", addressee="forbidden", cardinality={"exact": 2}),
        _cell("R5", speaker="forbidden", addressee="required", cardinality={"exact": 2}),
        _cell("R6", speaker="forbidden", addressee="forbidden", cardinality={"exact": 2}),
        _cell("R7", speaker="required", addressee="required", cardinality={"minimum": 3}),
        _cell("R8", speaker="required", addressee="forbidden", cardinality={"minimum": 3}),
        _cell("R9", speaker="forbidden", addressee="required", cardinality={"minimum": 3}),
        _cell("R10", speaker="forbidden", addressee="forbidden", cardinality={"minimum": 3}),
    ]
    return cells


REFERENCE_ARCHITECTURES = {
    "REF-A": _three_by_two,
    "REF-B": _clusive,
    "REF-C": _dual_clusive,
    "REF-D": _number_neutral,
}
REFERENCE_WEIGHTS = [0.35, 0.35, 0.15, 0.15]


def sample_reference_system(rng: random.Random, seed: int) -> tuple[dict, dict]:
    ids = list(REFERENCE_ARCHITECTURES)
    chosen = rng.choices(ids, weights=REFERENCE_WEIGHTS, k=1)[0]
    cells = REFERENCE_ARCHITECTURES[chosen]()
    system = _partition(chosen, cells, "reference")
    decision = {
        "feature": "participant_reference_partition",
        "value": chosen,
        "source": "Losica typological prior",
        "source_ids": ["LOSICA-REF-PARTITION-01"],
        "candidate_values": ids,
        "weights": REFERENCE_WEIGHTS,
        "sampling_method": "categorical reference-partition prior",
        "seed": seed,
        "evidence_kind": "typological_prior",
        "inference_kind": "statistical_inference",
        "choice_kind": "generated_choice",
    }
    return system, decision


def sample_agreement_system(rng: random.Random, seed: int, reference_system: dict, enabled: bool) -> tuple[dict, dict]:
    if not enabled:
        system = _partition("AGR-0", [{"cell_id": "A0", "condition": {"any": True}}], "agreement")
        weights = [1.0]
        candidates = ["AGR-0"]
    else:
        candidates = ["AGR-R", "AGR-P", "AGR-0"]
        weights = [0.55, 0.30, 0.15]
        chosen = rng.choices(candidates, weights=weights, k=1)[0]
        if chosen == "AGR-R":
            cells = [{"cell_id": f"A{i}", "condition": dict(cell["condition"])} for i, cell in enumerate(reference_system["cells"])]
        elif chosen == "AGR-P":
            cells = [
                {"cell_id": "A0", "condition": {"speaker_membership": "required"}},
                {"cell_id": "A1", "condition": {"speaker_membership": "forbidden", "addressee_membership": "required"}},
                {"cell_id": "A2", "condition": {"speaker_membership": "forbidden", "addressee_membership": "forbidden"}},
            ]
        else:
            cells = [{"cell_id": "A0", "condition": {"any": True}}]
        system = _partition(chosen, cells, "agreement")
    decision = {
        "feature": "subject_index_partition",
        "value": system["system_id"],
        "source": "Losica typological prior",
        "source_ids": ["LOSICA-AGR-PARTITION-01"],
        "candidate_values": candidates,
        "weights": weights,
        "sampling_method": "categorical agreement-partition prior",
        "seed": seed,
        "evidence_kind": "typological_prior",
        "inference_kind": "statistical_inference",
        "choice_kind": "generated_choice",
    }
    return system, decision


def reference_value(*, speaker: str, addressee: str, cardinality: int | None = None, minimum: int | None = None) -> dict:
    card = {"exact": cardinality} if cardinality is not None else {"minimum": minimum or 1}
    return {"speaker_membership": speaker, "addressee_membership": addressee, "cardinality": card}


def _membership_compatible(value: str, required: str) -> bool:
    if required == "unconstrained":
        return True
    if value == "unknown":
        return True
    return value == required


def _cardinality_compatible(value: dict, required: dict) -> bool:
    if "exact" in value:
        n = value["exact"]
        if "exact" in required:
            return n == required["exact"]
        return n >= required.get("minimum", 1)
    if "minimum" in value:
        minimum = value["minimum"]
        if "exact" in required:
            return required["exact"] >= minimum
        return True
    return True


def condition_matches(value: dict, condition: dict) -> bool:
    if condition.get("any"):
        return True
    return (
        _membership_compatible(value.get("speaker_membership", "unknown"), condition.get("speaker_membership", "unconstrained"))
        and _membership_compatible(value.get("addressee_membership", "unknown"), condition.get("addressee_membership", "unconstrained"))
        and _cardinality_compatible(value.get("cardinality", {"minimum": 1}), condition.get("cardinality", {"minimum": 1}))
    )


def resolve_cell(value: dict, cells: list[dict]) -> str:
    matches = [cell["cell_id"] for cell in cells if condition_matches(value, cell["condition"])]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"reference value is outside generated partition: {value!r}")
    raise ValueError(f"reference value is underspecified for generated partition; matching cells={matches}")
