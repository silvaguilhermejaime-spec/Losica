import csv
import json
from pathlib import Path

from losica_engine.adapters_v021 import compare_grammar_coverage, export_babel_constructions, export_egg_experiment, export_iterated_transmission, import_egg_results
from losica_engine.full_language import generate_complete_language
from losica_engine.historical_v021 import export_sound_change_stage, import_sound_change_trace, productivity_profile
from losica_engine.importers import (
    bind_qbv_ranking, extract_ud_templates, import_allosaurus_hypotheses, import_clics,
    import_concepticon, import_conllu, import_esc50_voice, import_grambank, import_phoible,
    import_unimorph, import_vocal_imitation_set, import_vocalsketch, import_wals,
)
from losica_engine.languageevolution_adapter import export_language_state, export_override, import_language_states
from losica_engine.rwcp_onomatopoeia import build_index as build_rwcp_index


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def test_grambank_import_preserves_ids_missingness_and_controls(tmp_path):
    write_csv(tmp_path / "parameters.csv", ["ID", "Name"], [{"ID": "GB001", "Name": "Feature"}])
    write_csv(tmp_path / "languages.csv", ["ID", "Family_name", "Macroarea", "Latitude", "Longitude"], [{"ID": "L1", "Family_name": "F", "Macroarea": "M", "Latitude": "1", "Longitude": "2"}])
    write_csv(tmp_path / "values.csv", ["ID", "Language_ID", "Parameter_ID", "Value", "Source"], [{"ID": "O1", "Language_ID": "L1", "Parameter_ID": "GB001", "Value": "?", "Source": "S"}])
    obj = import_grambank(tmp_path)
    assert obj["observations"][0] == {"observation_id": "O1", "parameter_id": "GB001", "value": None, "missing": True, "language_id": "L1", "family": "F", "macroarea": "M", "latitude": "1", "longitude": "2", "source": "S"}


def test_wals_import_preserves_feature_chapter_value_and_language_metadata(tmp_path):
    write_csv(tmp_path / "parameters.csv", ["ID", "Name", "Chapter_ID"], [{"ID": "81A", "Name": "Order", "Chapter_ID": "81"}])
    write_csv(tmp_path / "codes.csv", ["ID", "Name"], [{"ID": "81A-1", "Name": "SOV"}])
    write_csv(tmp_path / "languages.csv", ["ID", "Family", "Genus", "Macroarea"], [{"ID": "L", "Family": "F", "Genus": "G", "Macroarea": "M"}])
    write_csv(tmp_path / "values.csv", ["ID", "Language_ID", "Parameter_ID", "Value", "Code_ID", "Source"], [{"ID": "O", "Language_ID": "L", "Parameter_ID": "81A", "Value": "1", "Code_ID": "81A-1", "Source": "S"}])
    obj = import_wals(tmp_path)
    assert obj["features"]["81A"]["Chapter_ID"] == "81"
    assert obj["observations"][0]["value"] == "SOV"


def test_unimorph_import_preserves_feature_bundles(tmp_path):
    p = tmp_path / "um.tsv"; p.write_text("see\tsaw\tV;PST;3;SG\n", encoding="utf-8")
    assert import_unimorph(p, dataset_id="eng")["records"][0]["feature_bundle"] == ["V", "PST", "3", "SG"]


def test_concepticon_and_clics_importers_preserve_original_ids(tmp_path):
    c = tmp_path / "concepticon.tsv"
    c.write_text("ID\tGLOSS\tDEFINITION\tSEMANTICFIELD\tONTOLOGICAL_CATEGORY\tREPLACEMENT_ID\n948\tWATER\tliquid\tworld\tPerson/Thing\t\n", encoding="utf-8")
    assert import_concepticon(c)["records"][0]["concepticon_id"] == "948"
    e = tmp_path / "edges.csv"
    write_csv(e, ["ID", "Source_Concept", "Target_Concept", "Form_Count", "Variety_Count", "Language_Count", "Family_Count", "Family_Weight"], [{"ID": "7", "Source_Concept": "WATER", "Target_Concept": "RIVER", "Form_Count": "4", "Variety_Count": "3", "Language_Count": "3", "Family_Count": "2", "Family_Weight": "0.5"}])
    assert import_clics(e)["edges"][0]["edge_id"] == "7"


