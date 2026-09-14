"""File contracts for optional grammars, evolution, and experiments."""
from __future__ import annotations

import json
from pathlib import Path


def compare_grammar_coverage(language: dict, reference_manifest: str | Path, *, system: str) -> dict:
    if system not in {"DELPH-IN Grammar Matrix", "DELPH-IN Grammary"}:
        raise ValueError("grammar comparison system must be DELPH-IN Grammar Matrix or DELPH-IN Grammary")
    reference = json.loads(Path(reference_manifest).read_text(encoding="utf-8"))
    supported = {x["name"] for x in language["constructions"]}
    phenomena = set(reference.get("phenomena", []))
    return {
        "schema": "losica-grammar-coverage-comparison/1", "system": system,
        "reference_id": reference.get("id"), "covered": sorted(supported & phenomena),
        "reference_only": sorted(phenomena - supported), "losica_only": sorted(supported - phenomena),
        "coverage": len(supported & phenomena) / len(phenomena) if phenomena else None,
        "provenance": {"reference_manifest": str(reference_manifest), "comparison_basis": "named executable construction phenomena"},
    }


def export_egg_experiment(language: dict, out: str | Path, *, meanings: list[dict], agents=10, seed=None) -> Path:
    payload = {
        "schema": "losica-egg-experiment/1", "source_language_id": language["metadata"]["id"],
        "seed": language["seed"] if seed is None else seed, "agents": agents, "meanings": meanings,
        "initial_signals": [{"lexeme_id": x["lexeme_id"], "form": x["form"]} for x in language["lexicon"]],
        "output_boundary": "emergent signals remain distinct from the direct natural-language state",
        "source": "facebookresearch/EGG",
    }
    p = Path(out); p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return p


def import_egg_results(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") != "losica-egg-results/1":
        raise ValueError("losica-egg-results/1 required")
    return {"schema": "losica-emergent-communication-stage/1", "experiment_id": obj["experiment_id"], "signals": obj["signals"], "metrics": obj.get("metrics", {}), "natural_language_state_modified": False}


def export_iterated_transmission(language: dict, out: str | Path, *, chains: int, generations: int, bottleneck: int) -> Path:
    payload = {
        "schema": "losica-iterated-transmission/1", "source_language_id": language["metadata"]["id"],
        "seed": language["seed"], "chains": chains, "generations": generations, "bottleneck": bottleneck,
        "initial_pairs": [{"meaning": x["semantic_graph"], "signal": x["orthographic_sentence"]} for x in language["examples"]],
        "basis": {"source": "Kirby, Cornish & Smith 2008", "doi": "10.1073/pnas.0707835105"},
    }
    p = Path(out); p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return p


def export_babel_constructions(language: dict, out: str | Path) -> Path:
    payload = {
        "schema": "losica-fcg-constructions/1", "source": "Babel/Fluid Construction Grammar representation contract",
        "constructions": [{"name": x["name"], "form_constraints": x["form_constraints"], "meaning": x["semantic_input"]} for x in language["constructions"]],
    }
    p = Path(out); p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return p
