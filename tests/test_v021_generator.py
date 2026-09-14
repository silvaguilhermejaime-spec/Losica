import copy
import json
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from losica_engine.config import load_phonology
from losica_engine.full_language import generate_complete_language
from losica_engine.grammar_v021 import LanguageExecutor, semantic_equivalent
from losica_engine.lexicon_v021 import VOCABULARY_SCALES, _select_concepts
from losica_engine.morphophonology import Morpheme, phonemic_from_orthography, realize_morphemes
from losica_engine.phonology import is_legal_surface, legal_syllables
from losica_engine.semantic_core import G_MANNER_PROX, G_TIME_ALWAYS
from losica_engine.translation import translate
from losica_engine.independence import canonical_linguistic_hash
from losica_engine.typology import load_snapshot

ROOT = Path(__file__).resolve().parents[1]
CFG = load_phonology(ROOT / "config/preproto.json")


@pytest.fixture(scope="module")
def language():
    return generate_complete_language(seed=19020, vocabulary_scale="core", display_locale="en")


def test_same_seed_produces_identical_complete_state():
    a = generate_complete_language(seed=19020, vocabulary_scale="core")
    b = generate_complete_language(seed=19020, vocabulary_scale="core")
    assert a == b


def test_different_seeds_produce_controlled_structural_variation(language):
    other = generate_complete_language(seed=19021, vocabulary_scale="core")
    assert language["profile"]["id"] != other["profile"]["id"]
    assert language["phonology"]["consonants"] == other["phonology"]["consonants"]
    assert language["profile"]["syntax"] != other["profile"]["syntax"]


def test_vocabulary_scales_select_configured_concept_counts():
    snapshot = load_snapshot()
    for name, count in VOCABULARY_SCALES.items():
        assert len(_select_concepts(snapshot, name)) == count


def test_every_lexical_form_has_an_active_stage_parse(language):
    assert all(is_legal_surface(x["form"], CFG) for x in language["lexicon"])


def test_every_paradigm_form_has_an_active_stage_parse(language):
    assert all(is_legal_surface(c["form"], CFG) for lid, cells in language["paradigms"].items() if lid not in {"sample_noun", "sample_verb"} for c in cells)


def test_every_orthographic_form_maps_to_its_phonemic_form(language):
    mapping = language["orthography"]["segment_symbols"]
    for row in language["lexicon"]:
        assert phonemic_from_orthography(row["orthographic"], mapping, CFG) == ".".join(row["syllables"])


def test_every_word_has_exactly_one_prominent_syllable(language):
    for row in language["lexicon"]:
        assert row["annotated_form"].count("ˈ") == 1
    for cells in language["paradigms"].values():
        for cell in cells:
            assert cell["annotated_form"].count("ˈ") == 1


def test_paradigms_cover_each_licensed_feature_product(language):
    noun_expected = len(language["morphology"]["noun"]["number"]) * len(language["morphology"]["noun"]["case"])
    verb = language["morphology"]["verb"]
    verb_expected = 1
    for dim in ("polarity", "aspect", "tense", "mood", "voice", "evidentiality", "subject_index"):
        verb_expected *= max(1, len(verb[dim]))
    for row in language["lexicon"]:
        if row["class"] == "noun": assert len(language["paradigms"][row["lexeme_id"]]) == noun_expected
        if row["class"] in {"verb", "auxiliary"}: assert len(language["paradigms"][row["lexeme_id"]]) == verb_expected


def test_every_example_round_trips_through_typed_analysis(language):
    executor = LanguageExecutor(lexicon=language["lexicon"], paradigms=language["paradigms"], morphology=language["morphology"], profile=language["profile"])
    for example in language["examples"]:
        rerendered = executor.realize(example["semantic_graph"])
        assert semantic_equivalent(example["semantic_graph"], rerendered["semantic_graph"])
        assert rerendered["tokens"] == example["tokens"]


def test_every_required_construction_has_an_executable_pairing(language):
    required = {"intransitive", "transitive", "ditransitive", "copular", "existential", "possessive", "locative", "modification", "numeral", "quantification", "negation", "polar_question", "content_question", "imperative", "coordination", "complement", "relative", "adverbial"}
    assert required == {x["name"] for x in language["constructions"]}
    assert all(x["form_constraints"]["executable"] for x in language["constructions"])
    assert {x["construction"] for x in language["examples"]} == required


