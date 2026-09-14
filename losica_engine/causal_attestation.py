"""Pre-generation gate for facts that numeric bytes cannot prove about a sensor."""
from __future__ import annotations

import json
from pathlib import Path


SCHEMA = "losica-collection-attestation/1"
ALLOWED_INPUT_KINDS = frozenset({
    "general_optical_array",
    "general_acoustic_array",
    "general_mechanical_array",
    "general_electrical_array",
    "mixed_general_transducers",
})


def verify_collection_attestation(value: dict, *, source_sha256: str) -> dict:
    required = {
        "schema", "source_sha256", "input_kind", "selection_basis",
        "generation_projection", "reviewer_record",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("collection attestation has an invalid field set")
    if value["schema"] != SCHEMA:
        raise ValueError(f"{SCHEMA} required")
    if value["source_sha256"] != source_sha256:
        raise ValueError("attestation source digest does not match the causal stream")
    if value["input_kind"] not in ALLOWED_INPUT_KINDS:
        raise ValueError("input_kind is outside the general-transducer allowlist")
    if value["selection_basis"] != "physical_channel_without_named_target":
        raise ValueError("selection_basis must identify a general physical channel")
    if value["generation_projection"] != "samples_controls_time_offsets_only":
        raise ValueError("generation projection does not match losica-causal-stream/1")
    reviewer = value["reviewer_record"]
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer_record must identify the collection audit")
    return dict(value)


def load_collection_attestation(path: str | Path, *, source_sha256: str) -> dict:
    return verify_collection_attestation(
        json.loads(Path(path).read_text(encoding="utf-8")),
        source_sha256=source_sha256,
    )
