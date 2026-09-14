#!/usr/bin/env python3
"""Compile structural empirical evidence into the canonical Losica core."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

STRUCTURAL_PROBE_FIELDS = (
    "concepticon_id", "network_rank", "community_id", "form_count",
    "variety_count", "language_count", "family_count", "graph_degree",
    "weighted_family_degree", "weighted_language_degree",
)
STRUCTURAL_EDGE_FIELDS = (
    "edge_id", "source_concepticon_id", "target_concepticon_id",
    "form_count", "variety_count", "language_count", "family_count", "family_weight",
)


def _project(row: dict, fields: tuple[str, ...]) -> dict:
    return {key: row[key] for key in fields if key in row and row[key] is not None}


def build_core(source: dict) -> dict:
    registry = source["semantic_probe_registry"]
    concepts = [_project(row, STRUCTURAL_PROBE_FIELDS) for row in registry["concepts"]]
    core = {
        "schema": "losica-empirical-core/5",
        "versions": source["versions"],
        "missing_data_policy": source["missing_data_policy"],
        "semantic_probe_pool": {
            "registry": registry["registry"],
            "version": registry["version"],
            "selection_basis": registry["selection_basis"],
            "probe_count": len(concepts),
            "community_count": len({str(row.get("community_id")) for row in concepts}),
        },
        "concepts": concepts,
        "colexification_prior": source.get("colexification_prior", {}),
        "colexification_edges": [_project(row, STRUCTURAL_EDGE_FIELDS) for row in source.get("colexification_edges", [])],
        "wals_joint_profiles": source["wals_joint_profiles"],
        "wals_feature_audits": source["wals_feature_audits"],
        "grambank_parameters": source["grambank_parameters"],
        "phoible": source["phoible"],
    }
    return core


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Losica structural empirical core")
    ap.add_argument("source")
    ap.add_argument("out")
    args = ap.parse_args(argv)
    obj = build_core(json.loads(Path(args.source).read_text(encoding="utf-8")))
    Path(args.out).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
