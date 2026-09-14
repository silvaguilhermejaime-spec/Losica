"""Structural semantic-region and lexical-form generation."""
from __future__ import annotations

import random
import hashlib
from dataclasses import dataclass
from itertools import product
from pathlib import Path

from .config import PhonologyConfig
from .morphophonology import prominence_index
from .phonology import legal_syllables, syllabify_surface
from .semantic_core import FUNCTION_SPECS, frame_structure, lexical_item_id
from .semantic_network import generate_semantic_regions, region_class
from .numeral_system import numeral_semantic_id

VOCABULARY_SCALES = {"core": 128, "intermediate": 256, "large": 512}


@dataclass
class FormAllocator:
    forms: list[str]
    rng: random.Random

    @classmethod
    def create(cls, cfg: PhonologyConfig, rng: random.Random, reserved: set[str] | None = None):
        syllables = list(legal_syllables(cfg))
        forms = set(syllables)
        for a, b in product(syllables, repeat=2):
            forms.add(".".join(syllabify_surface(a + b, cfg)))
            if len(forms) >= 4096:
                break
        forms = sorted(forms)
        forms = [x for x in forms if x.replace(".", "") not in (reserved or set())]
        rng.shuffle(forms)
        return cls(forms, rng)

    def take(self, predicate=None) -> str:
        for i, form in enumerate(self.forms):
            if predicate is None or predicate(form):
                return self.forms.pop(i)
        raise ValueError("phonological form pool exhausted under the requested constraint")


def concept_target(snapshot: dict, scale: str) -> int:
    if scale not in VOCABULARY_SCALES:
        raise ValueError(f"vocabulary scale must be one of {sorted(VOCABULARY_SCALES)}")
    return min(VOCABULARY_SCALES[scale], len(snapshot["concepts"]))


def _distribution(cls: str) -> dict:
    return {
        "noun": {"heads_np": True, "takes_case": True, "takes_number": True, "predicate_requires_copula": True},
        "verb": {"heads_clause": True, "takes_tam": True, "licenses_arguments": True, "takes_subject_agreement": True},
        "property": {"modifies_noun": True, "predicative_with_copula": True, "takes_degree": True},
    }[cls]


def _select_concepts(snapshot: dict, scale: str, seed: int) -> list[dict]:
    """Compatibility view of the structural probe selection."""
    from .semantic_network import select_probes
    return select_probes(snapshot, concept_target(snapshot, scale), seed)


