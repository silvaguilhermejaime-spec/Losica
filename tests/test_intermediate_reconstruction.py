import json
from pathlib import Path

import pytest

from losica_engine.historical_examples import load_historical_examples
from losica_engine.config import load_phonology, load_transition
from losica_engine.family_history import load_family_history
from losica_engine.intermediate_reconstruction import load_intermediate_reconstruction


ROOT = Path(__file__).resolve().parents[1]
PHONOLOGY = load_phonology(ROOT / "config/preproto.json")
TRANSITION = load_transition(ROOT / "config/transition.json")
HISTORY = load_family_history(
    ROOT / "config/family_history.json",
    PHONOLOGY,
    TRANSITION,
)
EXAMPLES = load_historical_examples(ROOT / "data/historical_worked_examples.json", HISTORY)
CONSTRAINTS_PATH = ROOT / "config/intermediate_reconstruction.json"


def constraints():
    return load_intermediate_reconstruction(CONSTRAINTS_PATH, HISTORY, EXAMPLES)


def segments(items):
    return {item.segment for item in items}


def test_every_branch_has_constraint_only_reconstruction():
    record = constraints()
    assert set(record.lineages) == {"komuheftic", "sisengwigwo"}
    assert all(
        lineage.reconstruction_status == "constraint_only"
        for lineage in record.lineages.values()
    )
    assert all(
        lineage.simultaneous_inventory_status == "unresolved"
        for lineage in record.lineages.values()
    )


def test_komuheftic_constraints_cover_documented_inputs_only():
    lineage = constraints().lineages["komuheftic"]
    assert segments(lineage.required_consonants) == {
        "p", "t", "k", "kʼ", "b", "d", "g", "kʷ", "gʷ", "ts", "β", "n", "l", "r",
    }
    assert segments(lineage.required_vowels) == {"i", "a", "o"}
    assert set(lineage.unconstrained_proto_consonants) == {"m", "j", "w"}
    assert set(lineage.unconstrained_proto_vowels) == {"e", "u"}


def test_sisengwigwo_constraints_leave_unattested_retentions_open():
    lineage = constraints().lineages["sisengwigwo"]
    assert segments(lineage.required_consonants) == {
        "p", "t", "k", "kʼ", "g", "kʷ", "gʷ", "ts", "β", "r",
    }
    assert segments(lineage.required_vowels) == {"i", "a"}
    assert set(lineage.unconstrained_proto_consonants) == {"b", "d", "m", "n", "l", "j", "w"}
    assert set(lineage.unconstrained_proto_vowels) == {"e", "o", "u"}


def test_example_evidence_requires_an_attested_branch(tmp_path):
    data = json.loads(CONSTRAINTS_PATH.read_text())
    data["lineages"][0]["required_historical_segments"]["vowels"][0]["evidence"] = [
        "example:HX0004:komuheftic"
    ]
    changed = tmp_path / "constraints.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="example evidence is missing"):
        load_intermediate_reconstruction(changed, HISTORY, EXAMPLES)


def test_rule_evidence_must_belong_to_the_branch(tmp_path):
    data = json.loads(CONSTRAINTS_PATH.read_text())
    data["lineages"][0]["required_historical_segments"]["consonants"][0]["evidence"] = [
        "rule:S01"
    ]
    changed = tmp_path / "constraints.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown branch rule"):
        load_intermediate_reconstruction(changed, HISTORY, EXAMPLES)


def test_unconstrained_lists_must_be_exact_proto_complements(tmp_path):
    data = json.loads(CONSTRAINTS_PATH.read_text())
    data["lineages"][1]["unconstrained_proto_segments"]["consonants"].remove("w")
    changed = tmp_path / "constraints.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="exact Proto complement"):
        load_intermediate_reconstruction(changed, HISTORY, EXAMPLES)


def test_complete_inventory_claim_is_rejected(tmp_path):
    data = json.loads(CONSTRAINTS_PATH.read_text())
    data["lineages"][0]["simultaneous_inventory_status"] = "complete"
    changed = tmp_path / "constraints.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="must remain unresolved"):
        load_intermediate_reconstruction(changed, HISTORY, EXAMPLES)