def test_phoible_import_retains_segment_features_and_inventories(tmp_path):
    p = tmp_path / "phoible.csv"
    write_csv(p, ["InventoryID", "Glottocode", "ISO6393", "LanguageName", "SpecificDialect", "GlyphID", "Phoneme", "Allophones", "Marginal", "SegmentClass", "Source", "syllabic", "labial"], [{"InventoryID": "1", "Phoneme": "p", "SegmentClass": "consonant", "syllabic": "-", "labial": "+"}])
    obj = import_phoible(p)
    assert obj["segment_types"]["p"]["features"]["labial"] == "+"


def test_ud_import_extracts_relation_and_treebank_provenance(tmp_path):
    p = tmp_path / "x.conllu"
    p.write_text("# sent_id = s1\n# text = Child sleeps.\n1\tChild\tchild\tNOUN\t_\t_\t2\tnsubj\t_\t_\n2\tsleeps\tsleep\tVERB\t_\t_\t0\troot\t_\t_\n\n", encoding="utf-8")
    obj = import_conllu(p, treebank_id="UD_Test")
    template = extract_ud_templates(obj, {"nsubj", "root"})[0]
    assert template["source_treebank"] == "UD_Test" and template["relations"] == ["nsubj", "root"]


def test_vocal_corpus_importers_preserve_pair_and_participant_fields(tmp_path):
    p = tmp_path / "audio.csv"
    write_csv(p, ["id", "reference_wav", "imitation_wav", "speaker_id", "source_id", "referent", "participant", "response", "identified_as", "correct", "class", "reference", "imitation", "speaker"], [{"id": "1", "reference_wav": "r.wav", "imitation_wav": "i.wav", "speaker_id": "S", "source_id": "R", "referent": "bell", "participant": "P", "response": "ding", "identified_as": "bell", "correct": "1", "class": "bell", "reference": "r.wav", "imitation": "i.wav", "speaker": "S"}])
    assert import_esc50_voice(p)["records"][0]["paired_source_id"] == "R"
    assert import_vocalsketch(p)["records"][0]["participant_id"] == "P"
    assert import_vocal_imitation_set(p)["records"][0]["sound_class"] == "bell"


def test_rwcp_import_preserves_worker_confidence_and_acceptance_population_evidence(tmp_path):
    (tmp_path / "bell.ono").write_text("W1,I1,kan,4\n", encoding="utf-8")
    write_csv(tmp_path / "acceptance.csv", ["id", "sound_id", "form", "worker_id", "accepted"], [{"id": "J1", "sound_id": "bell", "form": "kan", "worker_id": "W2", "accepted": "1"}])
    obj = build_rwcp_index(tmp_path)
    assert obj["records"][0]["self_confidence"] == "4"
    assert obj["acceptance_judgments"][0]["accepted"] == "1"


def test_qbv_binding_deduplicates_and_binds_every_ranking(tmp_path):
    wav = tmp_path / "q.wav"; wav.write_bytes(b"RIFFfixture")
    rank = tmp_path / "r.json"
    row = {"imitation_id": "I", "speaker_id": "S", "score": 0.8}
    rank.write_text(json.dumps({"schema": "losica-vocal-retrieval-ranking/1", "ranking": [row, row]}), encoding="utf-8")
    obj = bind_qbv_ranking(rank, wav, checkpoint_id="C", corpus_index_id="D", preprocessing={"mono": True})
    assert obj["duplicate_records_removed"] == 1 and len(obj["ranking"][0]["query_wav_sha256"]) == 64


