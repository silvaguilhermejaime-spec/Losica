"""Optional English display metadata for generated Losica states."""
from __future__ import annotations

import json
from pathlib import Path

from . import semantic_core as s

DEFAULT_DISPLAY_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "display_en_v0_26.json"

FUNCTION_LABELS = {
    s.G_DEM_PROX: "this", s.G_DEM_DIST: "that",
    s.G_INT_PERSON: "who", s.G_INT_THING: "what", s.G_INT_PLACE: "where",
    s.G_QUANT_UNIV: "all", s.G_QUANT_EXIST: "some",
    s.G_COORD_ADD: "and", s.G_COORD_ALT: "or",
    s.G_Q_POLAR: "question", s.G_NEG: "negator", s.G_COMP: "complementizer",
    s.G_REL: "relativizer", s.G_IMP: "imperative", s.G_COP: "copula",
    s.G_EXIST: "exist", s.G_ADP_LOC: "inside", s.G_ADP_SOURCE: "from", s.G_ADP_INSTR: "with",
    s.G_TIME_ALWAYS: "always", s.G_MANNER_PROX: "like this",
}


def load_english_display_labels(snapshot_path: str | Path = DEFAULT_DISPLAY_SNAPSHOT) -> dict[str, str]:
    snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    return {str(row["concepticon_id"]): row["gloss"].lower() for row in snapshot["concepts"]} | FUNCTION_LABELS


def attach_display_labels(lexicon: list[dict], display_labels: dict) -> None:
    concept_labels = {str(key): str(value) for key, value in display_labels.items()}
    for lexeme in lexicon:
        object_ids = [
            str(link["object_id"])
            for mapping in lexeme.get("concept_mappings", [])
            for link in mapping.get("links", [])
            if link.get("namespace") == "concepticon"
        ]
        aliases = [concept_labels.get(object_id, concept_labels.get(f"c:{object_id}")) for object_id in object_ids]
        aliases = [label for label in aliases if label is not None]
        label = (aliases[0] if aliases else None) or concept_labels.get(lexeme["concept"])
        if lexeme.get("class") == "numeral" and lexeme["concept"].startswith("n:"):
            label = lexeme["concept"][2:]
        if lexeme.get("reference_cell"):
            label = lexeme["reference_cell"]
        if label is None and lexeme.get("derivational_history"):
            history = lexeme["derivational_history"][0]
            base = next((x for x in lexicon if x["lexeme_id"] == history["base_lexeme_id"]), None)
            base_label = (base or {}).get("display", {}).get("en") or concept_labels.get((base or {}).get("concept"))
            process = history["process"]
            if base_label:
                label = {"NMLZ": f"event/entity of {base_label}", "ADJZ": f"{base_label}-property", "ADVZ": f"in a {base_label} manner"}.get(process, f"{base_label}:{process.lower()}")
        display = lexeme.setdefault("display", {})
        display["en"] = label or lexeme["lexeme_id"]
        if aliases:
            display["en_aliases"] = aliases


def attach_english_display(lexicon: list[dict], snapshot_path: str | Path = DEFAULT_DISPLAY_SNAPSHOT) -> None:
    attach_display_labels(lexicon, load_english_display_labels(snapshot_path))
