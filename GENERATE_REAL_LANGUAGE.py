#!/usr/bin/env python3
"""Generate and align a Losica language from real media."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from losica_engine.causal_adapter import (
    build_alignment,
    external_to_losica,
    losica_to_external,
    stanza_analyzer,
)
from losica_engine.causal_finalize import finalize_causal_language
from losica_engine.media_stream import import_real_media


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Losica from real audio/video and align external wording")
    parser.add_argument("manifest")
    parser.add_argument("--catalog")
    parser.add_argument("--namespace", default="external")
    parser.add_argument("--seed", type=int, default=19020)
    parser.add_argument("--vocabulary-scale", choices=["core", "intermediate", "large"], default="core")
    parser.add_argument("--fps", type=float, default=40.0)
    parser.add_argument("--external-parser", choices=["surface", "stanza"], default="surface")
    parser.add_argument("--parser-language", default="en")
    parser.add_argument("--out-dir", type=Path, default=Path("dist/real-media"))
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stream, records, attestation, import_report = import_real_media(
        args.manifest, fps=args.fps, catalog_path=args.catalog,
    )
    write(out / "causal-stream.json", stream)
    write(out / "alignment-records.json", records)
    write(out / "collection-attestation.json", attestation)
    write(out / "import-report.json", import_report)
    release = finalize_causal_language(
        seed=args.seed, stream=stream, vocabulary_scale=args.vocabulary_scale,
        out=out / "language.json",
    )
    language = json.loads((out / "language.json").read_text(encoding="utf-8"))
    analyzer = stanza_analyzer(args.parser_language) if args.external_parser == "stanza" else None
    adapter = build_alignment(
        language,
        records,
        namespace=args.namespace,
        analyzer=analyzer,
        analyzer_id=(f"stanza:{args.parser_language}" if analyzer is not None else "surface"),
    )
    write(out / "adapter.json", adapter)
    expressions = sorted({row["expression"] for row in records})
    outward = [external_to_losica(language, adapter, expression) for expression in expressions]
    inward = []
    for outward_result in outward:
        utterance = outward_result["realizations"][0]["utterance"]
        inverse = losica_to_external(language, adapter, utterance)
        inverse["expected_expression"] = outward_result["expression"]
        inverse["top_expression"] = inverse["external_candidates"][0]["expression"]
        inverse["round_trip_match"] = inverse["top_expression"] == inverse["expected_expression"]
        inward.append(inverse)
    if not all(row["round_trip_match"] for row in inward):
        raise RuntimeError("one or more aligned expressions failed bidirectional translation")
    translations = {"external_to_losica": outward, "losica_to_external": inward}
    write(out / "translations.json", translations)
    result = {
        "schema": "losica-real-media-release/1", "status": "PASS",
        "recordings": import_report["recording_count"], "frames": import_report["frame_count"],
        "alignment_records": len(records), "external_expressions": len(expressions),
        "language_id": release["language_id"], "lexemes": release["lexemes"],
        "constructions": release["constructions"], "communication_wins": release["communication_wins"],
        "communication_trials": release["communication_trials"], "out": str(out),
    }
    write(out / "result.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
