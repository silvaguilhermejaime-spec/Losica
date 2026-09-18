import copy
import json

import pytest

from losica_engine.config import load_phonology
from losica_engine.phonology import is_legal_surface
from losica_engine.working_language import (
    DEFAULT_INVENTORY,
    DEFAULT_PHONOLOGY,
    analyze,
    build_working_language,
    lookup,
    translate,
    validate_working_language,
)


@pytest.fixture(scope="module")
def language():
    return build_working_language()


def test_full_source_backed_inventory_has_unique_legal_forms(language):
    assert validate_working_language(language)["status"] == "PASS"
    assert len(language["lexicon"]) >= 4000
    assert language["coverage"]["english_is_adapter_only"] is True
    assert language["semantic_inventory"]["commit"] == "918bc44e123952a6ab5733be36c2d463799c23b4"
    cfg = load_phonology(DEFAULT_PHONOLOGY)
    assert all(is_legal_surface(row["form"], cfg) for row in language["lexicon"])
    assert language["grammar"]["possession_kinship"]["schema"] == "losica-possession-kinship/2"


def test_english_glosses_do_not_control_form_assignment(language, tmp_path):
    inventory = json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))
    for row in inventory["concepts"]:
        row["gloss"] = f"changed display label {row['concepticon_id']}"
    altered_inventory = tmp_path / "relabeled-inventory.json"
    altered_inventory.write_text(json.dumps(inventory), encoding="utf-8")
    altered = build_working_language(inventory_path=altered_inventory)
    before = [(row["semantic_id"], row["form"]) for row in language["lexicon"]]
    after = [(row["semantic_id"], row["form"]) for row in altered["lexicon"]]
    assert before == after


def test_canonical_digest_detects_artifact_mutation(language):
    altered = copy.deepcopy(language)
    altered["lexicon"][0]["display"]["en"] = "tampered"
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        validate_working_language(altered)


def test_buy_bread_sentence_is_compositional_and_source_backed(language):
    result = translate(language, "Can I buy bread today?")
    ids = result["semantic_graph"]
    assert ids["predicate"] == "c:1869"
    assert ids["arguments"]["PATIENT"]["semantic_id"] == "c:1368"
    assert ids["adjuncts"][0]["semantic_id"] == "c:1283"
    assert {"mood:pot", "clause:q"} <= set(ids["features"])
    parsed = analyze(language, result["losica"])
    assert parsed["semantic_sequence"] == [row["semantic_id"] for row in result["tokens"]]


def test_reference_system_is_losica_internal_and_english_is_adapter_only(language):
    references = {row["semantic_id"]: row["meaning"] for row in language["markers"] if row["class"] == "reference"}
    assert references == {"ref:utterer": "current utterance source"}
    marker = next(row for row in language["markers"] if row["semantic_id"] == "ref:utterer")
    assert marker["form"] == "mutu"


def test_persistent_state_sentence_uses_concepticon_not_invented_labels(language):
    result = translate(language, "Bread has always been like this")
    graph = result["semantic_graph"]
    assert graph["predicate"] == "c:1579"  # Concepticon BE
    assert graph["arguments"]["ATTRIBUTE"]["semantic_id"] == "c:200"  # Concepticon SAME
    assert graph["arguments"]["ATTRIBUTE"]["deixis"] == "PROX"
    assert graph["adjuncts"][0]["semantic_id"] == "c:1676"  # Concepticon ALWAYS
    assert lookup(language, "always")[0]["links"] == [{"namespace": "concepticon", "object_id": "1676"}]


def test_unknown_source_word_fails_instead_of_inventing_a_meaning(language):
    with pytest.raises(KeyError, match="source-backed semantic lookup is empty"):
        translate(language, "I florp bread")


def test_common_tense_and_copular_patterns(language):
    prospective = translate(language, "I will buy bread")
    assert "asp:pros" in prospective["semantic_graph"]["features"]
    marker = next(row for row in language["markers"] if row["semantic_id"] == "asp:pros")
    assert marker["orthographic"] == "tam"
    assert all(row["semantic_id"] != "tam:fut" for row in language["markers"])
    assert language["grammar"]["temporal_interpretation"].startswith("unmarked predicates are tenseless")
    past = translate(language, "I bought bread")
    assert "tam:pst" in past["semantic_graph"]["features"]
    copular = translate(language, "Bread is big")
    assert copular["semantic_graph"]["predicate"] == "c:1579"
    assert copular["semantic_graph"]["arguments"]["ATTRIBUTE"]["semantic_id"] == "c:1202"
