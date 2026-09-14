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


ADAPTER_SCHEMA = "losica-external-alignment/3"
SUPPORTED_ADAPTER_SCHEMAS = frozenset({"losica-external-alignment/2", ADAPTER_SCHEMA})
RECORD_FIELDS = frozenset({"external_id", "expression", "source_offset_ranges"})
NORMALIZATION_MIN_DOMINANCE = 0.8


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


def _surface_analysis(expression: str) -> list[dict]:
    return [
        {"surface": token, "lemma": token, "upos": None, "deprel": None, "head": None}
        for token in _tokens(expression)
    ]


def stanza_analyzer(language: str = "en"):
    """Create a build-time UD analyzer without making it a phone dependency."""
    try:
        import stanza
    except ImportError as exc:
        raise RuntimeError(
            "Stanza analysis requires the optional nlp dependencies: pip install -e '.[nlp]'"
        ) from exc
    pipeline = stanza.Pipeline(
        lang=language,
        processors="tokenize,mwt,pos,lemma,depparse",
        tokenize_no_ssplit=True,
        verbose=False,
    )

    def analyze(expression: str) -> list[dict]:
        document = pipeline(expression)
        return [
            {
                "surface": word.text,
                "lemma": word.lemma or word.text,
                "upos": word.upos,
                "deprel": word.deprel,
                "head": word.head,
            }
            for sentence in document.sentences
            for word in sentence.words
        ]

    return analyze


def _normalize_analysis(expression: str, analyzer) -> list[dict]:
    analysis = analyzer(expression) if analyzer is not None else _surface_analysis(expression)
    if not isinstance(analysis, list) or not analysis:
        raise ValueError("external parser returned no tokens")
    result = []
    for index, row in enumerate(analysis):
        if not isinstance(row, dict) or not isinstance(row.get("surface"), str):
            raise ValueError(f"external parser token {index} requires surface text")
        surface_tokens = _tokens(row["surface"])
        lemma_tokens = _tokens(str(row.get("lemma") or row["surface"]))
        if not surface_tokens and not lemma_tokens:
            continue
        if len(surface_tokens) != 1 or len(lemma_tokens) != 1:
            raise ValueError(f"external parser token {index} must normalize to one token")
        result.append({
            "parser_index": index + 1,
            "surface": surface_tokens[0],
            "lemma": lemma_tokens[0],
            "upos": row.get("upos"),
            "deprel": row.get("deprel"),
            "head": row.get("head"),
        })
    if not result:
        raise ValueError("external parser returned no lexical tokens")
    return result


def _normalization_lexicon(aligned: list[dict]) -> dict[str, str]:
    candidates: dict[str, Counter] = defaultdict(Counter)
    for row in aligned:
        for token in row["linguistic_analysis"]:
            candidates[token["surface"]][token["lemma"]] += 1
    lexicon = {}
    for surface, counts in sorted(candidates.items()):
        lemma, winning_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        if winning_count / sum(counts.values()) >= NORMALIZATION_MIN_DOMINANCE:
            lexicon[surface] = lemma
    return lexicon


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
        phrases = _phrases(row["normalized_tokens"])
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
    if adapter.get("schema") not in SUPPORTED_ADAPTER_SCHEMAS:
        raise ValueError("unsupported external alignment schema")
    if adapter.get("language_id") != language.get("language_id") or adapter.get("canonical_language_sha256") != digest:
        raise ValueError("adapter does not identify this generated language")


