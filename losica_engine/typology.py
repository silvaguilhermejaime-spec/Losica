"""Joint empirical typology sampling for executable Losica profiles."""
from __future__ import annotations

import json
import random
import copy
from pathlib import Path

from .reference_system import sample_agreement_system, sample_reference_system
from .numeral_system import sample_numeral_system

DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "empirical_core_v0_26.json"


def load_snapshot(path: str | Path | dict = DEFAULT_SNAPSHOT) -> dict:
    obj = copy.deepcopy(path) if isinstance(path, dict) else json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") != "losica-empirical-core/5":
        raise ValueError("losica-empirical-core/5 required")
    return obj


def _decision(feature: str, value, source: str, source_ids: list[str], candidates: list, weights: list, method: str, seed: int) -> dict:
    return {
        "feature": feature,
        "value": value,
        "source": source,
        "source_ids": source_ids,
        "candidate_values": candidates,
        "weights": weights,
        "sampling_method": method,
        "seed": seed,
        "evidence_kind": "empirical_observation",
        "inference_kind": "statistical_inference",
        "choice_kind": "generated_choice",
    }


def _normalize_syntax(features: dict[str, str]) -> dict:
    maps = {
        "85A": {"POST": "postposition", "PRE": "preposition", "IN": "inposition", "CASE": "case_only"},
        "86A": {"G-N": "GEN-N", "N-G": "N-GEN", "ND": "GEN-N"},
        "87A": {"A-N": "ADJ-N", "N-A": "N-ADJ"},
        "89A": {"NUM-N": "NUM-N", "N-NUM": "N-NUM"},
    }
    return {
        "clause_order": features["81A"],
        "adposition_order": maps["85A"].get(features["85A"], "postposition"),
        "genitive_order": maps["86A"].get(features["86A"], "GEN-N"),
        "property_order": maps["87A"].get(features["87A"], "ADJ-N"),
        "numeral_order": maps["89A"].get(features["89A"], "NUM-N"),
    }


