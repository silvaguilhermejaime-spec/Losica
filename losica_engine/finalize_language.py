"""One-command creation of a finished generated-language bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .export_v021 import export_bundle
from .full_language import generate_complete_language
from .independence import canonical_linguistic_hash
from .validation_v021 import validate_complete_language


def finalize_language(*, seed: int = 19020, out_dir: str | Path = "output", history_generations: int = 0, display_locale: str | None = "en") -> dict:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    state = generate_complete_language(
        seed=seed,
        vocabulary_scale="large",
        historical_generations=history_generations,
        display_locale=display_locale,
    )
    validation = validate_complete_language(state)
    paths = export_bundle(state, root / "language.json", root / "resources")
    paradigm_cells = sum(len(v) for k, v in state["paradigms"].items() if k not in {"sample_noun", "sample_verb"})
    report = {
        "schema": "losica-final-language/1",
        "release": state["version"],
        "seed": seed,
        "status": validation["status"],
        "language_id": state["metadata"]["id"],
        "lexemes": len(state["lexicon"]),
        "concept_mappings": sum(len(x.get("concept_mappings", [])) for x in state["lexicon"]),
        "paradigm_cells": paradigm_cells,
        "constructions": len(state["constructions"]),
        "surface_semantic_round_trips": validation["semantic_round_trips"],
        "capability_probes": validation["capability_probes"],
        "reference_system": state["profile"]["reference_system"]["system_id"],
        "agreement_system": state["profile"]["agreement_system"]["system_id"],
        "numeral_system": state["profile"]["numeral_system"]["system_id"],
        "numeral_range": state["profile"]["numeral_system"]["range"],
        "canonical_linguistic_sha256": canonical_linguistic_hash(state),
        "language_json_sha256": hashlib.sha256(Path(paths["json"]).read_bytes()).hexdigest(),
        "resources": "resources",
    }
    (root / "FINAL_LANGUAGE.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate and validate a finished Losica language bundle")
    ap.add_argument("--seed", type=int, default=19020)
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--out", help="write the complete language JSON directly to this path")
    ap.add_argument("--history-generations", type=int, default=0)
    ap.add_argument("--display-locale", choices=["en", "none"], default="en")
    args = ap.parse_args(argv)
    if args.out:
        state = generate_complete_language(
            seed=args.seed,
            vocabulary_scale="large",
            historical_generations=args.history_generations,
            display_locale=None if args.display_locale == "none" else args.display_locale,
        )
        validation = validate_complete_language(state)
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"out": str(target), **validation}, sort_keys=True))
        return
    report = finalize_language(
        seed=args.seed,
        out_dir=args.out_dir,
        history_generations=args.history_generations,
        display_locale=None if args.display_locale == "none" else args.display_locale,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
