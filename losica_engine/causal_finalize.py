"""Create and validate a finalized causal-language artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .causal_stream import load_causal_stream
from .causal_attestation import load_collection_attestation
from .causal_validation import validate_causal_language
from .experiential_language import generate_causal_language


def finalize_causal_language(*, seed=19020, stream=None, vocabulary_scale="large", out="language.json") -> dict:
    language = generate_causal_language(seed=seed, stream=stream, vocabulary_scale=vocabulary_scale)
    validation = validate_causal_language(language)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(language, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": "losica-causal-release/1",
        "status": validation["status"],
        "language_id": language["language_id"],
        "seed": seed,
        "language_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        **{key: validation[key] for key in (
            "events", "semantic_regions", "lexemes", "root_lexemes", "historical_lexemes",
            "constructions", "morphology_dimensions", "membership_replays",
            "communication_trials", "communication_wins",
        )},
        "out": str(target),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Finalize an English-independent causal Losica language")
    parser.add_argument("--seed", type=int, default=19020)
    parser.add_argument("--stream")
    parser.add_argument("--attestation")
    parser.add_argument("--vocabulary-scale", choices=["core", "intermediate", "large"], default="large")
    parser.add_argument("--out", default="language.json")
    args = parser.parse_args(argv)
    if bool(args.stream) != bool(args.attestation):
        parser.error("--stream and --attestation are required together")
    stream = load_causal_stream(args.stream) if args.stream else None
    if stream is not None:
        load_collection_attestation(args.attestation, source_sha256=stream["source_sha256"])
    print(json.dumps(finalize_causal_language(seed=args.seed, stream=stream, vocabulary_scale=args.vocabulary_scale, out=args.out), sort_keys=True))


if __name__ == "__main__":
    main()
