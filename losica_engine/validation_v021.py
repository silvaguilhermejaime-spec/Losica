"""Cross-layer invariants for a generated v0.26 language state."""
from __future__ import annotations

from pathlib import Path

from .config import load_phonology
from .grammar_v021 import LanguageExecutor, semantic_equivalent
from .surface_analysis import analyze_surface
from .morphology_v021 import noun_bundles, verb_bundles
from .morphophonology import phonemic_from_orthography
from .phonology import is_legal_surface


def validate_complete_language(state: dict, phonology_path: str | Path | None = None) -> dict:
    cfg = load_phonology(phonology_path or Path(__file__).resolve().parents[1] / "config/preproto.json")
    errors = []
    lexical_checks = paradigm_checks = sentence_token_checks = orthography_checks = semantic_checks = 0
    mapping = state["orthography"]["segment_symbols"]
    for row in state["lexicon"]:
        lexical_checks += 1
        if not row["lexeme_id"].startswith("lx:"):
            errors.append(f"lexeme {row['lexeme_id']} lacks an lx: lexical-item identifier")
        if not is_legal_surface(row["form"], cfg): errors.append(f"lexeme {row['lexeme_id']} lacks a legal active-stage parse")
        orthography_checks += 1
        if phonemic_from_orthography(row["orthographic"], mapping, cfg).replace(".", "") != row["form"].replace(".", ""):
            errors.append(f"lexeme {row['lexeme_id']} has an orthography-to-phoneme mapping mismatch")
        if row["annotated_form"].count("ˈ") != 1: errors.append(f"lexeme {row['lexeme_id']} requires exactly one prominent syllable")
        for concept in row.get("concept_mappings", []):
            links = concept.get("links", [])
            if not links or any(set(link) != {"namespace", "object_id"} or link["namespace"] != "concepticon" for link in links):
                errors.append(f"lexeme {row['lexeme_id']} has an unbound Concepticon mapping")
            membership = concept.get("membership_record", {})
            if set(membership) != {"algorithm", "evidence_edge_ids", "seed", "draw", "threshold", "accepted"} or bool(membership.get("accepted")) != (float(membership.get("draw", 1)) <= float(membership.get("threshold", 0))):
                errors.append(f"lexeme {row['lexeme_id']} has an invalid membership record")
    lexemes = {x["lexeme_id"]: x for x in state["lexicon"]}
    noun_expected = {tuple(sorted(x.items())) for x in noun_bundles(state["morphology"])}
    verb_expected = {tuple(sorted(x.items())) for x in verb_bundles(state["morphology"])}
    for lid, cells in state["paradigms"].items():
        if lid in {"sample_noun", "sample_verb"}:
            continue
        lexeme = lexemes.get(lid)
        if lexeme is None:
            errors.append(f"paradigm {lid} lacks a lexical host")
            continue
        observed = {tuple(sorted(c["feature_bundle"].items())) for c in cells}
        expected = verb_expected if lexeme["class"] in {"verb", "auxiliary"} else noun_expected
        if observed != expected:
            errors.append(f"paradigm {lid} must equal its licensed feature product")
        for cell in cells:
            paradigm_checks += 1
            if not is_legal_surface(cell["form"], cfg): errors.append(f"paradigm {lid} has an illegal cell")
            if cell["annotated_form"].count("ˈ") != 1: errors.append(f"paradigm {lid} has a prominence violation")
            orthography_checks += 1
            if phonemic_from_orthography(cell["orthographic"], mapping, cfg).replace(".", "") != cell["form"].replace(".", ""):
                errors.append(f"paradigm {lid} has an orthography mismatch")
            for reference in cell.get("meaning_cells", []):
                partition = next((p for p in state["morphology"].get("meaning_partitions", []) if p["partition_id"] == reference["partition_id"]), None)
                if partition is None or reference["cell_id"] not in partition["cell_ids"]:
                    errors.append(f"paradigm {lid} refers to a morphology cell outside its partition")
    executor = LanguageExecutor(lexicon=state["lexicon"], paradigms=state["paradigms"], morphology=state["morphology"], profile=state["profile"])
    for example in state["examples"]:
        for token in example["tokens"]:
            sentence_token_checks += 1
            if not is_legal_surface(token, cfg): errors.append(f"example {example['construction_id']} contains an illegal token")
        semantic_checks += 1
        parsed = analyze_surface(state, example["orthographic_sentence"])
        if not any(semantic_equivalent(example["semantic_graph"], candidate) for candidate in parsed["analyses"]):
            errors.append(f"example {example['construction_id']} has surface-analysis coverage mismatch")
        regenerated = executor.realize(example["semantic_graph"])
        if regenerated["orthographic_sentence"] != example["orthographic_sentence"]:
            errors.append(f"example {example['construction_id']} has realization stability mismatch")
        if sum(bool(x.get("phrase_prominent")) for x in example["token_details"]) != 1:
            errors.append(f"example {example['construction_id']} lacks one phrase-level prominence target")
        arguments = example["semantic_graph"].get("arguments", {})
        for token in example["token_details"]:
            role, features = token.get("semantic_role"), token.get("features", {})
            if role and features.get("case") and features["case"] != executor._case(role):
                errors.append(f"example {example['construction_id']} contains unlicensed case for {role}")
            if token.get("deprel") == "root" and features.get("subject_index"):
                subject = arguments.get("AGENT") or arguments.get("THEME") or arguments.get("POSSESSED")
                if subject and features["subject_index"] != executor._subject_index(subject):
                    errors.append(f"example {example['construction_id']} requires a licensed controller for agreement")
    capability_checks = 0
    for probe in state.get("capability_probes", []):
        capability_checks += 1
        parsed = analyze_surface(state, probe["realization"])
        if not any(semantic_equivalent(probe["semantic_graph"], candidate) for candidate in parsed["analyses"]):
            errors.append(f"capability probe {probe['probe_id']} has surface-analysis coverage mismatch")

    for decision in state["profile"]["sampling_decisions"]:
        if not decision.get("source_ids") or not decision.get("sampling_method"):
            errors.append(f"typological decision {decision.get('feature')} lacks evidence binding")
    semantic_roots = [x for x in state["lexicon"] if x.get("formation") == "semantic_region_lexicalization"]
    multi_anchor_roots = 0
    probe_region_counts = {}
    for lexeme in semantic_roots:
        mappings = lexeme.get("concept_mappings", [])
        region = lexeme.get("semantic_region") or {}
        if lexeme.get("concept") != lexeme.get("semantic_region_id") or region.get("region_id") != lexeme.get("semantic_region_id"):
            errors.append(f"lexeme {lexeme['lexeme_id']} requires internal semantic-region identity")
        if not lexeme.get("semantic_region_id", "").startswith("sr:"):
            errors.append(f"lexeme {lexeme['lexeme_id']} requires an sr: meaning-region identifier")
        if not mappings or not region.get("community_id"):
            errors.append(f"lexeme {lexeme['lexeme_id']} requires structural semantic anchors")
        if len(mappings) > 1:
            multi_anchor_roots += 1
        for mapping_row in mappings:
            key = mapping_row.get("probe_id") or mapping_row.get("concept")
            probe_region_counts[key] = probe_region_counts.get(key, 0) + 1
    if semantic_roots and multi_anchor_roots == 0:
        errors.append("lexical semantic topology requires at least one multi-anchor region")
    if semantic_roots and not any(count > 1 for count in probe_region_counts.values()):
        errors.append("lexical semantic topology requires at least one overlapping probe-to-region mapping")
    morphology_partitions = {p["partition_id"]: set(p["cell_ids"]) for p in state["morphology"].get("meaning_partitions", [])}
    for partition_id, cell_ids in morphology_partitions.items():
        if not partition_id.startswith("sp:") or any(not cell_id.startswith("sc:") for cell_id in cell_ids):
            errors.append(f"morphology partition {partition_id} has non-canonical identifiers")
    for cell in state["morphology"].get("cells", []):
        if cell["cell_id"] not in morphology_partitions.get(cell["partition_id"], set()):
            errors.append(f"morphology cell {cell['cell_id']} does not belong to {cell['partition_id']}")
    stages = state["history"]["stages"]
    for index, stage in enumerate(stages):
        if stage["generation"] != index:
            errors.append(f"history stage {stage['stage_id']} has a non-sequential generation")
        expected_parent = None if index == 0 else stages[index - 1]["stage_id"]
        if stage.get("parent_stage_id") != expected_parent:
            errors.append(f"history stage {stage['stage_id']} has an incomplete ancestry link")
        for lid, form in stage["lexicon_forms"].items():
            if lid not in lexemes or not is_legal_surface(form, cfg):
                errors.append(f"history stage {stage['stage_id']} has an invalid descendant form for {lid}")
    if errors:
        raise ValueError("complete-language validation failed:\n" + "\n".join(errors[:50]))
    return {
        "status": "PASS", "lexical_forms": lexical_checks, "paradigm_cells": paradigm_checks,
        "sentence_tokens": sentence_token_checks, "orthography_mappings": orthography_checks,
        "semantic_round_trips": semantic_checks, "capability_probes": capability_checks,
        "profile_features": len(state["profile"]["feature_executions"]),
    }
