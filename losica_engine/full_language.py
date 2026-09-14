"""Losica v0.26 complete deterministic language generator."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .config import load_phonology
from .export_v021 import export_bundle
from .grammar_v021 import LanguageExecutor, clause, construction_inventory, entity, participant_reference, semantic_equivalent
from .surface_analysis import analyze_surface
from .historical_v021 import initial_history, run_usage_stage
from .lexicon_v021 import VOCABULARY_SCALES, by_concept, concept_target, generate_lexicon
from .morphology_v021 import allocate_morphology, compound_lexemes, derive_lexeme, generate_paradigms
from .morphophonology import orthographic_form
from .typology import DEFAULT_SNAPSHOT, load_snapshot, sample_typological_profile
from .semantic_core import G_COP, G_EXIST, G_INT_PERSON, G_QUANT_UNIV, lexical_item_id

SCHEMA = "losica-complete-language/2"
DEFAULT_PHONOLOGY = Path(__file__).resolve().parents[1] / "config/preproto.json"
DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "config/language_profile.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESENTATION_FIELDS = frozenset({"display"})


def remove_presentation_fields(value):
    if isinstance(value, dict):
        return {key: remove_presentation_fields(item) for key, item in value.items() if key not in PRESENTATION_FIELDS}
    if isinstance(value, list):
        return [remove_presentation_fields(item) for item in value]
    return copy.deepcopy(value)


def _evidence_sha256(evidence: dict) -> str:
    payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _generation_record(language: dict, evidence: dict, parameters: dict) -> dict:
    memberships = []
    for lexeme in language["lexicon"]:
        for mapping in lexeme.get("concept_mappings", []):
            membership = mapping.get("membership_record")
            if membership is None:
                continue
            link = next(link for link in mapping.get("links", []) if link.get("namespace") == "concepticon")
            memberships.append({
                "lexical_item_id": lexeme["lexeme_id"],
                "meaning_region_id": lexeme["semantic_region_id"],
                "concepticon_link": link,
                "record": copy.deepcopy(membership),
            })
    source_ids = set()
    for decision in language["profile"]["sampling_decisions"]:
        source_ids.update(map(str, decision.get("source_ids", [])))
    for item in memberships:
        source_ids.update(item["record"]["evidence_edge_ids"])
        source_ids.add(item["concepticon_link"]["object_id"])
    seeds = {language["seed"]}
    for decision in language["profile"]["sampling_decisions"]:
        if decision.get("seed") is not None:
            seeds.add(int(decision["seed"]))
    return {
        "schema": "losica-generation-record/1",
        "algorithm": "losica-complete-language-v1",
        "seed": language["seed"],
        "seeds": sorted(seeds),
        "evidence_sha256": _evidence_sha256(evidence),
        "evidence_ids": sorted(source_ids),
        "parameters": copy.deepcopy(parameters),
        "decisions": [copy.deepcopy(item["record"]) for item in memberships],
        "memberships": memberships,
    }


def replay_generation(record: dict, evidence: dict) -> dict:
    """Rebuild and verify a generated language from its recorded evidence and choices."""
    from .semantic_network import replay_membership

    evidence = load_snapshot(evidence)
    if record.get("schema") != "losica-generation-record/1" or record.get("algorithm") != "losica-complete-language-v1":
        raise ValueError("unsupported generation record")
    if record.get("evidence_sha256") != _evidence_sha256(evidence):
        raise ValueError("generation evidence does not match the recorded evidence digest")
    for membership in record.get("memberships", []):
        replay_membership(membership["record"], evidence)
    parameters = dict(record["parameters"])
    state = generate_complete_language(seed=int(record["seed"]), evidence=evidence, display_labels=None, **parameters)
    if state["generation_record"] != record:
        raise ValueError("regenerated decisions do not match the generation record")
    return remove_presentation_fields(state)


def _apply_profile_override(sampled: dict, path: str | Path | None) -> dict:
    if path is None or Path(path).resolve() == DEFAULT_PROFILE.resolve():
        return sampled
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema") not in {"losica-language-profile/1", "losica-typological-profile/2"}:
        raise ValueError("profile override requires losica-language-profile/1 or losica-typological-profile/2")
    out = copy.deepcopy(sampled)
    out["id"] += "-override"
    for section in ("syntax", "morphology", "prosody", "reference_system", "agreement_system", "numeral_system"):
        if section in obj and isinstance(obj[section], dict):
            for key, value in obj[section].items():
                if isinstance(value, dict) and isinstance(out.get(section, {}).get(key), dict):
                    out[section][key].update(value)
                else:
                    out[section][key] = value
    for execution in out["feature_executions"]:
        path_parts = execution.get("property_path", "").split(".")
        if len(path_parts) < 2:
            continue
        value = out
        try:
            for part in path_parts:
                value = value[part]
        except (KeyError, TypeError):
            continue
        execution["value"] = value
        if "normalized_value" in execution:
            execution["normalized_value"] = value
        execution["source"] = f"{execution['source']} + explicit profile override"
    out["sampling_decisions"].append({
        "feature": "profile_override", "value": str(path), "source": "user-supplied profile",
        "source_ids": [str(path)], "candidate_values": [str(path)], "weights": [1.0],
        "sampling_method": "explicit deterministic override", "seed": None,
        "evidence_kind": "empirical_or_user_observation", "inference_kind": "none", "choice_kind": "generated_choice",
    })
    return out


def _orthography(seed: int, cfg) -> dict:
    mapping = {x: x for x in (*cfg.consonants, *cfg.vowels)}
    mapping["kʼ"] = "q" if seed % 2 == 0 else "k'"
    return {
        "schema": "losica-orthography/2", "principle": "phonemic segment mapping", "segment_symbols": mapping,
        "syllable_separator": "", "word_separator": " ", "historical_conservatism": False,
        "rules": [{"input": seg, "output": graph, "environment": "all"} for seg, graph in mapping.items()],
        "provenance": {"entity": "orthography", "representation": "one-to-one grapheme map", "inputs": list(mapping), "transformation": "seeded grapheme selection", "outputs": list(mapping.values()), "seed": seed},
    }


def _derive_productive_lexemes(lexicon, morphology, cfg, profile, orthography):
    """Generate one productive category-changing derivative for each open-class root.

    This materializes the productive derivational grammar across the generated
    lexicon while keeping recursive derivation available through derive_lexeme().
    """
    process_for_class = {"verb": "NMLZ", "noun": "ADJZ", "property": "ADVZ"}
    result = []
    for base in list(lexicon):
        if base.get("formation") not in {"semantic_region_lexicalization"}:
            continue
        process = process_for_class.get(base.get("class"))
        if process not in morphology.get("derivation", {}):
            continue
        result.append(derive_lexeme(base, process, morphology, cfg, profile, orthography, lexical_item_id(f"der-{len(result)+1:04d}")))
    return result


def _fixture_inventory(lexicon: list[dict]) -> dict:
    """Select regression fixtures from Losica's generated lexical inventory."""
    roots = [x for x in lexicon if x.get("formation") == "semantic_region_lexicalization"]
    nouns = [x for x in roots if x.get("class") == "noun"]
    properties = [x for x in roots if x.get("class") == "property"]
    verbs = [x for x in roots if x.get("class") == "verb"]
    by_frame = {}
    for verb in verbs:
        frame = (verb.get("argument_structure") or {}).get("frame_id")
        by_frame.setdefault(frame, []).append(verb)
    required_frames = ("f:theme1", "f:patient2", "f:transfer3", "f:content2")
    if len(nouns) < 5 or not properties or any(frame not in by_frame for frame in required_frames):
        raise ValueError("generated lexical inventory lacks construction-fixture coverage")
    return {
        "nouns": nouns[:5], "property": properties[0],
        "intr": by_frame["f:theme1"][0], "trans": by_frame["f:patient2"][0],
        "ditr": by_frame["f:transfer3"][0], "content": by_frame["f:content2"][0],
    }


