import copy
import json
from pathlib import Path

import pytest

from losica_engine.possession_kinship import (
    clan_kin_graph,
    kin_relation_graph,
    load_possession_kinship,
    possession_graph,
)
from losica_engine.working_language import build_working_language, translate


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "possession_kinship.json"
INVENTORY = ROOT / "data" / "concepticon_inventory_v0_30.json"


@pytest.fixture(scope="module")
def inventory():
    return json.loads(INVENTORY.read_text())


@pytest.fixture(scope="module")
def grammar(inventory):
    return load_possession_kinship(CONFIG, inventory)


@pytest.fixture(scope="module")
def language():
    return build_working_language()


def semantic_sequence(result):
    return [token["semantic_id"] for token in result["tokens"]]


def test_general_possession_is_unmarked_possessor_head(language):
    result = translate(language, possession_graph("ref:utterer", "c:302"))
    assert semantic_sequence(result) == ["ref:utterer", "c:302"]
    assert [token["role"] for token in result["tokens"]] == ["POSSESSOR", "HEAD"]
    reference = next(row for row in language["markers"] if row["semantic_id"] == "ref:utterer")
    assert result["tokens"][0]["gloss"] == reference["meaning"] == "current utterance source"


def test_possession_is_defined_positively_without_imported_contrast_categories(inventory):
    grammar = load_possession_kinship(CONFIG, inventory)
    assert dict(grammar.nominal_possession) == {
        "strategy": "juxtaposition",
        "order": ["possessor", "head"],
        "possessor_omission": "discourse_recoverable_only",
    }


def test_kin_relation_uses_anchor_then_relation(language):
    result = translate(language, kin_relation_graph("ref:context", "c:1216"))
    assert semantic_sequence(result) == ["ref:context", "c:1216"]
    assert [token["role"] for token in result["tokens"]] == ["KIN_ANCHOR", "HEAD"]


@pytest.mark.parametrize(
    ("compound_id", "components"),
    [
        ("mother_clan", ["c:1216", "c:302"]),
        ("clan_peer", ["c:302", "c:1640"]),
        ("partner_group", ["c:2514", "c:789"]),
        ("communal_caregiver", ["c:253", "c:683"]),
    ],
)
def test_clan_kin_compounds_are_anchored_modifier_head(language, grammar, compound_id, components):
    graph = clan_kin_graph("ref:utterer", compound_id, grammar)
    result = translate(language, graph)
    assert semantic_sequence(result) == ["ref:utterer", *components]
    assert result["tokens"][-1]["role"] == "HEAD"


def test_compounds_use_only_source_backed_semantic_ids(grammar, inventory):
    available = {f"c:{row['concepticon_id']}" for row in inventory["concepts"]}
    assert all(set(compound.components) <= available for compound in grammar.compounds.values())


def test_partner_eligibility_is_contextual_not_lexically_claimed(grammar):
    compound = grammar.compounds["partner_group"]
    assert compound.components == ("c:2514", "c:789")
    assert "eligibility supplied by clan context" in compound.historical_path


def test_daughter_reflexes_remain_unresolved(grammar):
    assert all(compound.daughter_reflex_status == "unresolved" for compound in grammar.compounds.values())


def test_unknown_semantic_component_is_rejected(tmp_path, inventory):
    data = json.loads(CONFIG.read_text())
    data["conventional_compounds"][0]["components"][0] = "c:not-a-concept"
    changed = tmp_path / "possession.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="semantic inventory"):
        load_possession_kinship(changed, inventory)


def test_daughter_reflex_claim_is_rejected(tmp_path, inventory):
    data = copy.deepcopy(json.loads(CONFIG.read_text()))
    data["conventional_compounds"][0]["daughter_reflex_status"] = "known"
    changed = tmp_path / "possession.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="must remain unresolved"):
        load_possession_kinship(changed, inventory)
