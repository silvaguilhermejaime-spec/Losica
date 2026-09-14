"""Language induction from unnamed continuous experience.

This module is the causal generator.  Human-language resources and typological
questionnaires are not imported here.  The listener is trained and evaluated on
recovery of withheld numeric samples, not on recovery of a supplied class ID.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import copy
import hashlib
import json
import math
import random
from pathlib import Path

from .causal_stream import (
    causal_stream_sha256,
    generation_materials,
    load_causal_stream,
    make_causal_stream,
    validate_causal_stream,
)
from .causal_attestation import load_collection_attestation
from .causal_grammar import derive_morphology, realize_regions
from .causal_history import lexicalize_constructions
from .config import load_phonology
from .lexicon_v021 import FormAllocator
from .morphophonology import prominence_index


SCHEMA = "losica-causal-language/1"
ALGORITHM = "losica-causal-induction-v1"
VOCABULARY_SCALES = {"core": 256, "intermediate": 512, "large": 1024}
DEFAULT_PHONOLOGY = Path(__file__).resolve().parents[1] / "config" / "preproto.json"


def _stable_digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _mean(rows: list[list[float]]) -> list[float]:
    if not rows:
        return []
    return [sum(row[i] for row in rows) / len(rows) for i in range(len(rows[0]))]


def _sse(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, int(fraction * len(ordered))))
    return ordered[position]


def generate_builtin_stream(seed: int, frame_count: int = 4096) -> dict:
    """Create a deterministic numeric stream with persistent, controllable change.

    Its exported records contain only samples, controls, time, and offsets.  The
    recurrence supplies a package fixture; external deployments can pass recorded
    streams through the same schema.
    """
    if frame_count < 256:
        raise ValueError("frame_count must be at least 256")
    rng = random.Random(seed ^ 0x43415553414C)
    width, control_width = 12, 4
    x = [rng.uniform(-0.4, 0.4) for _ in range(width)]
    u = [0.0] * control_width
    frames = []
    for tick in range(frame_count):
        if tick % 11 == 0:
            u = [rng.uniform(-1.0, 1.0) for _ in range(control_width)]
        previous = list(x)
        for index in range(width):
            left = previous[(index - 1) % width]
            right = previous[(index + 1) % width]
            drive = u[index % control_width]
            slow = math.sin((tick + 1) * (index + 2) / 97.0)
            noise = rng.uniform(-0.018, 0.018)
            x[index] = math.tanh(0.88 * previous[index] + 0.08 * left - 0.04 * right + 0.12 * drive + 0.025 * slow + noise)
        frames.append({
            "t": tick / 20.0,
            "samples": [round(value, 9) for value in x],
            "controls": [round(value, 9) for value in u],
            "source_offset": tick,
        })
    return make_causal_stream(frames)


def _event_descriptor(frames: list[dict], start: int, width: int, horizon: int) -> tuple[list[float], list[float]]:
    observed = frames[start:start + width]
    later = frames[start + width:start + width + horizon]
    samples = [row["samples"] for row in observed]
    controls = [row["controls"] for row in observed]
    means = _mean(samples)
    deltas = [samples[-1][i] - samples[0][i] for i in range(len(samples[0]))]
    variances = [sum((row[i] - means[i]) ** 2 for row in samples) / len(samples) for i in range(len(means))]
    descriptor = means + deltas + variances + _mean(controls)
    future = _mean([row["samples"] for row in later])
    return descriptor, future


def learn_events(stream: dict, *, window: int = 6, horizon: int = 4, stride: int = 4) -> list[dict]:
    stream = validate_causal_stream(stream)
    frames = stream["frames"]
    events = []
    for start in range(0, len(frames) - window - horizon + 1, stride):
        descriptor, future = _event_descriptor(frames, start, window, horizon)
        events.append({
            "event_id": f"ev:{len(events)+1:06d}",
            "sample_indexes": list(range(start, start + window)),
            "future_sample_indexes": list(range(start + window, start + window + horizon)),
            "source_offsets": [frame["source_offset"] for frame in frames[start:start + window]],
            "future_source_offsets": [frame["source_offset"] for frame in frames[start + window:start + window + horizon]],
            "descriptor": [round(value, 12) for value in descriptor],
            "future": [round(value, 12) for value in future],
            "split": "holdout" if len(events) % 5 == 0 else "train",
        })
    return events


def _normalizer(events: list[dict]) -> tuple[list[float], list[float]]:
    train = [event["descriptor"] for event in events if event["split"] == "train"]
    means = _mean(train)
    scales = []
    for index, mean in enumerate(means):
        variance = sum((row[index] - mean) ** 2 for row in train) / max(1, len(train))
        scales.append(math.sqrt(variance) or 1.0)
    return means, scales


def _normalized(event: dict, means: list[float], scales: list[float]) -> list[float]:
    return [(value - means[index]) / scales[index] for index, value in enumerate(event["descriptor"])]


def _projection(rng: random.Random, dimensions: int) -> list[dict]:
    count = min(6, dimensions)
    indexes = sorted(rng.sample(range(dimensions), count))
    magnitude = 1.0 / math.sqrt(count)
    return [{"index": index, "weight": magnitude if rng.random() < 0.5 else -magnitude} for index in indexes]


def _project(vector: list[float], projection: list[dict]) -> float:
    return sum(vector[item["index"]] * item["weight"] for item in projection)


def _inside(value: float, lower: float | None, upper: float | None) -> bool:
    return (lower is None or value >= lower) and (upper is None or value < upper)


def replay_region_membership(region: dict, event: dict, normalizer: dict) -> bool:
    trace = region["membership_trace"]
    vector = _normalized(event, normalizer["means"], normalizer["scales"])
    observed = _inside(_project(vector, trace["projection"]), trace["lower"], trace["upper"])
    expected = event["event_id"] in set(region["train_event_ids"] + region["holdout_event_ids"])
    if observed != expected:
        raise ValueError(f"membership replay failed for {region['region_id']} and {event['event_id']}")
    return observed


def _score_candidate(events: list[dict], values: dict[str, float], lower, upper, global_future: list[float]) -> dict | None:
    train = [event for event in events if event["split"] == "train" and _inside(values[event["event_id"]], lower, upper)]
    holdout = [event for event in events if event["split"] == "holdout" and _inside(values[event["event_id"]], lower, upper)]
    if len(train) < 12 or len(holdout) < 4:
        return None
    prototype = _mean([event["future"] for event in train])
    model_errors = [_sse(event["future"], prototype) for event in holdout]
    baseline_errors = [_sse(event["future"], global_future) for event in holdout]
    model_total = sum(model_errors)
    baseline_total = sum(baseline_errors)
    wins = sum(model < base for model, base in zip(model_errors, baseline_errors))
    if not model_total < baseline_total:
        return None
    return {
        "prototype": [round(value, 12) for value in prototype],
        "train": [event["event_id"] for event in train],
        "holdout": [event["event_id"] for event in holdout],
        "model_error_sum": round(model_total, 12),
        "baseline_error_sum": round(baseline_total, 12),
        "wins": wins,
        "trials": len(holdout),
    }


def derive_regions(events: list[dict], *, seed: int, target: int) -> tuple[list[dict], dict]:
    means, scales = _normalizer(events)
    normalizer = {"means": means, "scales": scales}
    normalized = {event["event_id"]: _normalized(event, means, scales) for event in events}
    global_future = _mean([event["future"] for event in events if event["split"] == "train"])
    rng = random.Random(seed ^ 0x524547494F4E)
    regions, seen_memberships = [], set()
    projection_number = 0
    while len(regions) < target and projection_number < target * 5:
        projection_number += 1
        projection = _projection(rng, len(means))
        values = {event_id: _project(vector, projection) for event_id, vector in normalized.items()}
        train_values = [values[event["event_id"]] for event in events if event["split"] == "train"]
        cuts = [_quantile(train_values, fraction) for fraction in (0.2, 0.4, 0.6, 0.8)]
        bounds = [(None, cuts[0]), (cuts[0], cuts[1]), (cuts[1], cuts[2]), (cuts[2], cuts[3]), (cuts[3], None)]
        partition_id = f"sp:{projection_number:05d}"
        for bin_index, (lower, upper) in enumerate(bounds):
            score = _score_candidate(events, values, lower, upper, global_future)
            if score is None:
                continue
            signature = tuple(score["train"] + score["holdout"])
            if signature in seen_memberships:
                continue
            seen_memberships.add(signature)
            region_id = f"sr:{len(regions)+1:05d}"
            regions.append({
                "region_id": region_id,
                "partition_id": partition_id,
                "cell_id": f"sc:{projection_number:05d}:{bin_index}",
                "train_event_ids": score["train"],
                "holdout_event_ids": score["holdout"],
                "future_sample_prototype": score["prototype"],
                "membership_trace": {
                    "algorithm_id": "random-projection-quantile-v1",
                    "projection": projection,
                    "lower": lower,
                    "upper": upper,
                    "normalizer_id": "norm:00001",
                    "seed_stream": seed ^ 0x524547494F4E,
                },
                "communication_evidence": {
                    "target": "withheld_future_transducer_samples",
                    "model_squared_error_sum": score["model_error_sum"],
                    "global_baseline_squared_error_sum": score["baseline_error_sum"],
                    "reconstruction_wins": score["wins"],
                    "trial_count": score["trials"],
                    "acceptance_rule": "model squared-error sum is lower than the global-prototype squared-error sum",
                    "accepted": True,
                },
            })
            if len(regions) == target:
                break
    if len(regions) < target:
        raise RuntimeError(f"experience supported {len(regions)} regions; requested {target}")
    return regions, {"normalizer_id": "norm:00001", **normalizer}


def _forms(seed: int, count: int, phonology_path: str | Path) -> tuple[list[str], object]:
    cfg = load_phonology(phonology_path)
    allocator = FormAllocator.create(cfg, random.Random(seed ^ 0x464F524D))
    return [allocator.take() for _ in range(count)], cfg


def _region_distribution(region: dict, events_by_id: dict[str, dict]) -> dict:
    rows = [events_by_id[event_id] for event_id in region["train_event_ids"]]
    descriptor_mean = _mean([row["descriptor"] for row in rows])
    ranked = sorted(range(len(descriptor_mean)), key=lambda index: (-abs(descriptor_mean[index]), index))[:3]
    return {
        "distribution_class_id": "dc:" + hashlib.sha256(json.dumps(ranked).encode()).hexdigest()[:12],
        "active_internal_axes": ranked,
        "licensed_partition_id": region["partition_id"],
        "participant_slots": [f"slot:{index:02d}" for index in range(max(1, min(3, len(ranked))))],
    }


def _event_codes(events: list[dict], regions: list[dict]) -> dict[str, list[str]]:
    active: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for region in regions:
        evidence = region["communication_evidence"]
        gain = evidence["global_baseline_squared_error_sum"] - evidence["model_squared_error_sum"]
        for event_id in region["train_event_ids"] + region["holdout_event_ids"]:
            active[event_id].append((gain, region["region_id"]))
    return {
        event["event_id"]: [region_id for _, region_id in sorted(active[event["event_id"]], key=lambda row: (-row[0], row[1]))[:4]]
        for event in events
    }


def _joint_score(event_ids: list[str], events_by_id: dict[str, dict], train_ids: set[str], holdout_ids: set[str], baseline: list[float]) -> dict | None:
    train = [events_by_id[event_id] for event_id in event_ids if event_id in train_ids]
    holdout = [events_by_id[event_id] for event_id in event_ids if event_id in holdout_ids]
    if len(train) < 8 or len(holdout) < 3:
        return None
    prototype = _mean([event["future"] for event in train])
    model = sum(_sse(event["future"], prototype) for event in holdout)
    base = sum(_sse(event["future"], baseline) for event in holdout)
    if model >= base:
        return None
    return {
        "train": len(train), "holdout": len(holdout),
        "train_event_ids": [event["event_id"] for event in train],
        "holdout_event_ids": [event["event_id"] for event in holdout],
        "model": round(model, 12), "baseline": round(base, 12),
    }


def derive_constructions(events: list[dict], regions: list[dict], *, limit: int = 96) -> tuple[list[dict], dict[str, list[str]]]:
    codes = _event_codes(events, regions)
    events_by_id = {event["event_id"]: event for event in events}
    train_ids = {event["event_id"] for event in events if event["split"] == "train"}
    holdout_ids = set(events_by_id) - train_ids
    global_future = _mean([events_by_id[event_id]["future"] for event_id in train_ids])
    occurrences: dict[tuple[str, str], list[str]] = defaultdict(list)
    for event_id, message in codes.items():
        for left, right in zip(message, message[1:]):
            occurrences[(left, right)].append(event_id)
    constructions = []
    for pair, event_ids in sorted(occurrences.items(), key=lambda item: (-len(item[1]), item[0])):
        left = next(region for region in regions if region["region_id"] == pair[0])
        right = next(region for region in regions if region["region_id"] == pair[1])
        constituent_baseline = [
            (a + b) / 2.0
            for a, b in zip(left["future_sample_prototype"], right["future_sample_prototype"])
        ]
        score = _joint_score(event_ids, events_by_id, train_ids, holdout_ids, constituent_baseline)
        if score is None:
            continue
        constructions.append({
            "construction_id": f"cx:{len(constructions)+1:04d}",
            "ordered_cells": [left["cell_id"], right["cell_id"]],
            "ordered_regions": list(pair),
            "train_event_count": score["train"],
            "holdout_event_count": score["holdout"],
            "train_event_ids": score["train_event_ids"],
            "holdout_event_ids": score["holdout_event_ids"],
            "joint_squared_error_sum": score["model"],
            "constituent_baseline_squared_error_sum": score["baseline"],
            "acceptance_rule": "joint-use prototype has lower held-out squared error than the mean constituent prototype",
        })
        if len(constructions) == limit:
            break
    return constructions, codes


def _communication_report(events: list[dict], regions: list[dict], codes: dict[str, list[str]]) -> dict:
    by_region = {region["region_id"]: region for region in regions}
    train_future = [event["future"] for event in events if event["split"] == "train"]
    global_future = _mean(train_future)
    holdout = [event for event in events if event["split"] == "holdout"]
    model_total = baseline_total = 0.0
    wins = encoded = 0
    for event in holdout:
        message = codes[event["event_id"]]
        if not message:
            predicted = global_future
        else:
            predicted = _mean([by_region[region_id]["future_sample_prototype"] for region_id in message])
            encoded += 1
        model = _sse(event["future"], predicted)
        baseline = _sse(event["future"], global_future)
        model_total += model
        baseline_total += baseline
        wins += model < baseline
    return {
        "target": "withheld_future_transducer_samples",
        "holdout_trial_count": len(holdout),
        "message_available_count": encoded,
        "reconstruction_win_count": wins,
        "message_squared_error_sum": round(model_total, 12),
        "global_baseline_squared_error_sum": round(baseline_total, 12),
        "decision_rule": "language succeeds when message squared-error sum is lower than the global baseline on the same held-out events",
        "succeeded": model_total < baseline_total,
    }


def generate_causal_language(
    *, seed: int = 19020, stream: dict | None = None, vocabulary_scale: str = "large",
    phonology_path: str | Path = DEFAULT_PHONOLOGY,
) -> dict:
    if vocabulary_scale not in VOCABULARY_SCALES:
        raise ValueError(f"vocabulary_scale must be one of {sorted(VOCABULARY_SCALES)}")
    stream = validate_causal_stream(stream or generate_builtin_stream(seed))
    events = learn_events(stream)
    regions, normalizer = derive_regions(events, seed=seed, target=VOCABULARY_SCALES[vocabulary_scale])
    constructions, codes = derive_constructions(events, regions)
    morphology = derive_morphology(regions, codes)
    marker_cells = [cell for dimension in morphology["dimensions"] for cell in dimension["cells"]]
    forms, cfg = _forms(seed, len(regions) + len(marker_cells), phonology_path)
    events_by_id = {event["event_id"]: event for event in events}
    lexicon = []
    for index, (region, form) in enumerate(zip(regions, forms), 1):
        syllables = form.split(".")
        prominence = prominence_index(syllables, "penultimate")
        lexicon.append({
            "lexeme_id": f"lx:{index:05d}",
            "semantic_region_id": region["region_id"],
            "form": form,
            "orthographic": form.replace(".", ""),
            "syllables": syllables,
            "prominence": prominence,
            "annotated_form": ".".join(("ˈ" if i == prominence else "") + value for i, value in enumerate(syllables)),
            "formation": "learned_region_root",
            "current_analysis": {"root_id": f"root:{index:05d}", "parts": [f"root:{index:05d}"]},
            "distribution": _region_distribution(region, events_by_id),
            "generation_trace": {
                "region_id": region["region_id"],
                "membership_algorithm": region["membership_trace"]["algorithm_id"],
                "input_event_ids": region["train_event_ids"],
                "seed": seed,
            },
        })
    for cell, form in zip(marker_cells, forms[len(regions):]):
        cell["marker_form"] = form.replace(".", "")
        cell["form_trace"] = {
            "algorithm_id": "productive-host-distribution-v1",
            "source_region_id": cell["source_region_id"],
            "event_ids": cell["event_ids"],
            "seed": seed,
        }
    historical_lexemes, history = lexicalize_constructions(constructions, lexicon)
    lexicon.extend(historical_lexemes)
    partitions = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for region in regions:
        grouped[region["partition_id"]].append(region)
    for partition_id, rows in sorted(grouped.items()):
        partitions.append({
            "partition_id": partition_id,
            "cells": [{"cell_id": row["cell_id"], "semantic_region_id": row["region_id"]} for row in rows],
            "source": "learned projection ranges retained by held-out sample reconstruction",
        })
    report = _communication_report(events, regions, codes)
    if not report["succeeded"]:
        raise RuntimeError("learned messages did not improve held-out sample reconstruction")
    trace = {
        "schema": "losica-causal-generation-trace/1",
        "algorithm_id": ALGORITHM,
        "seed": seed,
        "stream_sha256": causal_stream_sha256(stream),
        "parameters": {"vocabulary_scale": vocabulary_scale, "phonology_path_sha256": hashlib.sha256(Path(phonology_path).read_bytes()).hexdigest()},
        "output_counts": {
            "events": len(events), "regions": len(regions), "lexemes": len(lexicon),
            "constructions": len(constructions), "morphology_dimensions": len(morphology["dimensions"]),
            "historical_lexemes": len(historical_lexemes),
        },
    }
    partial = {"lexicon": lexicon, "morphology": morphology}
    utterances = []
    for event_id, message in sorted(codes.items()):
        realized = realize_regions(partial, message)
        utterances.append({"event_id": event_id, **realized})
    return {
        "schema": SCHEMA,
        "version": "0.29.0",
        "seed": seed,
        "language_id": f"losica:{seed}:{causal_stream_sha256(stream)[:12]}",
        "causal_inputs": generation_materials(stream),
        "normalizers": [normalizer],
        "events": events,
        "semantic_regions": regions,
        "semantic_partitions": partitions,
        "lexicon": lexicon,
        "morphology": morphology,
        "constructions": constructions,
        "history": history,
        "utterance_traces": utterances,
        "communication": report,
        "phonology": {"consonants": list(cfg.consonants), "vowels": list(cfg.vowels), "syllable": cfg.syllable},
        "generation_trace": trace,
        "adapter_contract": {
            "load_order": "after_generation",
            "evidence_link": "external descriptions provide source_offset_ranges",
            "derivation": "ranges select overlapping ev:* records; their generated utterances supply sr:* identities",
            "generalization": "recurrent external word sequences associate with recurrent generated regions",
            "core_mutation": False,
        },
    }


def canonical_causal_language(language: dict) -> bytes:
    value = copy.deepcopy(language)
    value.pop("adapters", None)
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def replay_causal_generation(trace: dict, stream: dict, *, phonology_path: str | Path = DEFAULT_PHONOLOGY) -> dict:
    if trace.get("schema") != "losica-causal-generation-trace/1" or trace.get("algorithm_id") != ALGORITHM:
        raise ValueError("unsupported causal generation trace")
    stream = validate_causal_stream(stream)
    if causal_stream_sha256(stream) != trace["stream_sha256"]:
        raise ValueError("causal stream does not match generation trace")
    result = generate_causal_language(
        seed=int(trace["seed"]), stream=stream,
        vocabulary_scale=trace["parameters"]["vocabulary_scale"], phonology_path=phonology_path,
    )
    if result["generation_trace"] != trace:
        raise ValueError("replayed generation trace differs")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate Losica from unnamed transducer streams")
    parser.add_argument("--seed", type=int, default=19020)
    parser.add_argument("--stream", help="losica-causal-stream/1 JSON; omit for the deterministic numeric fixture")
    parser.add_argument("--attestation", help="required collection audit for an external stream")
    parser.add_argument("--vocabulary-scale", choices=sorted(VOCABULARY_SCALES), default="large")
    parser.add_argument("--phonology", default=str(DEFAULT_PHONOLOGY))
    parser.add_argument("--out", default="language.json")
    args = parser.parse_args(argv)
    if bool(args.stream) != bool(args.attestation):
        parser.error("--stream and --attestation are required together")
    stream = load_causal_stream(args.stream) if args.stream else None
    if stream is not None:
        load_collection_attestation(args.attestation, source_sha256=stream["source_sha256"])
    language = generate_causal_language(seed=args.seed, stream=stream, vocabulary_scale=args.vocabulary_scale, phonology_path=args.phonology)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(language, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(target), "language_id": language["language_id"],
        "lexemes": len(language["lexicon"]), "regions": len(language["semantic_regions"]),
        "constructions": len(language["constructions"]), "communication": language["communication"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
