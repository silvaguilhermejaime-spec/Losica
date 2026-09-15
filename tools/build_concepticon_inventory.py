#!/usr/bin/env python3
"""Normalize a pinned Concepticon concepticon.tsv into Losica's offline inventory."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


CONCEPTICON_COMMIT = "918bc44e123952a6ab5733be36c2d463799c23b4"
CONCEPTICON_VERSION = "3.4.0"


def build(source: Path) -> dict:
    payload = source.read_bytes()
    rows = []
    with source.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            concept_id = str(int(row["ID"]))
            rows.append({
                "concepticon_id": concept_id,
                "gloss": row["GLOSS"],
                "semantic_field": row["SEMANTICFIELD"] or None,
                "definition": row["DEFINITION"] or None,
                "ontological_category": row["ONTOLOGICAL_CATEGORY"] or None,
                "replacement_id": row["REPLACEMENT_ID"] or None,
            })
    rows.sort(key=lambda item: int(item["concepticon_id"]))
    if not rows or len({row["concepticon_id"] for row in rows}) != len(rows):
        raise ValueError("Concepticon input requires unique numeric IDs")
    return {
        "schema": "losica-semantic-inventory/1",
        "source": {
            "name": "Concepticon",
            "version": CONCEPTICON_VERSION,
            "repository": "concepticon/concepticon-data",
            "commit": CONCEPTICON_COMMIT,
            "path": "concepticondata/concepticon.tsv",
            "license": "CC BY 4.0",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "concept_count": len(rows),
        "concepts": rows,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), "concepts": result["concept_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