def test_derived_and_compound_words_reenter_lexicon_without_overwriting_base_meanings(language):
    executor = LanguageExecutor(lexicon=language["lexicon"], paradigms=language["paradigms"], morphology=language["morphology"], profile=language["profile"])
    base = next(x for x in language["lexicon"] if x.get("concept_mappings"))
    assert executor._lex(base["concept"])["concept"] == base["concept"]
    derived = [x for x in language["lexicon"] if x["formation"] == "productive_derivation"]
    compounds = [x for x in language["lexicon"] if x["formation"] == "productive_compounding"]
    assert derived and compounds
    assert all(not x["concept_mappings"] and x["derivational_history"] for x in derived)
    assert all(len(x["compound_history"]["constituents"]) >= 2 for x in compounds)


def test_predicate_arguments_must_match_the_lexical_valency_frame(language):
    executor = LanguageExecutor(lexicon=language["lexicon"], paradigms=language["paradigms"], morphology=language["morphology"], profile=language["profile"])
    predicate = next(x for x in language["lexicon"] if x["class"] in {"verb", "auxiliary"} and x.get("argument_structure") and len(x["argument_structure"].get("required_roles", [])) >= 2)
    noun = next(x for x in language["lexicon"] if x["class"] == "noun" and x.get("concept_mappings"))
    supplied_role = predicate["argument_structure"]["required_roles"][0]
    with pytest.raises(ValueError, match="licenses role sets"):
        executor.realize({"type": "clause", "predicate": predicate["concept"], "arguments": {supplied_role: {"type": "entity", "concept": noun["concept"]}}, "construction": None, "features": {}})


def test_profile_phrase_prosody_selects_one_content_token(language):
    for example in language["examples"]:
        assert sum(bool(x["phrase_prominent"]) for x in example["token_details"]) == 1
        assert example["phrase_prosody"]["rule"] == language["profile"]["prosody"]["phrase_rule"]


def test_each_typological_choice_names_its_executor_and_evidence(language):
    assert {"81A", "85A", "86A", "87A", "89A"} <= {x["feature_id"] for x in language["profile"]["feature_executions"]}
    assert all(x["executor"] and x["property_path"] for x in language["profile"]["feature_executions"])
    for decision in language["profile"]["sampling_decisions"]:
        assert decision["source_ids"] and decision["candidate_values"] and decision["weights"]


def test_constituent_order_is_observable_in_realization(language):
    example = next(x for x in language["examples"] if x["construction"] == "transitive")
    roles = [x["semantic_role"] or ("V" if x["deprel"] == "root" else None) for x in example["token_details"]]
    core = ["S" if x == "AGENT" else "O" if x == "PATIENT" else x for x in roles if x in {"AGENT", "PATIENT", "V"}]
    assert "".join(core) == language["profile"]["syntax"]["clause_order"]


def test_attachment_direction_is_observable_in_morpheme_sequence(language):
    cell = next(x for x in language["paradigms"]["sample_noun"] if x["number"] == "PL" and x["case"] == "ACC")
    ids = [x["morpheme_id"] for x in cell["morpheme_sequence"]]
    if language["morphology"]["attachment"] == "suffix": assert ids[0].startswith("LEX_")
    else: assert ids[-1].startswith("LEX_")


def test_profile_override_metadata_changes_the_executor_output(tmp_path):
    override = {
        "schema": "losica-language-profile/1",
        "syntax": {"clause_order": "SVO", "adposition_order": "preposition", "genitive_order": "N-GEN", "property_order": "N-ADJ", "numeral_order": "N-NUM", "demonstrative_order": "N-DEM", "question_particle_position": "clause_initial"},
        "morphology": {"dominant_attachment": "prefix"},
    }
    path = tmp_path / "profile.json"; path.write_text(json.dumps(override), encoding="utf-8")
    state = generate_complete_language(seed=19020, vocabulary_scale="core", profile_path=path)
    example = next(x for x in state["examples"] if x["construction"] == "transitive")
    core = ["V" if x["deprel"] == "root" else "S" if x["semantic_role"] == "AGENT" else "O" if x["semantic_role"] == "PATIENT" else "" for x in example["token_details"]]
    assert "".join(core) == "SVO"
    cell = next(x for x in state["paradigms"]["sample_noun"] if x["number"] == "PL" and x["case"] == "ACC")
    assert cell["morpheme_sequence"][-1]["morpheme_id"].startswith("LEX_")
    assert next(x for x in state["profile"]["feature_executions"] if x["property_path"] == "syntax.clause_order")["value"] == "SVO"