def _compound_sample_lexemes(lexicon, cfg, profile, orthography):
    fixture = _fixture_inventory(lexicon)
    nouns = fixture["nouns"][:4]
    pairs = ((nouns[0], nouns[1]), (nouns[2], nouns[3]))
    return [
        compound_lexemes([left, right], cfg, profile, orthography, lexical_item_id(f"cmp-{i:03d}"))
        for i, (left, right) in enumerate(pairs, 1)
    ]


def _example_meanings(lexicon: list[dict]) -> list[dict]:
    f = _fixture_inventory(lexicon)
    n1, n2, n3, n4, n5 = [entity(x["concept"]) for x in f["nouns"]]
    prop = f["property"]["concept"]
    intr, trans, ditr, content = (f[k]["concept"] for k in ("intr", "trans", "ditr", "content"))
    speaker = participant_reference(speaker="required", addressee="forbidden", cardinality=1)
    addressee = participant_reference(speaker="forbidden", addressee="required", cardinality=1)
    return [
        clause(trans, {"AGENT": n1, "PATIENT": n2}, features={"tense": "PST"}),
        clause(intr, {"THEME": n2}),
        clause(ditr, {"AGENT": n1, "PATIENT": n3, "RECIPIENT": n2}),
        clause(G_COP, {"THEME": n2, "ATTRIBUTE": entity(prop)}, construction="copular"),
        clause(G_EXIST, {"THEME": n5, "LOCATION": n4}, construction="existential"),
        clause(G_EXIST, {"POSSESSOR": n1, "POSSESSED": n4}, construction="possessive"),
        clause(G_COP, {"THEME": n1, "LOCATION": n4}, construction="locative"),
        {"type": "phrase", "head": entity(f["nouns"][1]["concept"], modifiers=[prop], deixis="PROX"), "construction": "modification"},
        {"type": "phrase", "head": entity(f["nouns"][4]["concept"], numeral=2), "construction": "numeral"},
        {"type": "phrase", "head": entity(f["nouns"][2]["concept"], number="PL", quantifier=G_QUANT_UNIV), "construction": "quantification"},
        clause(trans, {"AGENT": speaker, "PATIENT": n2}, features={"polarity": "NEG"}),
        clause(trans, {"AGENT": n1, "PATIENT": n2}, features={"question": "polar", "tense": "PST"}),
        clause(trans, {"AGENT": entity(G_INT_PERSON), "PATIENT": n2}, construction="content_question", features={"question": "content"}),
        clause(intr, {"AGENT": addressee}, features={"mood": "IMP"}),
        {"type": "coordination", "members": [clause(intr, {"THEME": n2}), clause(trans, {"AGENT": n2, "PATIENT": n3})]},
        clause(content, {"AGENT": n1, "CONTENT": clause(intr, {"THEME": n2})}, construction="complement"),
        clause(trans, {"AGENT": n1, "PATIENT": n2}, construction="relative"),
        clause(intr, {"AGENT": n1, "TIME": clause(intr, {"THEME": n2})}, construction="adverbial"),
    ]


