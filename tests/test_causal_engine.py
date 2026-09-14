from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from losica_engine.causal_adapter import build_alignment, external_to_losica, losica_to_external
from losica_engine.causal_grammar import analyze_utterance, realize_regions
from losica_engine.causal_attestation import verify_collection_attestation
from losica_engine.causal_stream import CausalBoundaryError, causal_stream_sha256, validate_causal_stream
from losica_engine.causal_validation import validate_causal_language
from losica_engine.causal_use import event_utterance
from losica_engine.experiential_language import (
    canonical_causal_language,
    generate_builtin_stream,
    generate_causal_language,
    replay_causal_generation,
    replay_region_membership,
)


@pytest.fixture(scope="module")
def stream():
    return generate_builtin_stream(19020)


@pytest.fixture(scope="module")
def language(stream):
    return generate_causal_language(seed=19020, stream=stream, vocabulary_scale="core")


@pytest.mark.parametrize("key", [
    "english_label", "reward", "success", "termination", "episode_boundary",
    "oracle_state", "target_molecule", "pretrained_checkpoint", "object_class",
])
def test_interpreted_input_fields_fail_closed(stream, key):
    bad = copy.deepcopy(stream)
    bad[key] = 1
    with pytest.raises(CausalBoundaryError):
        validate_causal_stream(bad)


def test_stream_contains_only_numeric_samples_controls_time_and_offsets(stream):
    assert set(stream) == {"schema", "frames", "source_sha256"}
    assert all(set(frame) == {"t", "samples", "controls", "source_offset"} for frame in stream["frames"])
    assert all(isinstance(value, float) for frame in stream["frames"] for value in frame["samples"] + frame["controls"])


def test_collection_gate_accepts_general_transducers_and_rejects_target_sensors(stream):
    base = {
        "schema": "losica-collection-attestation/1",
        "source_sha256": stream["source_sha256"],
        "input_kind": "mixed_general_transducers",
        "selection_basis": "physical_channel_without_named_target",
        "generation_projection": "samples_controls_time_offsets_only",
        "reviewer_record": "audit:fixture:1",
    }
    assert verify_collection_attestation(base, source_sha256=stream["source_sha256"]) == base
    targeted = dict(base, input_kind="molecular_target_sensor")
    with pytest.raises(ValueError):
        verify_collection_attestation(targeted, source_sha256=stream["source_sha256"])


def test_persistent_multistep_events_are_learned(language):
    assert len(language["events"]) > 500
    assert all(len(event["sample_indexes"]) == 6 for event in language["events"])
    assert all(len(event["future_sample_indexes"]) == 4 for event in language["events"])
    assert all(max(event["sample_indexes"]) < min(event["future_sample_indexes"]) for event in language["events"])
    assert all(len(event["source_offsets"]) == 6 for event in language["events"])
    assert all(len(event["future_source_offsets"]) == 4 for event in language["events"])


def test_every_region_is_heldout_reconstruction_supported(language):
    normalizer = language["normalizers"][0]
    by_event = {event["event_id"]: event for event in language["events"]}
    for region in language["semantic_regions"]:
        evidence = region["communication_evidence"]
        assert evidence["accepted"] is True
        assert evidence["trial_count"] == len(region["holdout_event_ids"])
        assert evidence["model_squared_error_sum"] < evidence["global_baseline_squared_error_sum"]
        for event_id in (region["train_event_ids"] + region["holdout_event_ids"])[::17]:
            assert replay_region_membership(region, by_event[event_id], normalizer) is True


def test_receiver_reconstructs_samples_instead_of_region_ids(language):
    report = language["communication"]
    assert report["target"] == "withheld_future_transducer_samples"
    assert report["message_squared_error_sum"] < report["global_baseline_squared_error_sum"]
    assert 0 <= report["reconstruction_win_count"] <= report["holdout_trial_count"]
    assert report["message_available_count"] <= report["holdout_trial_count"]
    train_ids = {event["event_id"] for event in language["events"] if event["split"] == "train"}
    assert report["decoder"]["algorithm_id"] == "exact-message-training-prototype-v1"
    assert all(
        set(entry["train_event_ids"]) <= train_ids
        for entry in report["decoder"]["entries"]
    )