def test_allosaurus_import_retains_alternative_phone_hypotheses(tmp_path):
    p = tmp_path / "phones.tsv"; p.write_text("m a\t-0.2\nn a\t-0.5\n", encoding="utf-8")
    obj = import_allosaurus_hypotheses(p, model_id="uni200")
    assert obj["uncertainty_retained"] and len(obj["hypotheses"]) == 2


def test_language_evolution_adapter_round_trips_agent_states(tmp_path):
    export_override(seed=2, affixes=["na"], out=tmp_path / "override.json")
    state = {"schema": "losica-languageevolution-results/1", "seed": 2, "generation": 4, "agents": [{"agent_id": "A", "lexicon": {"L": "na"}}]}
    p = tmp_path / "state.json"; p.write_text(json.dumps(state), encoding="utf-8")
    imported = import_language_states(p)
    assert imported["generation"] == 4 and imported["agents"][0]["agent_id"] == "A"


def test_sound_change_adapter_preserves_engine_rules_and_ancestry(tmp_path):
    lang = generate_complete_language(seed=19020, vocabulary_scale="core")
    manifest = export_sound_change_stage(lang, tmp_path / "out", engine="Lexurgy", rules_text="a => i", engine_version="1")
    lid, form = lang["lexicon"][0]["lexeme_id"], lang["lexicon"][0]["form"]
    trace = tmp_path / "trace.tsv"; trace.write_text(f"lexeme_id\tinput\toutput\trule_trace\n{lid}\t{form}\t{form}\tR1\n", encoding="utf-8")
    stage = import_sound_change_trace(trace, lang, engine="Lexurgy", engine_version="1", rules_sha256="0" * 64)
    assert manifest["engine"] == "Lexurgy" and stage["parent_stage_id"] == "GEN-000-SYNCHRONIC"


def test_productivity_profile_computes_baayen_measures():
    events = [{"process_id": "P", "host_lexeme_id": "A", "count": 3, "generation": 0}, {"process_id": "P", "host_lexeme_id": "B", "count": 1, "generation": 1}]
    p = productivity_profile(events, "P", novel_host_trials=[{"accepted": True}, {"accepted": False}])
    assert (p["N_token_frequency"], p["V_type_frequency"], p["n1_hapax_count"], p["P_potential_productivity"]) == (4, 2, 1, 0.25)
    assert p["novel_host_generalization"] == 0.5


def test_optional_history_interleaves_each_licensed_evolutionary_process():
    lang = generate_complete_language(seed=19020, vocabulary_scale="core", historical_generations=2)
    assert [x["generation"] for x in lang["history"]["stages"]] == [0, 1, 2]
    for parent, child in zip(lang["history"]["stages"], lang["history"]["stages"][1:]):
        assert child["parent_stage_id"] == parent["stage_id"]
        assert {x["operation"] for x in child["operations"]} == {"usage_update", "morphological_change", "sound_change", "analogy", "transmission"}


def test_optional_architecture_adapters_have_reproducible_file_contracts(tmp_path):
    lang = generate_complete_language(seed=19020, vocabulary_scale="core")
    manifest = tmp_path / "grammar.json"; manifest.write_text(json.dumps({"id": "G", "phenomena": ["transitive", "relative"]}), encoding="utf-8")
    assert compare_grammar_coverage(lang, manifest, system="DELPH-IN Grammar Matrix")["coverage"] == 1.0
    assert export_babel_constructions(lang, tmp_path / "fcg.json").exists()
    assert export_egg_experiment(lang, tmp_path / "egg.json", meanings=[], agents=2).exists()
    assert export_iterated_transmission(lang, tmp_path / "ilm.json", chains=2, generations=3, bottleneck=4).exists()
    results = tmp_path / "egg-results.json"; results.write_text(json.dumps({"schema": "losica-egg-results/1", "experiment_id": "E", "signals": []}), encoding="utf-8")
    assert import_egg_results(results)["natural_language_state_modified"] is False