def _capability_probes(language: dict) -> list[dict]:
    """Execute structural probes selected from the generated inventory."""
    f = _fixture_inventory(language["lexicon"])
    intr_base = f["intr"]
    nominal = next((
        x for x in language["lexicon"]
        if x.get("formation") == "productive_derivation"
        and x.get("class") == "noun"
        and x.get("derivational_history", [{}])[0].get("base_lexeme_id") == intr_base["lexeme_id"]
    ), None)
    if nominal is None:
        return []
    addressee = participant_reference(speaker="forbidden", addressee="required", cardinality=1)
    predication = clause(G_COP, {
        "THEME": entity(f["nouns"][0]["concept"], deixis="PROX"),
        "ATTRIBUTE": entity(f["property"]["concept"]),
    }, construction="copular")
    cognition = clause(f["content"]["concept"], {"AGENT": addressee, "CONTENT": predication}, construction="complement")
    graph = clause(f["intr"]["concept"], {
        "THEME": addressee,
        "SOURCE": entity(nominal["concept"]),
        "MANNER": cognition,
    }, construction="adverbial", features={"tense": "PST", "question": "polar"})
    executor = LanguageExecutor(
        lexicon=language["lexicon"], paradigms=language["paradigms"],
        morphology=language["morphology"], profile=language["profile"],
    )
    realization = executor.realize(graph)
    analysis = analyze_surface(language, realization["orthographic_sentence"])
    probes = [{
        "probe_id": "CAP-NESTED-EVENT-001", "semantic_graph": graph,
        "realization": realization["orthographic_sentence"], "analysis": analysis,
        "semantic_coverage": any(semantic_equivalent(graph, candidate) for candidate in analysis["analyses"]),
    }]
    numeral_graph = {"type": "phrase", "head": entity(f["nouns"][0]["concept"], numeral=123), "construction": "numeral"}
    numeral_realization = executor.realize(numeral_graph)
    numeral_analysis = analyze_surface(language, numeral_realization["orthographic_sentence"])
    probes.append({
        "probe_id": "CAP-CARDINAL-123-001", "semantic_graph": numeral_graph,
        "realization": numeral_realization["orthographic_sentence"], "analysis": numeral_analysis,
        "semantic_coverage": any(semantic_equivalent(numeral_graph, candidate) for candidate in numeral_analysis["analyses"]),
    })
    return probes


