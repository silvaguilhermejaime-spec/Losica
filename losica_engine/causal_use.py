"""Inspect and emit utterances from a causal Losica language."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .causal_grammar import analyze_utterance


def event_utterance(language: dict, event_id: str) -> dict:
    trace = next((row for row in language["utterance_traces"] if row["event_id"] == event_id), None)
    if trace is None:
        raise KeyError(f"unknown event {event_id}")
    return copy.deepcopy(trace)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Use an independently generated causal Losica language")
    parser.add_argument("language")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary")
    event = sub.add_parser("event")
    event.add_argument("event_id")
    region = sub.add_parser("region")
    region.add_argument("region_id")
    analyze = sub.add_parser("analyze")
    analyze.add_argument("utterance")
    args = parser.parse_args(argv)
    language = json.loads(Path(args.language).read_text(encoding="utf-8"))
    if args.command == "summary":
        result = {
            "language_id": language["language_id"],
            "events": len(language["events"]),
            "lexemes": len(language["lexicon"]),
            "root_lexemes": sum(row.get("formation") == "learned_region_root" for row in language["lexicon"]),
            "historical_lexemes": sum(row.get("formation") == "historical_lexicalization" for row in language["lexicon"]),
            "constructions": len(language["constructions"]),
            "morphology_dimensions": len(language["morphology"]["dimensions"]),
            "communication": language["communication"],
        }
    elif args.command == "event":
        result = event_utterance(language, args.event_id)
    elif args.command == "analyze":
        result = analyze_utterance(language, args.utterance)
    else:
        result = next((row for row in language["semantic_regions"] if row["region_id"] == args.region_id), None)
        if result is None:
            raise KeyError(f"unknown region {args.region_id}")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