def build_alignment(
    language: dict,
    records: list[dict],
    *,
    namespace: str,
    analyzer=None,
    analyzer_id: str = "surface",
) -> dict:
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
        linguistic_analysis = _normalize_analysis(expression, analyzer)
        tokens = [row["surface"] for row in linguistic_analysis]
        normalized_tokens = [row["lemma"] for row in linguistic_analysis]
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
            "normalized_tokens": normalized_tokens,
            "linguistic_analysis": linguistic_analysis,
            "source_offset_ranges": ranges,
            "evidence_event_ids": event_ids,
            "region_ids": region_ids,
            "derivation": "source ranges -> overlapping learned events -> regions used by those events",
        })
    normalization_lexicon = _normalization_lexicon(aligned)
    adapter = {
        "schema": ADAPTER_SCHEMA,
        "algorithm_id": "cross-situation-time-alignment-v1",
        "namespace": namespace,
        "language_id": language["language_id"],
        "canonical_language_sha256": before,
        "records": copy.deepcopy(aligned),
        "learned_units": _learn_units(aligned),
        "external_analysis": {
            "build_time_analyzer": analyzer_id,
            "runtime": "stored surface-to-lemma lexicon; no parser or model required",
            "normalization_min_dominance": NORMALIZATION_MIN_DOMINANCE,
            "ambiguity_rule": "leave a surface form unchanged unless one observed lemma has at least 80% of its evidence",
        },
        "normalization_lexicon": normalization_lexicon,
    }
    after = hashlib.sha256(canonical_causal_language(language)).hexdigest()
    if before != after:
        raise RuntimeError("adapter construction mutated the generated language")
    return adapter


def _learned_regions(adapter: dict, expression: str) -> tuple[list[str], dict]:
    surface_tokens = _tokens(expression)
    normalization = adapter.get("normalization_lexicon", {})
    tokens = [normalization.get(token, token) for token in surface_tokens]
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
        for association in unit["associations"][:2]:
            region_id = association["region_id"]
            if region_id not in regions:
                regions.append(region_id)
        covered += width
        position += width
    return regions, {
        "covered_token_count": covered,
        "total_token_count": len(surface_tokens),
        "coverage_ratio": covered / len(surface_tokens) if surface_tokens else 0.0,
        "measurement_rule": "tokens covered by the longest learned one-to-four-token units",
    }


def external_to_losica(language: dict, adapter: dict, expression: str) -> dict:
    """Translate through event-derived mappings; report measured token coverage."""
    _verify_adapter(language, adapter)
    matches = [row for row in adapter["records"] if row["expression"] == expression]
    choices = []
    if matches:
        learned_regions, learned_coverage = _learned_regions(adapter, expression)
        if len(matches) >= 2 and learned_coverage["coverage_ratio"] >= 0.8:
            event_ids = sorted({event_id for row in matches for event_id in row["evidence_event_ids"]})
            choices.append({
                "external_id": matches[0]["external_id"],
                "external_ids": [row["external_id"] for row in matches],
                "evidence_event_ids": event_ids,
                **realize_regions(language, learned_regions),
            })
            coverage = {
                **learned_coverage,
                "measurement_rule": "repeated time-aligned one-to-four-token units",
            }
        else:
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
    unit_index = {row["unit"]: row for row in adapter.get("learned_units", [])}
    ranked = []
    for row in adapter["records"]:
        full_unit = " ".join(row.get("normalized_tokens", _tokens(row["expression"])))
        learned = unit_index.get(full_unit)
        aligned = (
            {association["region_id"] for association in learned["associations"][:2]}
            if learned is not None else set(row["region_ids"])
        )
        union = observed | aligned
        overlap = len(observed & aligned)
        ranked.append({
            "external_id": row["external_id"],
            "expression": row["expression"],
            "shared_region_count": overlap,
            "combined_region_count": len(union),
            "overlap_ratio": overlap / len(union) if union else 0.0,
            "alignment_basis": "learned_expression_signature" if learned is not None else "time_aligned_record",
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
    build.add_argument("--external-parser", choices=["surface", "stanza"], default="surface")
    build.add_argument("--parser-language", default="en")
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
        analyzer = stanza_analyzer(args.parser_language) if args.external_parser == "stanza" else None
        adapter = build_alignment(
            language,
            records,
            namespace=args.namespace,
            analyzer=analyzer,
            analyzer_id=(f"stanza:{args.parser_language}" if analyzer is not None else "surface"),
        )
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