def test_generated_utterance_uses_only_internal_lexemes(language):
    result = event_utterance(language, language["events"][0]["event_id"])
    assert result["region_ids"]
    assert result["morphemes"]
    assert result["utterance"] == " ".join(result["words"])
    assert analyze_utterance(language, result["utterance"])["region_ids"] == result["region_ids"]


def test_generated_root_form_has_compositional_inverse(language):
    region_id = language["semantic_regions"][0]["region_id"]
    realization = realize_regions(language, [region_id])
    analysis = analyze_utterance(language, realization["utterance"])
    assert analysis["region_ids"] == [region_id]
    assert analysis["analysis_basis"] == "compositional_generated_forms"


def test_vocabulary_identity_and_size_are_internal(language):
    roots = [row for row in language["lexicon"] if row["formation"] == "learned_region_root"]
    assert len(roots) == 256
    assert len(language["lexicon"]) >= 256
    assert len(language["semantic_regions"]) == 256
    assert all(row["lexeme_id"].startswith("lx:") for row in language["lexicon"])
    assert all(row["semantic_region_id"].startswith("sr:") for row in language["lexicon"])
    assert not any("concepticon_id" in row or "concept_mappings" in row for row in language["lexicon"])


def test_generated_partitions_feed_constructions_and_lexical_distribution(language):
    partitions = {row["partition_id"] for row in language["semantic_partitions"]}
    cells = {cell["cell_id"] for row in language["semantic_partitions"] for cell in row["cells"]}
    assert partitions and language["constructions"]
    roots = [row for row in language["lexicon"] if row["formation"] == "learned_region_root"]
    assert all(row["distribution"]["licensed_partition_id"] in partitions for row in roots)
    assert all(set(row["ordered_cells"]) <= cells for row in language["constructions"])
    assert all(row["joint_squared_error_sum"] < row["constituent_baseline_squared_error_sum"] for row in language["constructions"])


def test_no_fixed_grammar_inventory_is_generated(language):
    forbidden = {"SG", "PL", "POS", "NEG", "IPFV", "PFV", "NPST", "PST", "FUT", "IND", "IMP"}
    values = set()
    stack = [language]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
        elif isinstance(value, str):
            values.add(value)
    assert not forbidden & values


def test_adapter_is_downstream_and_has_zero_causal_effect(language):
    before = canonical_causal_language(language)
    adapter = build_alignment(language, [{
        "external_id": "external:1",
        "expression": "arbitrary display text",
        "source_offset_ranges": [[0, 0]],
    }], namespace="test")
    assert adapter["records"][0]["expression"] == "arbitrary display text"
    assert adapter["records"][0]["region_ids"]
    assert adapter["records"][0]["evidence_event_ids"] == ["ev:000001"]
    renamed = build_alignment(language, [{
        "external_id": "external:1",
        "expression": "wholly replaced symbols",
        "source_offset_ranges": [[0, 0]],
    }], namespace="test")
    assert renamed["records"][0]["region_ids"] == adapter["records"][0]["region_ids"]
    assert canonical_causal_language(language) == before


def test_adapter_rejects_human_assigned_region_meanings(language):
    with pytest.raises(ValueError, match="region_ids are derived"):
        build_alignment(language, [{
            "external_id": "external:manual",
            "expression": "manual meaning",
            "region_ids": [language["semantic_regions"][0]["region_id"]],
            "source_offset_ranges": [[0, 0]],
        }], namespace="test")


def test_generated_morphology_consumes_learned_partitions(language):
    partitions = {row["partition_id"]: {cell["cell_id"] for cell in row["cells"]} for row in language["semantic_partitions"]}
    assert language["morphology"]["dimensions"]
    for dimension in language["morphology"]["dimensions"]:
        assert dimension["semantic_partition_id"] in partitions
        for cell in dimension["cells"]:
            assert cell["semantic_cell_id"] in partitions[dimension["semantic_partition_id"]]
            assert cell["event_count"] >= 12
            assert cell["host_type_count"] >= 6
            assert cell["marker_form"]