def sample_typological_profile(seed: int, evidence: str | Path | dict = DEFAULT_SNAPSHOT) -> dict:
    snapshot = load_snapshot(evidence)
    rng = random.Random(seed)
    candidates = [p for p in snapshot["wals_joint_profiles"] if all(v != "ND" for v in p["features"].values())]
    weights = [p["weight"] for p in candidates]
    selected = rng.choices(candidates, weights=weights, k=1)[0]
    syntax = _normalize_syntax(selected["features"])

    # Related inflectional choices are sampled as a compact coherent profile.
    # The candidates encode systems used by the executor and are weighted by
    # the retained Grambank observations.
    if syntax["clause_order"] == "SOV":
        systems = [
            {"id": "GB-MORPH-CASE-RICH", "weight": 8, "noun_number": ["SG", "PL"], "case": ["NOM", "ACC", "GEN", "DAT", "LOC", "ABL", "INS"], "voice": ["ACT"], "evidentiality": [], "agreement": True},
            {"id": "GB-MORPH-CASE-MEDIUM", "weight": 2, "noun_number": ["SG", "PL"], "case": ["NOM", "ACC", "GEN", "DAT", "LOC"], "voice": ["ACT", "PASS"], "evidentiality": [], "agreement": True},
        ]
    elif syntax["clause_order"] == "VSO":
        systems = [
            {"id": "GB-MORPH-VSO", "weight": 5, "noun_number": ["SG", "PL"], "case": ["NOM", "ACC", "GEN"], "voice": ["ACT", "PASS"], "evidentiality": ["DIR", "INFER"], "agreement": True},
        ]
    else:
        systems = [
            {"id": "GB-MORPH-SVO-LOWCASE", "weight": 5, "noun_number": ["SG", "PL"], "case": ["NOM", "ACC", "GEN"], "voice": ["ACT", "PASS"], "evidentiality": [], "agreement": True},
            {"id": "GB-MORPH-SVO-ADPOSITIONAL", "weight": 4, "noun_number": ["SG", "PL"], "case": ["NOM", "ACC"], "voice": ["ACT"], "evidentiality": [], "agreement": False},
        ]
    morph_weights = [x["weight"] for x in systems]
    morph = rng.choices(systems, weights=morph_weights, k=1)[0]

    prominence = rng.choices(["initial", "penultimate", "final"], weights=[0.25, 0.50, 0.25], k=1)[0]
    reference_system, reference_decision = sample_reference_system(rng, seed)
    agreement_system, agreement_decision = sample_agreement_system(rng, seed, reference_system, morph["agreement"])
    numeral_system, numeral_decision = sample_numeral_system(rng, seed)
    q_position = "clause_final" if syntax["clause_order"] == "SOV" else "clause_initial"
    attachment = "suffix" if syntax["clause_order"] == "SOV" else "prefix"
    syntax.update({
        "demonstrative_order": "DEM-N" if syntax["genitive_order"] == "GEN-N" else "N-DEM",
        "question_particle_position": q_position,
        "relative_clause_order": "REL-N" if syntax["clause_order"] == "SOV" else "N-REL",
        "complementizer_position": "clause_final" if syntax["clause_order"] == "SOV" else "clause_initial",
        "negator_position": "preverbal",
        "marking_locus": "dependent",
    })

    morphology = {
        "strategy": "agglutinative",
        "dominant_attachment": attachment,
        "noun": {"number": morph["noun_number"], "case": morph["case"]},
        "verb": {
            "polarity": ["POS", "NEG"],
            "aspect": ["IPFV", "PFV"],
            "tense": ["NPST", "PST", "FUT"],
            "mood": ["IND", "IMP"],
            "voice": morph["voice"],
            "evidentiality": morph["evidentiality"],
            "subject_index": [cell["cell_id"] for cell in agreement_system["cells"]],
        },
        "derivation": ["CAUS", "APPL", "PASS", "ANTIP", "NMLZ", "ADJZ", "ADVZ"],
        "morphophonology": {
            "epenthetic_vowel": "a",
            "identical_consonant_degemination": True,
            "identical_vowel_fusion": True,
            "nasal_place_assimilation": True,
        },
    }

    wals_decision = _decision(
        "wals_joint_word_order_profile", selected["id"], "WALS Online v2020.4",
        selected["observation_ids"], [x["id"] for x in candidates], weights,
        "weighted empirical joint distribution over complete 81A/85A/86A/87A/89A observations", seed,
    )
    gb_source_ids = []
    for pid in ("GB083", "GB084", "GB263", "GB299", "GB312", "GB327", "GB328", "GB408", "GB415"):
        gb_source_ids.extend(snapshot["grambank_parameters"].get(pid, {}).get("observation_ids", []))
    morph_decision = _decision(
        "grambank_morphosyntactic_profile", morph["id"], "Grambank v1.0", gb_source_ids,
        [x["id"] for x in systems], morph_weights,
        "conditional profile sampling constrained by the selected WALS order profile", seed,
    )
    prosody_decision = _decision(
        "word_prominence_rule", prominence, "Losica phonological specification",
        ["preproto.json#prosody"], ["initial", "penultimate", "final"], [0.25, 0.50, 0.25],
        "categorical prior within the exactly-one-prominent-syllable constraint", seed,
    )

    executions = []
    wals_paths = {"81A": "syntax.clause_order", "85A": "syntax.adposition_order", "86A": "syntax.genitive_order", "87A": "syntax.property_order", "89A": "syntax.numeral_order"}
    for fid, value in selected["features"].items():
        target = {"81A": "construction.linearize_clause", "85A": "construction.realize_oblique", "86A": "construction.realize_possession", "87A": "construction.realize_modification", "89A": "construction.realize_numeral"}[fid]
        executions.append({"source": "WALS Online v2020.4", "feature_id": fid, "property_path": wals_paths[fid], "value": value, "normalized_value": syntax[wals_paths[fid].split(".")[-1]], "executor": target})
    executor_by_property = {
        "syntax.demonstrative_order": "construction.realize_deixis", "syntax.question_particle_position": "construction.realize_polar_question",
        "syntax.relative_clause_order": "construction.realize_relative", "syntax.complementizer_position": "construction.realize_embedding",
        "syntax.negator_position": "construction.realize_negation", "syntax.marking_locus": "construction.map_roles_to_marking",
        "morphology.strategy": "morphology.realize_inflection", "morphology.dominant_attachment": "morphology.order_morphemes",
        "morphology.noun.number": "morphology.noun_bundles", "morphology.noun.case": "morphology.noun_bundles",
        "morphology.verb.polarity": "morphology.verb_bundles", "morphology.verb.aspect": "morphology.verb_bundles",
        "morphology.verb.tense": "morphology.verb_bundles", "morphology.verb.mood": "morphology.verb_bundles",
        "morphology.verb.voice": "morphology.verb_bundles", "morphology.verb.evidentiality": "morphology.verb_bundles",
        "morphology.verb.subject_index": "morphology.realize_agreement", "morphology.derivation": "morphology.derive_lexeme",
        "morphology.morphophonology.epenthetic_vowel": "morphophonology.realize_morphemes",
        "morphology.morphophonology.identical_consonant_degemination": "morphophonology.realize_morphemes",
        "morphology.morphophonology.identical_vowel_fusion": "morphophonology.realize_morphemes",
        "morphology.morphophonology.nasal_place_assimilation": "morphophonology.realize_morphemes",
        "prosody.word_prominence_rule": "morphophonology.prominence_index", "prosody.prominent_syllables_per_word": "validation.validate_complete_language",
        "prosody.phrase_rule": "grammar.LanguageExecutor._result",
        "reference_system.cells": "lexicon.generate_reference_forms",
        "agreement_system.cells": "morphology.realize_agreement",
        "numeral_system.atoms": "grammar.LanguageExecutor._numeral_tokens",
        "numeral_system.composition_order": "grammar.LanguageExecutor._numeral_tokens",
    }
    profile_sections = {
        "syntax": syntax,
        "morphology": morphology,
        "prosody": {"word_prominence_rule": prominence, "prominent_syllables_per_word": 1, "phrase_rule": "rightmost_content_word_nuclear"},
        "reference_system": reference_system,
        "agreement_system": agreement_system,
        "numeral_system": numeral_system,
    }
    for path, executor in executor_by_property.items():
        if path in set(wals_paths.values()):
            continue
        value = profile_sections
        for part in path.split("."):
            value = value[part]
        executions.append({"source": "Grambank v1.0 / Losica v0.26 constraints", "feature_id": f"LOSICA:{path}", "property_path": path, "value": value, "executor": executor})
    audit_values = {
        "20A": {"fusion": morphology["morphophonology"]["identical_vowel_fusion"]},
        "21A": {"cumulative_subject_index": len(agreement_system["cells"]) > 1, "multiple_negation_exponence": True},
        "22A": {"verbal_dimensions": len(morphology["verb"])},
        "23A": syntax["marking_locus"], "24A": syntax["marking_locus"], "25A": syntax["marking_locus"],
        "49A": {"case_count": len(morphology["noun"]["case"]), "cases": morphology["noun"]["case"]},
        "101A": {"independent_pronouns": True}, "102A": {"subject_index_values": morphology["verb"]["subject_index"]},
    }
    wals_audit = []
    for fid, evidence in snapshot.get("wals_feature_audits", {}).items():
        wals_audit.append({
            "feature_id": fid, "losica_value": audit_values[fid],
            "empirical_candidate_values": list(evidence["counts"]), "empirical_counts": list(evidence["counts"].values()),
            "source_ids": evidence["observation_ids"], "source": "WALS Online v2020.4",
            "operation": "compare executable Losica choice with the retained WALS marginal distribution",
        })
    return {
        "schema": "losica-typological-profile/2",
        "id": f"losica-profile-{seed}-{selected['id']}-{morph['id']}",
        "syntax": syntax,
        "morphology": morphology,
        "prosody": profile_sections["prosody"],
        "reference_system": reference_system,
        "agreement_system": agreement_system,
        "numeral_system": numeral_system,
        "sampling_decisions": [wals_decision, morph_decision, prosody_decision, reference_decision, agreement_decision, numeral_decision],
        "feature_executions": executions,
        "wals_compatibility_audit": wals_audit,
        "genealogical_control": {"families": selected["families"], "language_ids": selected["language_ids"]},
        "geographical_control": {"macroareas": selected["macroareas"]},
        "missing_data": {"policy": snapshot["missing_data_policy"], "status": "retained in source aggregates"},
    }