SOURCE_LEDGER = [
    ("Grambank", "1.0", "joint structural profile evidence"), ("WALS Online", "2020.4", "word-order joint profiles and audits"),
    ("UniMorph", "23 dimensions / 212+ features", "morphological feature vocabulary and paradigm evidence"),
    ("Concepticon", "3.4.0", "stable semantic-probe identifiers"), ("Concepticon CLICS-derived list", "2018-1105", "network rank and community topology"), ("CLICS3", "3", "cross-family colexification edges"),
    ("PHOIBLE", "2.0", "distinctive features and inventory audit"), ("Universal Dependencies", "2.18", "dependency relations and construction templates"),
    ("DELPH-IN Grammar Matrix", "external current", "typed-choice/executable-grammar architecture"), ("DELPH-IN Grammary", "2026", "optional construction coverage comparison"),
    ("CLDF", "current", "interoperable export validated with pycldf"), ("QBV", "Greif et al. 2024", "dual-encoder environmental/vocal retrieval contract"),
    ("RWCP-SSD-Onomatopoeia", "Okamoto et al. 2020", "population vocal-form calibration"), ("ESC-50-Voice", "2024", "paired vocal imitation audio; DOI 10.5281/zenodo.11385662"),
    ("VocalSketch", "CHI 2015", "imitation and listener-identification evidence"), ("Vocal Imitation Set", "DCASE 2018", "additional paired imitation corpus; DOI 10.5281/zenodo.1340763"),
    ("Allosaurus", "ICASSP 2020", "uncertain universal-phone hypotheses"), ("Brassica", "external current", "stress/tone/paradigm-aware history adapter"),
    ("Lexurgy", "external current", "canonical regular sound-change adapter"), ("SakanaAI LanguageEvolution", "2026", "population and morphological evolution adapter"),
    ("Babel/Fluid Construction Grammar", "external current", "form-meaning construction reference"), ("EGG", "external current", "optional emergent communication substrate"),
    ("Kirby, Cornish & Smith", "2008", "iterated transmission basis; DOI 10.1073/pnas.0707835105"),
    ("Bybee", "2006/2011", "usage, repetition, reduction, and grammaticalization"), ("Baayen et al.", "1992–1999+", "measured morphological productivity"),
    ("ConlangCrafter", "ACL 2026 Oral", "phonology+grammar+lexicon+translation completeness benchmark"),
]


def _source_ledger(snapshot: dict) -> list[dict]:
    version_keys = {"Grambank": "Grambank", "WALS Online": "WALS", "Concepticon": "Concepticon", "PHOIBLE": "PHOIBLE"}
    rows = []
    for source, version, role in SOURCE_LEDGER:
        row = {"source": source, "version": version, "role": role}
        if source in version_keys:
            pinned = snapshot["versions"][version_keys[source]]
            row.update({"version": pinned["version"], "commit": pinned["commit"], "evidence": "bundled compact snapshot"})
        rows.append(row)
    return rows


