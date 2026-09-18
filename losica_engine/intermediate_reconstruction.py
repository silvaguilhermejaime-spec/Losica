"""Validated evidence constraints for intermediate Losican reconstruction."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .validation import identifier, keys, label, read_json, require, strings, text


@dataclass(frozen=True)
class SegmentConstraint:
    segment: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class LineageConstraints:
    branch_id: str
    stage: str
    descendant: str
    reconstruction_status: str
    required_consonants: tuple[SegmentConstraint, ...]
    required_vowels: tuple[SegmentConstraint, ...]
    unconstrained_proto_consonants: tuple[str, ...]
    unconstrained_proto_vowels: tuple[str, ...]
    simultaneous_inventory_status: str
    absolute_chronology_status: str
    scope_note: str


@dataclass(frozen=True)
class IntermediateReconstruction:
    schema: str
    claim_type: str
    lineages: Mapping[str, LineageConstraints]


def _constraint(value, context):
    keys(value, {"segment", "evidence"}, context=context)
    return SegmentConstraint(
        text(value["segment"], f"{context} segment"),
        strings(value["evidence"], f"{context} evidence", max_items=16),
    )


def _validate_evidence(reference, branch, historical_examples, context):
    parts = reference.split(":")
    require(len(parts) >= 2, f"{context}: malformed evidence reference {reference!r}")
    if parts[0] == "rule":
        require(len(parts) == 2, f"{context}: malformed rule reference {reference!r}")
        require(parts[1] in {rule.id for rule in branch.rules},
                f"{context}: unknown branch rule {parts[1]!r}")
        return
    if parts[0] == "example":
        require(len(parts) == 3, f"{context}: malformed example reference {reference!r}")
        require(historical_examples is not None,
                f"{context}: historical worked-example register required for example evidence")
        entries = {entry.id: entry for entry in historical_examples.entries}
        require(parts[1] in entries, f"{context}: unknown historical example {parts[1]!r}")
        require(parts[2] == branch.id, f"{context}: example evidence belongs to another branch")
        require(entries[parts[1]].attestations[branch.id].status == "attested",
                f"{context}: example evidence is missing in branch {branch.id}")
        return
    require(False, f"{context}: evidence kind must be rule or example")


def _lineage(value, family_history, historical_examples):
    keys(
        value,
        {
            "branch_id", "stage", "descendant", "reconstruction_status",
            "required_historical_segments", "unconstrained_proto_segments",
            "simultaneous_inventory_status", "absolute_chronology_status",
            "scope_note",
        },
        context="intermediate lineage",
    )
    branch_id = identifier(value["branch_id"], "intermediate lineage branch_id")
    require(branch_id in family_history.branches, f"unknown family branch {branch_id!r}")
    branch = family_history.branches[branch_id]
    require(value["stage"] == branch.ancestor, f"lineage {branch_id}: stage disagrees with family history")
    require(value["descendant"] == branch.descendant,
            f"lineage {branch_id}: descendant disagrees with family history")
    require(value["reconstruction_status"] == "constraint_only",
            f"lineage {branch_id}: reconstruction_status must be constraint_only")

    required = value["required_historical_segments"]
    keys(required, {"consonants", "vowels"}, context=f"lineage {branch_id} required segments")
    require(isinstance(required["consonants"], list) and isinstance(required["vowels"], list),
            f"lineage {branch_id}: required segment lists required")
    consonants = tuple(
        _constraint(item, f"lineage {branch_id} consonant constraint")
        for item in required["consonants"]
    )
    vowels = tuple(
        _constraint(item, f"lineage {branch_id} vowel constraint")
        for item in required["vowels"]
    )
    for kind, constraints, proto_inventory in (
        ("consonant", consonants, set(family_history.proto_consonants)),
        ("vowel", vowels, set(family_history.proto_vowels)),
    ):
        segments = [item.segment for item in constraints]
        require(len(segments) == len(set(segments)),
                f"lineage {branch_id}: duplicate required {kind}")
        require(set(segments) <= proto_inventory,
                f"lineage {branch_id}: required {kind} outside Proto inventory")
        for item in constraints:
            require(item.evidence, f"lineage {branch_id}: {item.segment} requires evidence")
            for reference in item.evidence:
                _validate_evidence(
                    reference,
                    branch,
                    historical_examples,
                    f"lineage {branch_id} segment {item.segment}",
                )

    unconstrained = value["unconstrained_proto_segments"]
    keys(unconstrained, {"consonants", "vowels"}, context=f"lineage {branch_id} unconstrained segments")
    unconstrained_consonants = strings(
        unconstrained["consonants"],
        f"lineage {branch_id} unconstrained consonants",
    )
    unconstrained_vowels = strings(
        unconstrained["vowels"],
        f"lineage {branch_id} unconstrained vowels",
    )
    require(
        set(unconstrained_consonants)
        == set(family_history.proto_consonants) - {item.segment for item in consonants},
        f"lineage {branch_id}: unconstrained consonants must be the exact Proto complement",
    )
    require(
        set(unconstrained_vowels)
        == set(family_history.proto_vowels) - {item.segment for item in vowels},
        f"lineage {branch_id}: unconstrained vowels must be the exact Proto complement",
    )
    require(value["simultaneous_inventory_status"] == "unresolved",
            f"lineage {branch_id}: simultaneous inventory must remain unresolved")
    require(value["absolute_chronology_status"] == "unresolved",
            f"lineage {branch_id}: absolute chronology must remain unresolved")

    return LineageConstraints(
        branch_id,
        label(value["stage"], f"lineage {branch_id} stage"),
        label(value["descendant"], f"lineage {branch_id} descendant"),
        value["reconstruction_status"],
        consonants,
        vowels,
        unconstrained_consonants,
        unconstrained_vowels,
        value["simultaneous_inventory_status"],
        value["absolute_chronology_status"],
        text(value["scope_note"], f"lineage {branch_id} scope_note"),
    )


def load_intermediate_reconstruction(path, family_history, historical_examples=None):
    data = read_json(path)
    keys(data, {"schema", "claim_type", "lineages"}, context="intermediate reconstruction")
    schema = text(data["schema"], "intermediate reconstruction schema")
    require(schema == "losica-intermediate-constraints/1",
            "unsupported intermediate reconstruction schema")
    claim_type = text(data["claim_type"], "intermediate reconstruction claim_type")
    require(claim_type == "diachronic_lineage_constraints",
            "intermediate reconstruction must contain diachronic lineage constraints")
    require(isinstance(data["lineages"], list), "intermediate lineages must be a list")
    rows = tuple(
        _lineage(value, family_history, historical_examples)
        for value in data["lineages"]
    )
    lineages = {row.branch_id: row for row in rows}
    require(len(lineages) == len(rows), "duplicate intermediate lineage branch_id")
    require(set(lineages) == set(family_history.branches),
            "intermediate reconstruction must cover every family branch")
    return IntermediateReconstruction(schema, claim_type, MappingProxyType(lineages))
