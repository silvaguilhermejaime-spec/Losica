"""UniMorph-shaped inflection, derivation, and paradigm execution."""
from __future__ import annotations

from itertools import product

from .config import PhonologyConfig
from .lexicon_v021 import FormAllocator
from .morphophonology import Morpheme, realize_morphemes
from .semantic_core import meaning_cell_id, meaning_partition_id

UNIMORPH_VERSION = "schema current at Losica v0.26; 23 dimensions / 212+ features"

NOUN_BASE = {"number": "SG", "case": "NOM"}
VERB_BASE = {"polarity": "POS", "aspect": "IPFV", "tense": "NPST", "mood": "IND", "voice": "ACT", "evidentiality": None}


def _distribution_for_category(category: str) -> dict:
    return {
        "noun": {"heads_np": True, "takes_case": True, "takes_number": True, "predicate_requires_copula": True},
        "verb": {"heads_clause": True, "takes_tam": True, "licenses_arguments": True, "takes_subject_agreement": True},
        "property": {"modifies_noun": True, "predicative_with_copula": True, "takes_degree": True},
        "adverb": {"modifies_clause": True, "semantic_domain": "manner_or_degree"},
    }.get(category, {"category": category})


def _affix(allocator: FormAllocator, attachment: str) -> str:
    # One-syllable exponents make the boundary trace easy to inspect; the
    # compositor repairs every boundary before realization.
    return allocator.take(lambda x: "." not in x)


def _dimension(values: list[str], base: str | None, allocator: FormAllocator, attachment: str, dim: str) -> dict:
    partition_id = meaning_partition_id(f"morphology-{dim}")
    forms = {}
    for value in values:
        forms[value] = "" if value == base else _affix(allocator, attachment)
    cells = [{
        "cell_id": meaning_cell_id(f"{partition_id[3:]}-{value if value is not None else 'none'}"),
        "partition_id": partition_id,
        "value": value,
        "exponent": forms.get(value, ""),
    } for value in (values or [None])]
    return {"partition_id": partition_id, "dimension": dim, "values": values, "exponents": forms, "attachment": attachment, "cells": cells}