def generate_complete_language(
    *, phonology_path=DEFAULT_PHONOLOGY, profile_path=DEFAULT_PROFILE, empirical_snapshot_path=DEFAULT_SNAPSHOT,
    seed=19020, vocabulary_scale="intermediate", historical_generations=0, canonical_sound_change_engine="Lexurgy", display_locale=None,
    evidence: dict | None = None, display_labels: dict | None = None,
) -> dict:
    cfg = load_phonology(phonology_path)
    snapshot = load_snapshot(evidence if evidence is not None else empirical_snapshot_path)
    profile = _apply_profile_override(sample_typological_profile(seed, snapshot), profile_path)
    orthography = _orthography(seed, cfg)
    lexicon, allocator, lexical_decisions = generate_lexicon(snapshot, cfg, profile, seed=seed, scale=vocabulary_scale, project_root=PROJECT_ROOT, display_labels=None)
    morphology = allocate_morphology(profile, allocator, seed=seed)
    lexicon.extend(_derive_productive_lexemes(lexicon, morphology, cfg, profile, orthography["segment_symbols"]))
    lexicon.extend(_compound_sample_lexemes(lexicon, cfg, profile, orthography["segment_symbols"]))
    for row in lexicon:
        row["orthographic"] = orthographic_form(row["form"], orthography["segment_symbols"], cfg)
    paradigms = generate_paradigms(lexicon, morphology, cfg, profile, orthography["segment_symbols"])
    fixture = _fixture_inventory(lexicon)
    paradigms["sample_noun"] = paradigms[fixture["nouns"][0]["lexeme_id"]]
    paradigms["sample_verb"] = paradigms[fixture["trans"]["lexeme_id"]]
    executor = LanguageExecutor(lexicon=lexicon, paradigms=paradigms, morphology=morphology, profile=profile)
    examples = [executor.realize(x) for x in _example_meanings(lexicon)]
    for ex in examples:
        parsed = analyze_surface({"lexicon": lexicon, "paradigms": paradigms, "morphology": morphology, "profile": profile}, ex["orthographic_sentence"])
        parsed["round_trip_equivalent"] = any(semantic_equivalent(ex["semantic_graph"], candidate) for candidate in parsed["analyses"])
        ex["analysis"] = parsed
    constructions = construction_inventory(profile)
    phoible = snapshot["phoible"]
    inventory = list(cfg.consonants) + list(cfg.vowels)
    phonological_audit = {
        "source": "PHOIBLE 2.0", "source_commit": snapshot["versions"]["PHOIBLE"]["commit"], "comparison_inventory_count": phoible["inventory_count"],
        "losica_inventory": inventory, "exact_inventory_count": phoible["exact_inventory_count"],
        "segment_inventory_counts": {s: phoible["segment_inventory_counts"].get(s, 0) for s in inventory},
        "segment_features": {s: phoible["features"].get(s, {}) for s in inventory},
        "interpretation": "The fixed Losica starting inventory remains authoritative; PHOIBLE counts provide comparison statistics.",
    }
    language = {
        "schema": SCHEMA, "version": "0.26.0", "seed": seed,
        "metadata": {"id": f"losica-{seed}", "name": f"Losica {seed}", "generator": "Losica v0.26", "vocabulary_scale": vocabulary_scale, "concept_target": concept_target(snapshot, vocabulary_scale)},
        "source_boundaries": {
            "physical_acoustic": "physical quantities and propagated waveforms", "human_imitation": "auditory and production evidence",
            "lexical": "conventional form-meaning mappings", "grammar": "morphology and typed constructions", "historical": "chronological transformations",
        },
        "phonology": {
            "language": cfg.language_metadata, "consonants": list(cfg.consonants), "vowels": list(cfg.vowels), "syllable": cfg.syllable,
            "onsets": list(cfg.onsets), "codas": list(cfg.codas), "distinctive_features": phonological_audit["segment_features"],
            "morphophonological_pipeline": ["morpheme_sequence", "segment_representation", "morpheme_internal_syllabification", "morphophonology", "resyllabification", "prosody", "surface_form"],
        },
        "phonological_audit": phonological_audit, "profile": profile, "lexicon": lexicon, "morphology": morphology,
        "syntax": profile["syntax"], "prosody": profile["prosody"], "orthography": orthography,
        "constructions": constructions, "semantic_schema": {"types": ["clause", "entity", "coordination", "phrase"], "roles": ["AGENT", "PATIENT", "THEME", "RECIPIENT", "LOCATION", "SOURCE", "GOAL", "INSTRUMENT", "BENEFICIARY", "POSSESSOR", "POSSESSED", "ATTRIBUTE", "CONTENT", "TIME", "MANNER"]},
        "paradigms": paradigms, "examples": examples,
        "texts": [{"text_id": "TEXT-001", "title": "Generated account", "sentences": [x["orthographic_sentence"] for x in examples[:3]], "coherence": {"shared_referents": [x["concept"] for x in fixture["nouns"][:3]], "discourse_order": [x["construction_id"] for x in examples[:3]]}}],
        "translation_interface": {"structured_meaning": "losica_engine.translation.translate(state, graph)", "controlled_source": "losica_engine.translation.translate(state, text)", "state_semantics": "read_only", "analysis": "losica_engine.surface_analysis.analyze_surface(state, sentence)"},
        "external_integrations": {
            "full_data_policy": "Full corpora/checkpoints remain separately distributed and enter through tested adapters.",
            "adapter_modules": ["losica_engine.importers", "losica_engine.languageevolution_adapter", "losica_engine.sound_change_external", "losica_engine.historical_v021"],
            "grammar_validation_hooks": {"Grammar Matrix": "typed feature/construction coverage comparison", "Grammary": "optional implemented-grammar coverage comparison"},
        },
        "source_ledger": _source_ledger(snapshot),
    }
    if display_locale not in (None, "none", "en"):
        raise ValueError(f"display locale accepts en or none; received {display_locale!r}")

    language["capability_probes"] = _capability_probes(language)
    language["history"] = initial_history(language)
    language["history"]["canonical_sound_change_engine"] = canonical_sound_change_engine
    if historical_generations:
        run_usage_stage(language, generations=historical_generations)
    nodes = profile["sampling_decisions"] + lexical_decisions + [x["provenance"] for x in lexicon] + [x["ud"] | {"entity": "construction", "outputs": [x["construction_id"]]} for x in constructions] + [orthography["provenance"]]
    language["provenance_graph"] = {"schema": "losica-provenance-graph/1", "categories": ["empirical_observation", "statistical_inference", "generated_choice", "linguistic_derivation"], "nodes": nodes}
    language["validation_contract"] = {
        "determinism": "same seed and inputs produce byte-identical canonical state", "profile_execution": [x["executor"] for x in profile["feature_executions"]],
        "phonology": "every lexical, derived, inflected, and sentence token has a legal active-stage parse", "semantics": "typed meaning → realization → surface analysis preserves each licensed reading",
        "cldf": "export metadata validates with pycldf", "history": "every child stage names its parent and generation",
    }
    language["generation_record"] = _generation_record(language, snapshot, {
        "vocabulary_scale": vocabulary_scale,
        "historical_generations": historical_generations,
        "canonical_sound_change_engine": canonical_sound_change_engine,
    })
    if display_labels is None and display_locale == "en":
        from .display_en import load_english_display_labels
        display_labels = load_english_display_labels()
    if display_labels is not None:
        from .display_en import attach_display_labels
        attach_display_labels(language["lexicon"], display_labels)
    return language


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate a complete executable Losica v0.26 language")
    ap.add_argument("--phonology", default=str(DEFAULT_PHONOLOGY))
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE), help="optional explicit profile override; the bundled default enables empirical sampling")
    ap.add_argument("--empirical-snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--seed", type=int, default=19020)
    ap.add_argument("--vocabulary-scale", choices=sorted(VOCABULARY_SCALES), default="intermediate")
    ap.add_argument("--history-generations", type=int, default=0)
    ap.add_argument("--sound-change-engine", choices=["Lexurgy", "Brassica"], default="Lexurgy")
    ap.add_argument("--out", default="language.json")
    ap.add_argument("--export-dir")
    ap.add_argument("--no-companion-exports", action="store_true")
    ap.add_argument("--display-locale", choices=["en", "none"], default="none")
    args = ap.parse_args(argv)
    obj = generate_complete_language(
        phonology_path=args.phonology, profile_path=args.profile, empirical_snapshot_path=args.empirical_snapshot,
        seed=args.seed, vocabulary_scale=args.vocabulary_scale, historical_generations=args.history_generations,
        canonical_sound_change_engine=args.sound_change_engine, display_locale=None if args.display_locale == "none" else args.display_locale,
    )
    if args.no_companion_exports:
        Path(args.out).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        exported = {"json": args.out, "resources": None}
    else:
        exported = export_bundle(obj, args.out, args.export_dir)
    print(json.dumps({
        "out": args.out, "resources": exported["resources"], "lexemes": len(obj["lexicon"]),
        "concept_mappings": sum(len(x.get("concept_mappings", [])) for x in obj["lexicon"]),
        "paradigm_cells": sum(len(v) for k, v in obj["paradigms"].items() if k not in {"sample_noun", "sample_verb"}),
        "examples": len(obj["examples"]), "profile": obj["profile"]["id"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
