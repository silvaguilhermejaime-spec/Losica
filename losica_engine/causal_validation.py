"""Validation for a finalized causal Losica language."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .causal_grammar import analyze_utterance
from .experiential_language import SCHEMA, replay_region_membership


FORBIDDEN_GENERATED_KEYS = frozenset({
    "concepticon_id", "concept_mappings", "gloss", "display", "translation",
    "reward", "success", "termination", "target_label", "oracle_state",
})


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def validate_causal_language(language: dict) -> dict:
    errors = []
    if language.get("schema") != SCHEMA:
        errors.append(f"{SCHEMA} required")
    keys = set(_walk_keys(language))
    crossed = sorted(keys & FORBIDDEN_GENERATED_KEYS)
    if crossed:
        errors.append(f"generated artifact contains forbidden semantic fields: {crossed}")

    events = language.get("events", [])
    regions = language.get("semantic_regions", [])
    lexicon = language.get("lexicon", [])
    normalizers = {row["normalizer_id"]: row for row in language.get("normalizers", [])}
    events_by_id = {row.get("event_id"): row for row in events}
    regions_by_id = {row.get("region_id"): row for row in regions}
    root_lexicon = [row for row in lexicon if row.get("formation") == "learned_region_root"]
    historical_lexicon = [row for row in lexicon if row.get("formation") == "historical_lexicalization"]
    lexemes_by_id = {row.get("lexeme_id"): row for row in lexicon}
    constructions_by_id = {row.get("construction_id"): row for row in language.get("constructions", [])}
    cells = {
        cell["cell_id"]
        for partition in language.get("semantic_partitions", [])
        for cell in partition.get("cells", [])
    }
    if len(events_by_id) != len(events) or not events:
        errors.append("event identities must be nonempty and unique")
    if len(regions_by_id) != len(regions) or not regions:
        errors.append("region identities must be nonempty and unique")
    if len({row.get("lexeme_id") for row in lexicon}) != len(lexicon):
        errors.append("lexeme identities must be unique")
    if len({row.get("form") for row in lexicon}) != len(lexicon):
        errors.append("lexical forms must be unique")
    if len(root_lexicon) != len(regions):
        errors.append("each accepted region must have exactly one root lexeme")

    replayed = 0
    for region in regions:
        trace = region.get("membership_trace", {})
        normalizer = normalizers.get(trace.get("normalizer_id"))
        if normalizer is None:
            errors.append(f"region {region.get('region_id')} lacks its normalizer")
            continue
        evidence = region.get("communication_evidence", {})
        if evidence.get("accepted") is not True:
            errors.append(f"region {region.get('region_id')} lacks accepted communication evidence")
        if evidence.get("trial_count", 0) != len(region.get("holdout_event_ids", [])):
            errors.append(f"region {region.get('region_id')} has inconsistent trial counts")
        if evidence.get("model_squared_error_sum", float("inf")) >= evidence.get("global_baseline_squared_error_sum", 0):
            errors.append(f"region {region.get('region_id')} fails its reconstruction rule")
        for event_id in region.get("train_event_ids", []) + region.get("holdout_event_ids", []):
            event = events_by_id.get(event_id)
            if event is None:
                errors.append(f"region {region.get('region_id')} names missing event {event_id}")
                continue
            try:
                replay_region_membership(region, event, normalizer)
                replayed += 1
            except ValueError as exc:
                errors.append(str(exc))

    for lexeme in lexicon:
        if not str(lexeme.get("lexeme_id", "")).startswith("lx:"):
            errors.append("lexeme identity must start with lx:")
        if lexeme.get("formation") == "learned_region_root" and lexeme.get("semantic_region_id") not in regions_by_id:
            errors.append(f"root lexeme {lexeme.get('lexeme_id')} names a missing region")
        if lexeme.get("current_analysis", {}).get("parts") != [lexeme.get("current_analysis", {}).get("root_id")]:
            errors.append(f"lexeme {lexeme.get('lexeme_id')} must be synchronically stored as one root")

    transitions = {row.get("transition_id"): row for row in language.get("history", {}).get("transitions", [])}
    for lexeme in historical_lexicon:
        historical = lexeme.get("historical_analysis", {})
        transition = transitions.get(historical.get("transition_id"))
        if transition is None:
            errors.append(f"historical lexeme {lexeme.get('lexeme_id')} lacks a replayable transition")
            continue
        if any(source not in lexemes_by_id for source in historical.get("source_lexeme_ids", [])):
            errors.append(f"historical lexeme {lexeme.get('lexeme_id')} names a missing source lexeme")
        if historical.get("construction_id") not in constructions_by_id:
            errors.append(f"historical lexeme {lexeme.get('lexeme_id')} names a missing construction")
        if transition.get("current_boundary_visible") is not False or transition.get("source_process_productive") is not False:
            errors.append(f"historical lexeme {lexeme.get('lexeme_id')} has not completed lexical reanalysis")
        if transition.get("stages", [])[-1].get("analysis") != lexeme.get("current_analysis", {}).get("parts"):
            errors.append(f"historical lexeme {lexeme.get('lexeme_id')} current analysis disagrees with its history")

    partition_cells = {
        row["partition_id"]: {cell["cell_id"] for cell in row.get("cells", [])}
        for row in language.get("semantic_partitions", [])
    }
    for dimension in language.get("morphology", {}).get("dimensions", []):
        allowed = partition_cells.get(dimension.get("semantic_partition_id"))
        if allowed is None:
            errors.append(f"morphology dimension {dimension.get('morphology_dimension_id')} names a missing partition")
            continue
        for cell in dimension.get("cells", []):
            if cell.get("semantic_cell_id") not in allowed:
                errors.append(f"morphology cell {cell.get('morphology_cell_id')} names a missing semantic cell")
            if cell.get("event_count", 0) < 12 or cell.get("host_type_count", 0) < 6:
                errors.append(f"morphology cell {cell.get('morphology_cell_id')} lacks productive distribution support")
            if not cell.get("marker_form"):
                errors.append(f"morphology cell {cell.get('morphology_cell_id')} lacks a generated form")

    for construction in language.get("constructions", []):
        if any(cell not in cells for cell in construction.get("ordered_cells", [])):
            errors.append(f"construction {construction.get('construction_id')} names a missing learned cell")
        if construction.get("joint_squared_error_sum", float("inf")) >= construction.get("constituent_baseline_squared_error_sum", 0):
            errors.append(f"construction {construction.get('construction_id')} fails its held-out reconstruction rule")

    communication = language.get("communication", {})
    if communication.get("succeeded") is not True:
        errors.append("whole-language communication gate failed")
    if communication.get("message_squared_error_sum", float("inf")) >= communication.get("global_baseline_squared_error_sum", 0):
        errors.append("messages do not improve held-out reconstruction")

    utterances = language.get("utterance_traces", [])
    if len({row.get("event_id") for row in utterances}) != len(utterances):
        errors.append("utterance trace event identities must be unique")
    for trace in utterances[::max(1, len(utterances) // 32)]:
        if not trace.get("utterance") or any(region_id not in regions_by_id for region_id in trace.get("region_ids", [])):
            errors.append(f"utterance trace {trace.get('event_id')} is not grounded in learned regions")
            continue
        try:
            analyzed = analyze_utterance(language, trace["utterance"])
            if analyzed["region_ids"] != trace["region_ids"]:
                errors.append(f"utterance trace {trace.get('event_id')} does not round-trip")
        except ValueError as exc:
            errors.append(str(exc))

    materials = language.get("causal_inputs", {})
    if len(materials.get("materials", [])) != 1 or materials["materials"][0].get("kind") != "causal_stream":
        errors.append("generation materials must contain exactly one causal stream")
    required_exclusions = {"authored_outcomes", "oracle_state", "target_specific_sensors", "pretrained_representations", "human_language_resources"}
    if not required_exclusions <= set(materials.get("excluded_kinds", [])):
        errors.append("causal manifest lacks required exclusions")

    counts = language.get("generation_trace", {}).get("output_counts", {})
    expected = {
        "events": len(events), "regions": len(regions), "lexemes": len(lexicon),
        "constructions": len(language.get("constructions", [])),
        "morphology_dimensions": len(language.get("morphology", {}).get("dimensions", [])),
        "historical_lexemes": len(historical_lexicon),
    }
    if counts != expected:
        errors.append("generation trace output counts do not match the artifact")
    if errors:
        raise ValueError("causal-language validation failed:\n" + "\n".join(errors[:50]))
    return {
        "status": "PASS",
        "events": len(events),
        "semantic_regions": len(regions),
        "lexemes": len(lexicon),
        "root_lexemes": len(root_lexicon),
        "historical_lexemes": len(historical_lexicon),
        "constructions": len(language.get("constructions", [])),
        "morphology_dimensions": len(language.get("morphology", {}).get("dimensions", [])),
        "membership_replays": replayed,
        "communication_trials": communication["holdout_trial_count"],
        "communication_wins": communication["reconstruction_win_count"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a causal Losica language")
    parser.add_argument("language")
    args = parser.parse_args(argv)
    language = json.loads(Path(args.language).read_text(encoding="utf-8"))
    print(json.dumps(validate_causal_language(language), sort_keys=True))


if __name__ == "__main__":
    main()