def test_acoustic_evidence_is_unique_and_bound(language):
    rows = [x for x in language["lexicon"] if x["formation"] == "empirical_vocal_imitation"]
    assert rows
    evidence = rows[0]["provenance"]["acoustic"]
    keys = [(x["query_wav_sha256"], x["imitation_id"], x["speaker_id"]) for x in evidence["ranking"]]
    assert len(keys) == len(set(keys))
    assert all(len(x[0]) == 64 for x in keys)
    assert evidence["model"]["checkpoint_id"] and evidence["corpus_index"]["identity"]


def test_allomorph_condition_generalizes_by_phonological_feature(language):
    rules = language["morphology"]["allomorphy"]
    assert rules and all(not x["host_id_specific"] for x in rules)
    assert all(x["condition"] == {"host_final_feature": "+labial"} for x in rules)


def test_allomorph_inventory_contains_no_whole_word_exceptions(language):
    assert "exceptions" not in language["morphology"]
    assert all("host_lexeme_id" not in x for x in language["morphology"]["allomorphy"])


def test_initial_rt_boundary_receives_general_legal_repair():
    out = realize_morphemes([Morpheme("A", "r", "A"), Morpheme("B", "ta", "B")], CFG)
    assert out["surface_phonemic"] == "ra.ta"


def test_initial_rk_boundary_receives_general_legal_repair():
    out = realize_morphemes([Morpheme("A", "r", "A"), Morpheme("B", "ka", "B")], CFG)
    assert out["surface_phonemic"] == "ra.ka"


def test_final_kn_boundary_receives_general_legal_repair():
    out = realize_morphemes([Morpheme("A", "ak", "A"), Morpheme("B", "n", "B")], CFG)
    assert is_legal_surface(out["surface_phonemic"], CFG)
    assert any(x["operation"] == "epenthesis" for x in out["operations"])


def test_identical_consonants_degeminate_before_cluster_repair():
    out = realize_morphemes([Morpheme("A", "uk", "A"), Morpheme("B", "kuk", "B")], CFG)
    assert out["underlying_form"] == "ukkuk"
    assert out["surface_phonemic"].replace(".", "") == "ukuk"
    assert not is_legal_surface("ukkuk", CFG)
    assert is_legal_surface("ukuk", CFG)
    assert any(x["operation"] == "degemination" for x in out["operations"])
    assert not any(
        x["operation"] == "epenthesis" and x["input"] == ["k", "k"]
        for x in out["operations"]
    )


def test_raw_morpheme_sequence_enters_composition_pipeline():
    out = realize_morphemes([{"morpheme_id": "ROOT", "form": "tak", "gloss": "root"}, {"morpheme_id": "SUFFIX", "form": "na", "gloss": "suffix"}], CFG)
    assert out["underlying_form"] == "takna"
    assert out["morpheme_sequence"][1]["morpheme_id"] == "SUFFIX"
    assert is_legal_surface(out["surface_phonemic"], CFG)


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from(legal_syllables(CFG)), min_size=1, max_size=4))
def test_any_legal_morpheme_sequence_produces_a_legal_surface(sequence):
    out = realize_morphemes([Morpheme(f"M{i}", form, str(i)) for i, form in enumerate(sequence)], CFG)
    assert is_legal_surface(out["surface_phonemic"], CFG)


def test_controlled_translation_is_read_only(language):
    state = copy.deepcopy(language)
    before_count = len(state["lexicon"])
    before_hash = canonical_linguistic_hash(state)
    result = translate(state, "the person sees the child")
    assert len(state["lexicon"]) == before_count
    assert canonical_linguistic_hash(state) == before_hash
    assert result["tokens"]


def test_always_been_like_this_translates_compositionally(language):
    result = translate(language, "I always been like this")
    concepts = {token["concept"] for token in result["token_details"]}
    assert {G_TIME_ALWAYS, G_MANNER_PROX} <= concepts
    assert result["translation"] == "I have always been like this"
    assert result["orthographic_sentence"]


def test_source_ledger_covers_each_required_research_boundary(language):
    names = {x["source"] for x in language["source_ledger"]}
    assert {"Grambank", "WALS Online", "UniMorph", "Concepticon", "CLICS4", "PHOIBLE", "Universal Dependencies", "DELPH-IN Grammar Matrix", "DELPH-IN Grammary", "CLDF", "QBV", "RWCP-SSD-Onomatopoeia", "ESC-50-Voice", "VocalSketch", "Vocal Imitation Set", "Allosaurus", "Brassica", "Lexurgy", "SakanaAI LanguageEvolution", "Babel/Fluid Construction Grammar", "EGG", "Kirby, Cornish & Smith", "Bybee", "Baayen et al.", "ConlangCrafter"} <= names