def allocate_morphology(profile: dict, allocator: FormAllocator, *, seed: int) -> dict:
    p = profile["morphology"]
    attachment = p["dominant_attachment"]
    noun_number = _dimension(p["noun"]["number"], "SG", allocator, attachment, "Number")
    noun_case = _dimension(p["noun"]["case"], "NOM", allocator, attachment, "Case")
    # A phonologically conditioned plural allomorph generalizes across eligible
    # hosts by segment features.
    plural_allomorphy = []
    if "PL" in noun_number["exponents"]:
        plural_allomorphy.append({
            "dimension": "number", "value": "PL", "condition": {"host_final_feature": "+labial"},
            "default_form": noun_number["exponents"]["PL"], "conditioned_form": _affix(allocator, attachment),
            "basis": "PHOIBLE distinctive feature conditioning", "host_id_specific": False,
        })

    vp = p["verb"]
    verbal_dimensions = {
        "polarity": _dimension(vp["polarity"], "POS", allocator, attachment, "Polarity"),
        "aspect": _dimension(vp["aspect"], "IPFV", allocator, attachment, "Aspect"),
        "tense": _dimension(vp["tense"], "NPST", allocator, attachment, "Tense"),
        "mood": _dimension(vp["mood"], "IND", allocator, attachment, "Mood"),
        "voice": _dimension(vp.get("voice", ["ACT"]), "ACT", allocator, attachment, "Voice"),
        "evidentiality": _dimension(vp.get("evidentiality", []), None, allocator, attachment, "Evidentiality"),
        "subject_index": _dimension(vp["subject_index"], None, allocator, attachment, "SubjectIndex"),
    }
    deriv_specs = {
        "CAUS": ("verb", "verb", "add_causer_and_demote_subject"),
        "APPL": ("verb", "verb", "promote_oblique_to_core_object"),
        "PASS": ("verb", "verb", "suppress_agent_and_promote_patient"),
        "ANTIP": ("verb", "verb", "suppress_patient_and retain_agent"),
        "NMLZ": ("verb", "noun", "reify_event_or_participant"),
        "ADJZ": ("noun", "property", "form_property_predicate"),
        "ADVZ": ("property", "adverb", "form_manner_modifier"),
    }
    derivation = {}
    for name in p.get("derivation", []):
        if name in deriv_specs:
            incat, outcat, effect = deriv_specs[name]
            derivation[name] = {
                "morpheme_id": f"DERIV-{name}", "form": _affix(allocator, attachment), "attachment": attachment,
                "input_category": incat, "output_category": outcat, "semantic_effect": effect,
                "productive": True, "recursive": True, "unimorph_feature": name if name in {"CAUS", "PASS", "ANTIP"} else None,
            }

    noun_template = "STEM-NUMBER-CASE" if attachment == "suffix" else "CASE-NUMBER-STEM"
    verb_order = ["polarity", "aspect", "tense", "mood", "voice", "evidentiality", "subject_index"]
    verb_template = "STEM-POLARITY-ASPECT-TENSE-MOOD-SUBJECT" if attachment == "suffix" and vp.get("voice", ["ACT"]) == ["ACT"] and not vp.get("evidentiality") else (
        "STEM-" + "-".join(x.upper() for x in verb_order) if attachment == "suffix" else "-".join(x.upper() for x in reversed(verb_order)) + "-STEM"
    )
    partitions = [noun_number, noun_case, *verbal_dimensions.values()]
    return {
        "schema": "losica-morphology/2",
        "unimorph": {"schema_version": UNIMORPH_VERSION, "bundle_storage": "dimension-value map"},
        "attachment": attachment,
        "meaning_partitions": [{
            "partition_id": partition["partition_id"],
            "dimension": partition["dimension"],
            "cell_ids": [cell["cell_id"] for cell in partition["cells"]],
        } for partition in partitions],
        "cells": [cell for partition in partitions for cell in partition["cells"]],
        "noun": {"number": noun_number["exponents"], "case": noun_case["exponents"], "dimensions": {"number": noun_number, "case": noun_case}, "template": noun_template},
        "verb": {**{k: v["exponents"] for k, v in verbal_dimensions.items()}, "dimensions": verbal_dimensions, "template": verb_template},
        "derivation": derivation,
        "morpheme_order": {
            "noun": ["stem", "number", "case"] if attachment == "suffix" else ["case", "number", "stem"],
            "verb": ["stem"] + verb_order if attachment == "suffix" else list(reversed(verb_order)) + ["stem"],
            "source": "sampled typological profile",
        },
        "syncretism": [{"category": "noun", "cells": [{"case": "NOM", "number": "SG"}], "exponent": "zero"}],
        "zero_realization": [{"dimension": "number", "value": "SG"}, {"dimension": "case", "value": "NOM"}, {"dimension": "polarity", "value": "POS"}, {"dimension": "tense", "value": "NPST"}],
        "cumulative_exponence": [{"dimension": "subject_index", "combines": ["Reference"], "values": vp["subject_index"]}],
        "multiple_exponence": [{"feature": "NEG", "realizations": ["bound polarity exponent", "negator particle in negative construction"]}],
        "allomorphy": plural_allomorphy,
        "paradigm_gaps": [],
        "provenance": {"entity": "morphological system", "representation": "feature dimensions and exponents", "inputs": [profile["id"], "UniMorph"], "transformation": "profile-conditioned exponent allocation", "outputs": [noun_template, verb_template], "seed": seed},
    }


def _host_final_labial(form: str) -> bool:
    plain = form.replace(".", "")
    return plain.endswith(("p", "m"))


