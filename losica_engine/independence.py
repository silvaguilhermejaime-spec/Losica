"""Canonical linguistic-state projection for source-language invariance tests."""
from __future__ import annotations

import hashlib
import json


def canonical_linguistic_state(state: dict) -> dict:
    lexicon = []
    for row in state["lexicon"]:
        lexicon.append({
            "lexeme_id": row["lexeme_id"],
            "concept": row["concept"],
            "concepticon_id": row.get("concepticon_id"),
            "semantic_region_id": row.get("semantic_region_id"),
            "semantic_region": row.get("semantic_region"),
            "concept_mappings": [
                {
                    "concepticon_id": m.get("concepticon_id"), "concept": m["concept"],
                    "probe_id": m.get("probe_id"), "membership": m.get("membership"),
                    "structural_evidence": m.get("structural_evidence", {}),
                }
                for m in row.get("concept_mappings", [])
            ],
            "class": row["class"],
            "distribution": row.get("distribution"),
            "argument_structure": row.get("argument_structure"),
            "grammatical_features": row.get("grammatical_features"),
            "reference_cell": row.get("reference_cell"),
            "underlying_form": row["underlying_form"],
            "form": row["form"],
            "orthographic": row.get("orthographic"),
            "formation": row["formation"],
        })

    examples = [{
        "construction": x["construction"],
        "semantic_graph": x["semantic_graph"],
        "tokens": x["tokens"],
        "orthographic_tokens": x["orthographic_tokens"],
        "dependencies": x["dependencies"],
        "features": [t.get("features", {}) for t in x["token_details"]],
        "semantic_roles": [t.get("semantic_role") for t in x["token_details"]],
    } for x in state["examples"]]

    paradigms = {k: v for k, v in state["paradigms"].items() if k not in {"sample_noun", "sample_verb"}}
    profile = state["profile"]
    linguistic_profile = {
        key: profile[key]
        for key in ("id", "syntax", "morphology", "prosody", "reference_system", "agreement_system", "numeral_system")
        if key in profile
    }
    return {
        "seed": state["seed"],
        "phonology": state["phonology"],
        "profile": linguistic_profile,
        "lexicon": lexicon,
        "morphology": state["morphology"],
        "syntax": state["syntax"],
        "prosody": state["prosody"],
        "orthography": state["orthography"],
        "paradigms": paradigms,
        "examples": examples,
        "history": state["history"],
    }


def canonical_linguistic_bytes(state: dict) -> bytes:
    return (json.dumps(canonical_linguistic_state(state), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_linguistic_hash(state: dict) -> str:
    return hashlib.sha256(canonical_linguistic_bytes(state)).hexdigest()
