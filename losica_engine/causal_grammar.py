"""Generated morphology, realization, and analysis over learned regions."""
from __future__ import annotations

from collections import defaultdict


def derive_morphology(regions: list[dict], event_codes: dict[str, list[str]], *, dimension_limit: int = 16) -> dict:
    """Retain recurrent region ranges that occur across many lexical hosts."""
    region_by_id = {row["region_id"]: row for row in regions}
    evidence: dict[str, dict] = defaultdict(lambda: {"events": [], "hosts": set(), "before": 0, "after": 0})
    for event_id, message in event_codes.items():
        for index, region_id in enumerate(message):
            if len(message) < 2:
                continue
            host_index = index + 1 if index + 1 < len(message) else index - 1
            host = message[host_index]
            row = evidence[region_id]
            row["events"].append(event_id)
            row["hosts"].add(host)
            if index < host_index:
                row["before"] += 1
            else:
                row["after"] += 1

    partitions: dict[str, list[str]] = defaultdict(list)
    for region_id, row in evidence.items():
        if len(row["events"]) >= 12 and len(row["hosts"]) >= 6:
            partitions[region_by_id[region_id]["partition_id"]].append(region_id)
    ranked = sorted(
        partitions.items(),
        key=lambda item: (-sum(len(evidence[region_id]["hosts"]) for region_id in item[1]), item[0]),
    )
    dimensions = []
    for partition_id, region_ids in ranked:
        if len(region_ids) < 2:
            continue
        cells = []
        for region_id in sorted(region_ids):
            row = evidence[region_id]
            cells.append({
                "morphology_cell_id": f"mc:{len(dimensions)+1:03d}:{len(cells)+1:02d}",
                "source_region_id": region_id,
                "semantic_cell_id": region_by_id[region_id]["cell_id"],
                "attachment": "before" if row["before"] >= row["after"] else "after",
                "event_ids": sorted(row["events"]),
                "event_count": len(row["events"]),
                "host_region_ids": sorted(row["hosts"]),
                "host_type_count": len(row["hosts"]),
                "productivity_rule": "retained across at least 6 distinct host regions and 12 events",
            })
        dimensions.append({
            "morphology_dimension_id": f"md:{len(dimensions)+1:03d}",
            "semantic_partition_id": partition_id,
            "cells": cells,
            "selection_rule": "partition ranks by distinct host support; every retained cell meets the productivity rule",
        })
        if len(dimensions) == dimension_limit:
            break
    return {"schema": "losica-generated-morphology/1", "dimensions": dimensions}


def marker_index(morphology: dict) -> dict[str, dict]:
    return {
        cell["source_region_id"]: cell
        for dimension in morphology.get("dimensions", [])
        for cell in dimension.get("cells", [])
    }


def realize_regions(language: dict, region_ids: list[str]) -> dict:
    """Realize an ordered internal message with generated bound morphology."""
    roots = {row["semantic_region_id"]: row for row in language["lexicon"] if row.get("formation") == "learned_region_root"}
    markers = marker_index(language["morphology"])
    fossil_by_pair = {
        tuple(row["historical_analysis"]["source_region_ids"]): row
        for row in language["lexicon"] if row.get("formation") == "historical_lexicalization"
    }
    output = []
    morphemes = []
    index = 0
    while index < len(region_ids):
        pair = tuple(region_ids[index:index + 2])
        fossil = fossil_by_pair.get(pair)
        if fossil is not None:
            output.append(fossil["orthographic"])
            morphemes.append({"lexeme_id": fossil["lexeme_id"], "current_parts": [fossil["current_analysis"]["root_id"]]})
            index += 2
            continue
        region_id = region_ids[index]
        marker = markers.get(region_id)
        if marker is not None and index + 1 < len(region_ids):
            host = roots[region_ids[index + 1]]
            marker_form = marker["marker_form"]
            host_form = host["orthographic"]
            surface = marker_form + "-" + host_form if marker["attachment"] == "before" else host_form + "-" + marker_form
            output.append(surface)
            morphemes.append({
                "morphology_cell_id": marker["morphology_cell_id"],
                "marker_form": marker_form,
                "host_lexeme_id": host["lexeme_id"],
                "attachment": marker["attachment"],
            })
            index += 2
            continue
        root = roots[region_id]
        output.append(root["orthographic"])
        morphemes.append({"lexeme_id": root["lexeme_id"], "current_parts": [root["current_analysis"]["root_id"]]})
        index += 1
    return {"region_ids": list(region_ids), "words": output, "utterance": " ".join(output), "morphemes": morphemes}


def analyze_utterance(language: dict, utterance: str, *, candidate_limit: int = 8) -> dict:
    """Recover internal regions and the listener's predicted future samples."""
    exact = next((row for row in language["utterance_traces"] if row["utterance"] == utterance), None)
    if exact is None:
        roots = {
            row["orthographic"]: [row["semantic_region_id"]]
            for row in language["lexicon"] if row.get("formation") == "learned_region_root"
        }
        fossils = {
            row["orthographic"]: list(row["historical_analysis"]["source_region_ids"])
            for row in language["lexicon"] if row.get("formation") == "historical_lexicalization"
        }
        generated = {}
        markers = marker_index(language["morphology"])
        region_ids = [row["region_id"] for row in language["semantic_regions"]]
        for left in region_ids:
            for right in region_ids:
                marker = markers.get(left)
                if marker is None:
                    break
                realized = realize_regions(language, [left, right])
                if len(realized["words"]) == 1:
                    generated.setdefault(realized["words"][0], [left, right])
        parsed = []
        for word in utterance.split():
            candidates = [mapping[word] for mapping in (roots, fossils, generated) if word in mapping]
            unique = {tuple(candidate) for candidate in candidates}
            if len(unique) != 1:
                raise ValueError("surface is outside the generated compositional inventory")
            parsed.extend(next(iter(unique)))
        realized = realize_regions(language, parsed)
        if realized["utterance"] != utterance:
            raise ValueError("surface does not round-trip through generated morphology")
        exact = {"region_ids": parsed, "morphemes": realized["morphemes"]}
        analysis_basis = "compositional_generated_forms"
    else:
        analysis_basis = "attested_event"
    regions = {row["region_id"]: row for row in language["semantic_regions"]}
    decoder = language["communication"]["decoder"]
    decoded = next((
        row for row in decoder["entries"]
        if row["message_region_ids"] == exact["region_ids"]
    ), None)
    predicted = decoded["future_sample_prototype"] if decoded is not None else decoder["global_training_prototype"]
    scored = []
    for event in language["events"]:
        error = sum((a - b) ** 2 for a, b in zip(event["future"], predicted))
        scored.append((error, event["event_id"]))
    return {
        "utterance": utterance,
        "region_ids": exact["region_ids"],
        "current_morphological_analysis": exact["morphemes"],
        "analysis_basis": analysis_basis,
        "decoder_basis": "trained_message" if decoded is not None else decoder["unseen_message_policy"],
        "predicted_future_samples": [round(value, 12) for value in predicted],
        "nearest_event_ids": [event_id for _, event_id in sorted(scored)[:candidate_limit]],
        "nearest_squared_errors": [round(error, 12) for error, _ in sorted(scored)[:candidate_limit]],
    }
