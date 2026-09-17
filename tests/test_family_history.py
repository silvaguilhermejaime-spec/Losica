import json
from pathlib import Path

import pytest

from losica_engine.config import load_phonology, load_transition
from losica_engine.family_history import load_family_history, transition_output_inventory


ROOT = Path(__file__).resolve().parents[1]
PHONOLOGY = load_phonology(ROOT / "config/preproto.json")
TRANSITION = load_transition(ROOT / "config/transition.json")
HISTORY_PATH = ROOT / "config/family_history.json"


def history():
    return load_family_history(HISTORY_PATH, PHONOLOGY, TRANSITION)


def rule(branch, rule_id):
    return next(change for change in branch.rules if change.id == rule_id)


def test_proto_inventory_is_exactly_the_implemented_transition_output():
    record = history()
    consonants, vowels = transition_output_inventory(PHONOLOGY, TRANSITION)
    assert set(record.proto_consonants) == consonants
    assert set(record.proto_vowels) == vowels
    assert record.reconstruction_status == "provisional"


def test_split_and_branch_ancestry_are_explicit():
    record = history()
    assert record.split_year == 1036
    assert record.parent_stage == "Proto-Losica"
    assert record.daughter_stages == ("Komuheftic", "Sisengwigwo")
    assert record.branches["komuheftic"].descendant == "Komuheft"
    assert record.branches["sisengwigwo"].descendant == "Tegofarela"


def test_diagnostic_branch_correspondences_remain_distinct():
    record = history()
    komuheft = record.branches["komuheftic"]
    tegofarela = record.branches["sisengwigwo"]
    assert rule(komuheft, "K09").chain == ("kʼ", "k")
    assert rule(tegofarela, "S02").chain == ("kʼ", "ʔ")
    assert rule(komuheft, "K10").chain == ("ts", "s", "h", "∅")
    assert rule(tegofarela, "S03").chain == ("ts", "s", "h")


def test_shared_igwara_input_has_separate_documented_outcomes():
    record = history()
    komuheft = record.branches["komuheftic"].examples["igwara"]
    tegofarela = record.branches["sisengwigwo"].examples["igwara_simple"]
    assert komuheft[0] == tegofarela[0] == "igwara"
    assert komuheft[-1] == "iwwara"
    assert tegofarela[-1] == "iʋaːa"


def test_family_history_rejects_drift_from_transition(tmp_path):
    data = json.loads(HISTORY_PATH.read_text())
    data["proto_reconstruction"]["consonants"].remove("β")
    changed = tmp_path / "family_history.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Proto consonants disagree"):
        load_family_history(changed, PHONOLOGY, TRANSITION)


def test_family_history_rejects_undocumented_shape(tmp_path):
    data = json.loads(HISTORY_PATH.read_text())
    data["branches"][0]["rules"][0]["invented_field"] = True
    changed = tmp_path / "family_history.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="fields must be within"):
        load_family_history(changed)