def generate_lexicon(evidence: dict, cfg: PhonologyConfig, profile: dict, *, seed: int, scale: str, project_root: Path, display_labels: dict | None = None) -> tuple[list[dict], FormAllocator, list[dict]]:
    rng = random.Random(seed ^ 0x4C455849)
    allocator = FormAllocator.create(cfg, rng)
    target = concept_target(evidence, scale)
    regions, decisions = generate_semantic_regions(evidence, target, seed)
    lexicon = []
    for region in regions:
        cls = region_class(region)
        frame_id = region.get("frame_id")
        form = allocator.take()
        pindex = prominence_index(form.split("."), profile["prosody"]["word_prominence_rule"])
        mappings = [{
            "concepticon_id": anchor["concepticon_id"],
            "links": list(anchor["links"]),
            "concept": anchor["probe_id"],
            "probe_id": anchor["probe_id"],
            "membership": anchor["membership"],
            "structural_evidence": anchor.get("structural_evidence", {}),
            "membership_record": anchor["membership_record"],
        } for anchor in region["anchors"]]
        argument_structure = frame_structure(frame_id) if cls == "verb" and frame_id else None
        lexicon.append({
            "lexeme_id": lexical_item_id(f"{len(lexicon)+1:04d}"),
            "semantic_region_id": region["region_id"],
            "semantic_region": region,
            "lemma": region["region_id"],
            "concept": region["region_id"],
            "concepticon_id": None,
            "concept_mappings": mappings,
            "class": cls,
            "distribution": _distribution(cls),
            "argument_structure": argument_structure,
            "underlying_form": form,
            "form": form,
            "syllables": form.split("."),
            "prominence": pindex,
            "annotated_form": ".".join(("ˈ" if i == pindex else "") + syll for i, syll in enumerate(form.split("."))),
            "formation": "semantic_region_lexicalization",
            "provenance": {
                "entity": "lexeme",
                "representation": "Losica lexicalization of an internally generated semantic region",
                "inputs": [region["region_id"]],
                "transformation": "semantic-region lexicalization plus phonotactic form allocation",
                "outputs": [form],
                "semantic_region": {
                    "region_id": region["region_id"],
                    "community_id": region["community_id"],
                    "semantic_mode": region["semantic_mode"],
                    "frame_id": frame_id,
                    "anchor_probe_ids": [m["probe_id"] for m in mappings],
                },
                "clics": {
                    "version": evidence.get("colexification_prior", {}).get("version"),
                    "edges": region.get("direct_edge_evidence", []),
                    "evidence_channel": "semantic topology",
                },
                "seed": seed,
            },
        })

    for cell in profile["reference_system"]["cells"]:
        semantic_id = cell["cell_id"]
        form = allocator.take(); syllables = form.split(".")
        pindex = prominence_index(syllables, profile["prosody"]["word_prominence_rule"])
        lexicon.append({
            "lexeme_id": lexical_item_id(f"{len(lexicon)+1:04d}"), "lemma": semantic_id, "concept": semantic_id, "concepticon_id": None,
            "concept_mappings": [], "class": "pronoun", "distribution": {"closed_class": True, "licensed_by": cell["condition"]},
            "argument_structure": None, "reference_cell": cell["cell_id"], "meaning_partition_id": cell["partition_id"], "grammatical_features": cell["condition"],
            "underlying_form": form, "form": form, "syllables": syllables, "prominence": pindex,
            "annotated_form": ".".join(("ˈ" if i == pindex else "") + x for i, x in enumerate(syllables)),
            "formation": "generated_reference_form",
            "provenance": {"entity": "lexeme", "representation": "generated reference-cell realization", "inputs": [cell], "transformation": "reference-partition form allocation", "outputs": [form], "seed": seed},
        })

    for value in profile["numeral_system"]["atoms"]:
        semantic_id = numeral_semantic_id(value)
        form = allocator.take(); syllables = form.split(".")
        pindex = prominence_index(syllables, profile["prosody"]["word_prominence_rule"])
        lexicon.append({
            "lexeme_id": lexical_item_id(f"{len(lexicon)+1:04d}"), "lemma": semantic_id, "concept": semantic_id, "concepticon_id": None,
            "concept_mappings": [], "class": "numeral", "distribution": {"closed_class": True, "licensed_by": {"numeral_value": value}},
            "argument_structure": None, "grammatical_features": {"numeral_value": value},
            "underlying_form": form, "form": form, "syllables": syllables, "prominence": pindex,
            "annotated_form": ".".join(("ˈ" if i == pindex else "") + x for i, x in enumerate(syllables)),
            "formation": "generated_numeral_form",
            "provenance": {"entity": "lexeme", "representation": "generated numeral-atom realization", "inputs": [value, profile["numeral_system"]["system_id"]], "transformation": "numeral-system form allocation", "outputs": [form], "seed": seed},
        })

    for semantic_id, cls, features, argument_structure in FUNCTION_SPECS:
        form = allocator.take(); syllables = form.split(".")
        pindex = prominence_index(syllables, profile["prosody"]["word_prominence_rule"])
        lexicon.append({
            "lexeme_id": lexical_item_id(f"{len(lexicon)+1:04d}"), "lemma": semantic_id, "concept": semantic_id, "concepticon_id": None,
            "concept_mappings": [], "class": cls, "distribution": {"closed_class": True, "licensed_by": features},
            "argument_structure": argument_structure, "grammatical_features": features, "underlying_form": form, "form": form, "syllables": syllables, "prominence": pindex,
            "annotated_form": ".".join(("ˈ" if i == pindex else "") + x for i, x in enumerate(syllables)),
            "formation": "generated_grammatical_form",
            "provenance": {"entity": "lexeme", "representation": "grammatical semantic realization", "inputs": [semantic_id, features], "transformation": "profile-driven closed-class allocation", "outputs": [form], "seed": seed},
        })
    if display_labels is not None:
        from .display_en import attach_display_labels
        attach_display_labels(lexicon, display_labels)
    return lexicon, allocator, decisions


def by_concept(lexicon: list[dict]) -> dict[str, dict]:
    out = {}
    strengths = {}
    for lexeme in lexicon:
        out[lexeme["concept"]] = lexeme
        for mapping in lexeme.get("concept_mappings", []):
            key = mapping["concept"]
            strength = float(mapping.get("membership", 1.0))
            if strength > strengths.get(key, -1.0):
                out[key] = lexeme
                strengths[key] = strength
    return out