def test_fossilized_forms_separate_current_and_historical_analysis(language):
    fossils = [row for row in language["lexicon"] if row["formation"] == "historical_lexicalization"]
    assert fossils
    transitions = {row["transition_id"]: row for row in language["history"]["transitions"]}
    for lexeme in fossils:
        assert lexeme["current_analysis"]["parts"] == [lexeme["current_analysis"]["root_id"]]
        assert len(lexeme["historical_analysis"]["source_lexeme_ids"]) == 2
        transition = transitions[lexeme["historical_analysis"]["transition_id"]]
        assert transition["current_boundary_visible"] is False
        assert transition["source_process_productive"] is False


def test_external_translation_uses_separate_adapter(language):
    trace = language["utterance_traces"][0]
    before = canonical_causal_language(language)
    adapter = build_alignment(language, [
        {"external_id": "sentence:1", "expression": "shared human sentence", "source_offset_ranges": [[0, 0]]},
        {"external_id": "sentence:2", "expression": "shared alternate wording", "source_offset_ranges": [[0, 0]]},
        {"external_id": "sentence:3", "expression": "contrast record first", "source_offset_ranges": [[1000, 1000]]},
        {"external_id": "sentence:4", "expression": "contrast record second", "source_offset_ranges": [[1000, 1000]]},
    ], namespace="human-test")
    outward = external_to_losica(language, adapter, "shared human sentence")
    generalized = external_to_losica(language, adapter, "shared")
    inward = losica_to_external(language, adapter, trace["utterance"])
    assert outward["realizations"][0]["region_ids"] == trace["region_ids"]
    assert outward["coverage"]["covered_token_count"] == 3
    assert generalized["coverage"] == {
        "covered_token_count": 1,
        "total_token_count": 1,
        "coverage_ratio": 1.0,
        "measurement_rule": "tokens covered by the longest learned one-to-four-token units",
    }
    assert generalized["realizations"][0]["region_ids"]
    assert inward["external_candidates"][0]["external_id"] == "sentence:1"
    assert canonical_causal_language(language) == before
    with pytest.raises(KeyError, match="1/3 tokens covered; at least 80% required"):
        external_to_losica(language, adapter, "shared unseen wording")


def test_repeated_exact_expression_uses_compact_learned_region(language):
    adapter = build_alignment(language, [
        {"external_id": "repeat:1", "expression": "repeated signal", "source_offset_ranges": [[0, 0]]},
        {"external_id": "repeat:2", "expression": "repeated signal", "source_offset_ranges": [[0, 0]]},
        {"external_id": "contrast:1", "expression": "contrast wording", "source_offset_ranges": [[1000, 1000]]},
        {"external_id": "contrast:2", "expression": "contrast wording", "source_offset_ranges": [[1000, 1000]]},
    ], namespace="human-test")
    result = external_to_losica(language, adapter, "repeated signal")
    assert result["coverage"]["measurement_rule"] == "repeated time-aligned one-to-four-token units"
    assert len(result["realizations"]) == 1
    assert 1 <= len(result["realizations"][0]["region_ids"]) <= 2
    assert result["realizations"][0]["external_ids"] == ["repeat:1", "repeat:2"]
    inverse = losica_to_external(language, adapter, result["realizations"][0]["utterance"])
    assert inverse["external_candidates"][0]["expression"] == "repeated signal"


def test_generation_replays_exactly(language, stream):
    replayed = replay_causal_generation(language["generation_trace"], stream)
    assert canonical_causal_language(replayed) == canonical_causal_language(language)


def test_numeric_input_change_changes_generation_identity(stream):
    changed = copy.deepcopy(stream)
    changed.pop("source_sha256")
    changed["frames"][20]["samples"][0] += 0.125
    changed = validate_causal_stream(changed)
    assert causal_stream_sha256(changed) != causal_stream_sha256(stream)


def test_full_validator(language):
    result = validate_causal_language(language)
    assert result["status"] == "PASS"
    assert result["semantic_regions"] == 256
    assert result["communication_trials"] > 0


def test_generated_language_matches_release_schema(language):
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "causal-language.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(language, schema)
