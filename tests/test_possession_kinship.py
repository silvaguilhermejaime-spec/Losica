import copy
import json
from pathlib import Path

import pytest

from losica_engine.config import load_phonology
from losica_engine.possession_kinship import load_possession_kinship
from losica_engine.working_language import build_working_language, translate


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "possession_kinship.json"
INVENTORY = ROOT / "data" / "concepticon_inventory_v0_30.json"
PHONOLOGY = ROOT / "config" / "preproto.json"


@pytest.fixture(scope="module")
def inventory():
    return json.loads(INVENTORY.read_text())


@pytest.fixture(scope="module")
def boundary(inventory):
    return load_possession_kinship(CONFIG, inventory, load_phonology(PHONOLOGY))


@pytest.fixture(scope="module")
def language():
    return build_working_language()


def test_muto_adapts_to_legal_pre_proto_mutu(boundary, language):
    reference = boundary.reference_forms["ref:utterer"]
    assert reference.source_form == "muto"
    assert reference.form == "mutu"
    assert dict(reference.adaptation) == {
        "input": "o",
        "output": "u",
        "scope": "every documented form entering Pre-Proto-Losica",
    }
    marker = next(row for row in language["markers"] if row["semantic_id"] == "ref:utterer")
    assert marker["form"] == marker["orthographic"] == "mutu"


def test_mutu_is_usable_as_an_ordinary_referring_expression(language):
    result = translate(language, "I buy bread")
    assert result["tokens"][0]["semantic_id"] == "ref:utterer"
    assert result["tokens"][0]["form"] == "mutu"
    assert result["tokens"][0]["role"] == "AGENT"


def test_other_reference_words_are_absent(language):
    references = [row for row in language["markers"] if row["class"] == "reference"]
    assert [(row["semantic_id"], row["form"]) for row in references] == [
        ("ref:utterer", "mutu")
    ]
    with pytest.raises(KeyError, match="source-backed semantic lookup is empty"):
        translate(language, "you buy bread")


def test_possession_and_kin_syntax_remain_unresolved(boundary, language):
    assert boundary.nominal_possession_status == "unresolved"
    assert boundary.kin_relation_status == "unresolved"
    with pytest.raises(ValueError, match="syntax is unresolved"):
        translate(language, {
            "type": "nominal_possession",
            "possessor": {"semantic_id": "ref:utterer"},
            "head": {"semantic_id": "c:302"},
        })


def test_only_matrilineal_clan_membership_is_established(boundary):
    assert dict(boundary.social_principles) == {
        "matrilineal_clan_membership": "established",
        "clan_exogamy": "unresolved",
        "communal_childcare": "unresolved",
    }


def test_derived_clan_kin_vocabulary_is_unresolved(boundary):
    assert dict(boundary.vocabulary_policy) == {
        "authorization": "existing_documented_roots_only",
        "derived_clan_kin_terms": "unresolved",
    }


def test_inconsistent_adaptation_is_rejected(tmp_path, inventory):
    data = copy.deepcopy(json.loads(CONFIG.read_text()))
    data["documented_reference_forms"][0]["adaptation"]["output"] = "a"
    changed = tmp_path / "boundary.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="o > u consistently"):
        load_possession_kinship(changed, inventory, load_phonology(PHONOLOGY))


def test_additional_undocumented_reference_form_is_rejected(tmp_path, inventory):
    data = copy.deepcopy(json.loads(CONFIG.read_text()))
    extra = copy.deepcopy(data["documented_reference_forms"][0])
    extra["semantic_id"] = "ref:other"
    data["documented_reference_forms"].append(extra)
    changed = tmp_path / "boundary.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="currently contains only"):
        load_possession_kinship(changed, inventory, load_phonology(PHONOLOGY))