def _morpheme_for(dim: str, value: str, partition: dict, morphology: dict, host_form: str) -> Morpheme:
    form = partition["exponents"].get(value, "")
    for rule in morphology.get("allomorphy", []):
        if rule["dimension"] == dim and rule["value"] == value and _host_final_labial(host_form):
            form = rule["conditioned_form"]
    cell = next(cell for cell in partition["cells"] if cell["value"] == value)
    return Morpheme(cell["cell_id"], form, str(value), morphology["attachment"])


def realize_inflection(lexeme: dict, bundle: dict, morphology: dict, cfg: PhonologyConfig, profile: dict, orthography: dict[str, str]) -> dict:
    category = "verb" if lexeme["class"] in {"verb", "auxiliary"} else "noun"
    order = morphology["morpheme_order"][category]
    dimensions = morphology[category]
    morphemes = []
    meaning_cells = []
    for slot in order:
        if slot == "stem":
            morphemes.append(Morpheme(lexeme["lexeme_id"], lexeme["underlying_form"], lexeme["lemma"], "root"))
        else:
            value = bundle[slot]
            partition = dimensions["dimensions"][slot]
            cell = next(cell for cell in partition["cells"] if cell["value"] == value)
            meaning_cells.append({"partition_id": partition["partition_id"], "cell_id": cell["cell_id"]})
            morphemes.append(_morpheme_for(slot, value, partition, morphology, lexeme["underlying_form"]))
    realized = realize_morphemes(
        morphemes, cfg, rules=profile["morphology"]["morphophonology"],
        prominence_rule=profile["prosody"]["word_prominence_rule"], orthography=orthography,
    )
    realized["orthographic"] = realized.get("orthographic") or ""
    return {
        **bundle,
        "feature_bundle": {k: v for k, v in bundle.items()},
        "meaning_cells": meaning_cells,
        "unimorph": ";".join(str(v) for v in bundle.values() if v not in (None, "NONE")),
        "form": realized["surface_phonemic"],
        "orthographic": realized["orthographic"],
        "underlying_form": realized["underlying_form"],
        "morpheme_sequence": realized["morpheme_sequence"],
        "morpheme_glosses": realized["morpheme_glosses"],
        "morphophonology": realized["operations"],
        "prominence": realized["prominence"],
        "annotated_form": realized["annotated_form"],
    }


def noun_bundles(morphology: dict):
    for number, case in product(morphology["noun"]["number"], morphology["noun"]["case"]):
        yield {"number": number, "case": case}


def verb_bundles(morphology: dict):
    order = ["polarity", "aspect", "tense", "mood", "voice", "evidentiality", "subject_index"]
    dimensions = [list(morphology["verb"][x]) or [None] for x in order]
    for values in product(*dimensions):
        yield dict(zip(order, values))


def generate_paradigms(lexicon: list[dict], morphology: dict, cfg: PhonologyConfig, profile: dict, orthography: dict[str, str]) -> dict[str, list[dict]]:
    out = {}
    noun_rows = list(noun_bundles(morphology))
    verb_rows = list(verb_bundles(morphology))
    for lexeme in lexicon:
        if lexeme["class"] == "noun":
            out[lexeme["lexeme_id"]] = [realize_inflection(lexeme, b, morphology, cfg, profile, orthography) for b in noun_rows]
        elif lexeme["class"] in {"verb", "auxiliary"}:
            out[lexeme["lexeme_id"]] = [realize_inflection(lexeme, b, morphology, cfg, profile, orthography) for b in verb_rows]
    return out


