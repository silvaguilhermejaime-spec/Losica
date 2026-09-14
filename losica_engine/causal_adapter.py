"""Learn a post-generation human-language interface from time-aligned experience."""
from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import unicodedata

from .experiential_language import canonical_causal_language
from .causal_grammar import analyze_utterance, realize_regions


ADAPTER_SCHEMA = "losica-external-alignment/2"
RECORD_FIELDS = frozenset({"external_id", "expression", "source_offset_ranges"})


def _tokens(expression: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", expression).casefold()
    out, current = [], []
    for character in normalized:
        if character.isalnum() or character in {"'", "’"}:
            current.append(character)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def _phrases(tokens: list[str], limit: int = 4) -> set[str]:
    return {
        " ".join(tokens[start:start + width])
        for start in range(len(tokens))
        for width in range(1, min(limit, len(tokens) - start) + 1)
    }


def _ranges(value, index: int) -> list[list[int]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"alignment record {index} requires source_offset_ranges")
    result = []
    for range_index, row in enumerate(value):
        if (
            not isinstance(row, list) or len(row) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in row)
            or row[0] < 0 or row[1] < row[0]
        ):
            raise ValueError(f"alignment record {index} range {range_index} must be [nonnegative_start, end]")
        result.append([row[0], row[1]])
    return result


def _events_for_ranges(language: dict, ranges: list[list[int]]) -> list[str]:
    selected = []
    for event in language["events"]:
        offsets = event.get("source_offsets", [])
        if any(start <= offset <= end for start, end in ranges for offset in offsets):
            selected.append(event["event_id"])
    return selected


def _ordered_regions(event_ids: list[str], traces: dict[str, dict]) -> list[str]:
    positions: dict[str, list[int]] = defaultdict(list)
    for event_id in event_ids:
        for position, region_id in enumerate(traces[event_id]["region_ids"]):
            positions[region_id].append(position)
    return sorted(
        positions,
        key=lambda region_id: (
            sum(positions[region_id]) / len(positions[region_id]),
            -len(positions[region_id]),
            region_id,
        ),
    )


def _learn_units(aligned: list[dict]) -> list[dict]:
    total = len(aligned)
    phrase_counts, region_counts = Counter(), Counter()
    joint: dict[str, Counter] = defaultdict(Counter)
    for row in aligned:
        phrases = _phrases(row["tokens"])
        regions = set(row["region_ids"])
        phrase_counts.update(phrases)
        region_counts.update(regions)
        for phrase in phrases:
            joint[phrase].update(regions)
    units = []
    for phrase, region_joint in sorted(joint.items()):
        associations = []
        for region_id, shared in region_joint.items():
            if shared < 2:
                continue
            score = math.log2((shared * total) / (phrase_counts[phrase] * region_counts[region_id]))
            if score <= 0:
                continue
            associations.append({
                "region_id": region_id,
                "shared_record_count": shared,
                "phrase_record_count": phrase_counts[phrase],
                "region_record_count": region_counts[region_id],
                "total_record_count": total,
                "association_bits": round(score, 12),
            })
        associations.sort(
            key=lambda row: (-row["association_bits"], -row["shared_record_count"], row["region_id"])
        )
        if associations:
            units.append({"unit": phrase, "token_count": len(phrase.split()), "associations": associations})
    return units


def _verify_adapter(language: dict, adapter: dict) -> None:
    digest = hashlib.sha256(canonical_causal_language(language)).hexdigest()
    if adapter.get("schema") != ADAPTER_SCHEMA:
        raise ValueError("unsupported external alignment schema")
    if adapter.get("language_id") != language.get("language_id") or adapter.get("canonical_language_sha256") != digest:
        raise ValueError("adapter does not identify this generated language")


def build_alignment(language: dict, records: list[dict], *, namespace: str) -> dict:
    """Derive external mappings from descriptions aligned to source time ranges."""
    before = hashlib.sha256(canonical_causal_language(language)).hexdigest()
    traces = {row["event_id"]: row for row in language["utterance_traces"]}
    aligned = []
    for index, row in enumerate(records):
        if not isinstance(row, dict) or set(row) != RECORD_FIELDS:
            raise ValueError(
                f"alignment record {index} must contain external_id, expression, and source_offset_ranges; region_ids are derived"
            )
        expression = str(row["expression"])
        tokens = _tokens(expression)
        if not tokens:
            raise ValueError(f"alignment record {index} expression has no tokens")
        ranges = _ranges(row["source_offset_ranges"], index)
        event_ids = _events_for_ranges(language, ranges)
        if not event_ids:
            raise ValueError(f"alignment record {index} overlaps no generated event")
        region_ids = _ordered_regions(event_ids, traces)
        if not region_ids:
            raise ValueError(f"alignment record {index} overlaps no communicatively retained region")
        aligned.append({
            "external_id": str(row["external_id"]),
            "expression": expression,
            "tokens": tokens,
            "source_offset_ranges": ranges,
            "evidence_event_ids": event_ids,
            "region_ids": region_ids,
            "derivation": "source ranges -> overlapping learned events -> regions used by those events",
        })
    adapter = {
        "schema": ADAPTER_SCHEMA,
        "algorithm_id": "cross-situation-time-alignment-v1",
        "namespace": namespace,
        "language_id": language["language_id"],
        "canonical_language_sha256": before,
        "records": copy.deepcopy(aligned),
        "learned_units": _learn_units(aligned),
    }
    after = hashlib.sha256(canonical_causal_language(language)).hexdigest()
    if before != after:
        raise RuntimeError("adapter construction mutated the generated language")
    return adapter


