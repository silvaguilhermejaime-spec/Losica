#!/usr/bin/env python3
"""Acceptance tests for replayable lexical membership generation."""
from __future__ import annotations

import pytest

from losica_engine.display_en import load_english_display_labels
from losica_engine.full_language import (
    generate_complete_language,
    remove_presentation_fields,
    replay_generation,
)
from losica_engine.semantic_network import replay_membership
from losica_engine.typology import load_snapshot


MEMBERSHIP_FIELDS = {
    "algorithm",
    "evidence_edge_ids",
    "seed",
    "draw",
    "threshold",
    "accepted",
}
SEEDS = (0, 1, 19020, 4294967295)


@pytest.fixture(scope="module")
def evidence():
    return load_snapshot()


@pytest.fixture(scope="module")
def state(evidence):
    return generate_complete_language(
        seed=19020,
        evidence=evidence,
        display_labels=load_english_display_labels(),
        vocabulary_scale="core",
    )


def lexical_memberships(state):
    return [
        mapping
        for lexeme in state["lexicon"]
        for mapping in lexeme.get("concept_mappings", [])
    ]


def test_membership_replay(state, evidence):
    memberships = lexical_memberships(state)
    assert memberships
    for membership in memberships:
        record = membership["membership_record"]
        assert set(record) == MEMBERSHIP_FIELDS
        assert record["algorithm"] == "colex-region-v1"
        assert replay_membership(record, evidence) == record["accepted"]

    rejected = {
        "algorithm": "colex-region-v1",
        "evidence_edge_ids": [],
        "seed": 19020,
        "draw": 0.75,
        "threshold": 0.25,
        "accepted": False,
    }
    assert replay_membership(rejected, evidence) is False


def test_display_labels_are_independent_generation_input(evidence):
    english = load_english_display_labels()
    sequential = {
        key: f"label-{index:04d}"
        for index, key in enumerate(sorted(english), 1)
    }
    label_sets = (english, sequential, {})
    for seed in SEEDS:
        generated = [
            generate_complete_language(
                seed=seed,
                evidence=evidence,
                display_labels=labels,
                vocabulary_scale="core",
            )
            for labels in label_sets
        ]
        canonical = [remove_presentation_fields(language) for language in generated]
        assert canonical[0] == canonical[1] == canonical[2]


def test_internal_identifiers(state):
    assert all(lexeme["lexeme_id"].startswith("lx:") for lexeme in state["lexicon"])
    roots = [
        lexeme
        for lexeme in state["lexicon"]
        if lexeme.get("formation") == "semantic_region_lexicalization"
    ]
    assert roots
    assert all(lexeme["semantic_region_id"].startswith("sr:") for lexeme in roots)

    for system_name in ("reference_system", "agreement_system"):
        system = state["profile"][system_name]
        assert system["partition_id"].startswith("sp:")
        assert system["cells"]
        assert all(cell["cell_id"].startswith("sc:") for cell in system["cells"])
        assert all(cell["partition_id"] == system["partition_id"] for cell in system["cells"])


def test_concepticon_links(state):
    memberships = lexical_memberships(state)
    assert memberships
    for membership in memberships:
        assert membership["links"]
        for link in membership["links"]:
            assert link == {
                "namespace": "concepticon",
                "object_id": membership["concepticon_id"],
            }


def test_morphology_partition_references(state):
    partitions = {
        partition["partition_id"]: set(partition["cell_ids"])
        for partition in state["morphology"]["meaning_partitions"]
    }
    assert partitions
    assert all(partition_id.startswith("sp:") for partition_id in partitions)
    for cell in state["morphology"]["cells"]:
        assert cell["cell_id"].startswith("sc:")
        assert cell["cell_id"] in partitions[cell["partition_id"]]
    for lexeme_id, paradigm in state["paradigms"].items():
        if lexeme_id in {"sample_noun", "sample_verb"}:
            continue
        for form in paradigm:
            for reference in form["meaning_cells"]:
                assert reference["cell_id"] in partitions[reference["partition_id"]]


def test_full_generation_replay(state, evidence):
    record = state["generation_record"]
    assert record["seed"] == 19020
    assert 19020 in record["seeds"]
    assert record["evidence_ids"]
    assert record["decisions"]
    assert all(set(decision) == MEMBERSHIP_FIELDS for decision in record["decisions"])
    assert replay_generation(record, evidence) == remove_presentation_fields(state)