def derive_lexeme(base: dict, process: str, morphology: dict, cfg: PhonologyConfig, profile: dict, orthography: dict[str, str], lexeme_id: str) -> dict:
    spec = morphology["derivation"][process]
    if base["class"] != spec["input_category"]:
        raise ValueError(f"derivation {process} requires {spec['input_category']}, received {base['class']}")
    seq = [Morpheme(base["lexeme_id"], base["underlying_form"], base["lemma"], "root"), Morpheme(spec["morpheme_id"], spec["form"], process, spec["attachment"])]
    if spec["attachment"] == "prefix":
        seq.reverse()
    realized = realize_morphemes(seq, cfg, rules=profile["morphology"]["morphophonology"], prominence_rule=profile["prosody"]["word_prominence_rule"], orthography=orthography)
    argument = base.get("argument_structure")
    if argument:
        argument = {**argument}
        if process == "CAUS":
            argument = {"valency": argument["valency"] + 1, "roles": ["CAUSER"] + argument["roles"], "required_roles": ["CAUSER"] + argument["required_roles"], "alternations": argument["alternations"]}
        elif process in {"PASS", "ANTIP"}:
            argument = {"valency": max(1, argument["valency"] - 1), "roles": argument["roles"][1:] if process == "PASS" else argument["roles"][:-1], "required_roles": argument["required_roles"][1:] if process == "PASS" else argument["required_roles"][:-1], "alternations": argument["alternations"]}
    output_category = spec["output_category"]
    if output_category != "verb":
        argument = None
    semantic_id = f"d:{base['lexeme_id']}:{process}"
    return {
        **base, "lexeme_id": lexeme_id, "lemma": semantic_id, "concept": semantic_id,
        "concepticon_id": None, "concept_mappings": [],
        "class": output_category, "distribution": _distribution_for_category(output_category),
        "underlying_form": realized["surface_phonemic"], "form": realized["surface_phonemic"],
        "syllables": realized["syllables"], "prominence": realized["prominence"], "annotated_form": realized["annotated_form"],
        "orthographic": realized["orthographic"], "argument_structure": argument, "formation": "productive_derivation",
        "derivational_history": [{"process": process, "base_lexeme_id": base["lexeme_id"], "semantic_effect": spec["semantic_effect"], "trace": realized}],
        "provenance": {"entity": "derived lexeme", "representation": "lexical form-meaning mapping", "inputs": [base["lexeme_id"], spec["morpheme_id"]], "transformation": process, "outputs": [realized["surface_phonemic"]], "source": "Losica productive morphology v0.26", "base_concepticon_ids": [x.get("concepticon_id") for x in base.get("concept_mappings", [])]},
    }


def compound_lexemes(parts: list[dict], cfg: PhonologyConfig, profile: dict, orthography: dict[str, str], lexeme_id: str, *, semantic_relation="modifier_head") -> dict:
    """Compose lexical stems through the active phonological grammar."""
    if len(parts) < 2 or any(x["class"] != "noun" for x in parts):
        raise ValueError("nominal compounding requires at least two noun lexemes")
    ordered = parts if profile["syntax"]["genitive_order"] == "GEN-N" else list(reversed(parts))
    morphemes = [Morpheme(x["lexeme_id"], x["underlying_form"], x["lemma"], "compound_stem") for x in ordered]
    realized = realize_morphemes(morphemes, cfg, rules=profile["morphology"]["morphophonology"], prominence_rule=profile["prosody"]["word_prominence_rule"], orthography=orthography)
    lemma = "_".join(x["lemma"] for x in parts)
    return {
        "lexeme_id": lexeme_id, "lemma": lemma, "concept": lemma, "concepticon_id": None, "concept_mappings": [],
        "class": "noun", "distribution": parts[-1]["distribution"], "argument_structure": None,
        "underlying_form": "".join(x["underlying_form"].replace(".", "") for x in ordered), "form": realized["surface_phonemic"],
        "syllables": realized["syllables"], "prominence": realized["prominence"], "annotated_form": realized["annotated_form"],
        "orthographic": realized["orthographic"], "formation": "productive_compounding",
        "compound_history": {"constituents": [x["lexeme_id"] for x in parts], "linearized_constituents": [x["lexeme_id"] for x in ordered], "semantic_relation": semantic_relation, "trace": realized},
        "provenance": {"entity": "compound lexeme", "representation": "compositional lexical form-meaning mapping", "inputs": [x["lexeme_id"] for x in parts], "transformation": f"profile-ordered {semantic_relation} compounding", "outputs": [realized["surface_phonemic"]], "source": "Losica productive morphology v0.26"},
    }