def _learned_regions(adapter: dict, expression: str) -> tuple[list[str], dict]:
    tokens = _tokens(expression)
    index = {row["unit"]: row for row in adapter.get("learned_units", [])}
    regions, covered = [], 0
    position = 0
    while position < len(tokens):
        match = None
        for width in range(min(4, len(tokens) - position), 0, -1):
            phrase = " ".join(tokens[position:position + width])
            if phrase in index:
                match = (width, index[phrase])
                break
        if match is None:
            position += 1
            continue
        width, unit = match
        region_id = unit["associations"][0]["region_id"]
        if region_id not in regions:
            regions.append(region_id)
        covered += width
        position += width
    return regions, {
        "covered_token_count": covered,
        "total_token_count": len(tokens),
        "coverage_ratio": covered / len(tokens) if tokens else 0.0,
        "measurement_rule": "tokens covered by the longest learned one-to-four-token units",
    }


def external_to_losica(language: dict, adapter: dict, expression: str) -> dict:
    """Translate through event-derived mappings; report measured token coverage."""
    _verify_adapter(language, adapter)
    matches = [row for row in adapter["records"] if row["expression"] == expression]
    choices = []
    if matches:
        for row in matches:
            realization = realize_regions(language, row["region_ids"])
            choices.append({
                "external_id": row["external_id"],
                "evidence_event_ids": row["evidence_event_ids"],
                **realization,
            })
        token_count = len(_tokens(expression))
        coverage = {
            "covered_token_count": token_count,
            "total_token_count": token_count,
            "coverage_ratio": 1.0,
            "measurement_rule": "exact time-aligned record",
        }
    else:
        region_ids, coverage = _learned_regions(adapter, expression)
        if not region_ids or coverage["coverage_ratio"] < 0.8:
            raise KeyError(
                "external expression lacks translation coverage: "
                f"{coverage['covered_token_count']}/{coverage['total_token_count']} tokens covered; at least 80% required"
            )
        choices.append({"external_id": None, "evidence_event_ids": [], **realize_regions(language, region_ids)})
    return {
        "namespace": adapter["namespace"],
        "expression": expression,
        "coverage": coverage,
        "realizations": choices,
    }


def losica_to_external(language: dict, adapter: dict, utterance: str) -> dict:
    """Analyze an utterance, then rank separately stored external expressions."""
    _verify_adapter(language, adapter)
    analysis = analyze_utterance(language, utterance)
    observed = set(analysis["region_ids"])
    ranked = []
    for row in adapter["records"]:
        aligned = set(row["region_ids"])
        union = observed | aligned
        overlap = len(observed & aligned)
        ranked.append({
            "external_id": row["external_id"],
            "expression": row["expression"],
            "shared_region_count": overlap,
            "combined_region_count": len(union),
            "overlap_ratio": overlap / len(union) if union else 0.0,
        })
    ranked.sort(key=lambda row: (-row["overlap_ratio"], -row["shared_region_count"], row["external_id"]))
    return {"namespace": adapter["namespace"], "analysis": analysis, "external_candidates": ranked}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build or use a post-generation human-language adapter")
    parser.add_argument("language")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("records")
    build.add_argument("--namespace", required=True)
    build.add_argument("--out", required=True)
    outward = sub.add_parser("external-to-losica")
    outward.add_argument("adapter")
    outward.add_argument("expression")
    inward = sub.add_parser("losica-to-external")
    inward.add_argument("adapter")
    inward.add_argument("utterance")
    args = parser.parse_args(argv)
    language = json.loads(Path(args.language).read_text(encoding="utf-8"))
    if args.command == "build":
        records = json.loads(Path(args.records).read_text(encoding="utf-8"))
        adapter = build_alignment(language, records, namespace=args.namespace)
        Path(args.out).write_text(json.dumps(adapter, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {
            "status": "PASS",
            "out": args.out,
            "records": len(adapter["records"]),
            "learned_units": len(adapter["learned_units"]),
        }
    else:
        adapter = json.loads(Path(args.adapter).read_text(encoding="utf-8"))
        result = (
            external_to_losica(language, adapter, args.expression)
            if args.command == "external-to-losica"
            else losica_to_external(language, adapter, args.utterance)
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
