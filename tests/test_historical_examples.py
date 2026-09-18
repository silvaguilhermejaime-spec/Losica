import json
from pathlib import Path

import pytest

from losica_engine.historical_examples import load_historical_examples
from losica_engine.config import load_phonology, load_transition
from losica_engine.family_history import load_family_history


ROOT = Path(__file__).resolve().parents[1]
PHONOLOGY = load_phonology(ROOT / "config/preproto.json")
TRANSITION = load_transition(ROOT / "config/transition.json")
HISTORY = load_family_history(
    ROOT / "config/family_history.json",
    PHONOLOGY,
    TRANSITION,
)
EXAMPLES_PATH = ROOT / "data/historical_worked_examples.json"


def examples():
    return load_historical_examples(EXAMPLES_PATH, HISTORY)


def entry(record, entry_id):
    return next(item for item in record.entries if item.id == entry_id)


def phonemic_outcome(attestation):
    return next(stage.form for stage in reversed(attestation.chain) if stage.notation == "phonemic")


def test_register_contains_every_supplied_worked_derivation():
    record = examples()
    assert [item.id for item in record.entries] == ["HX0001", "HX0002", "HX0003", "HX0004"]
    assert len(record.shared_input_examples) == 1
    assert record.shared_input_examples[0].reconstruction_form == "igwara"


def test_igwara_is_the_only_input_printed_in_both_descriptions():
    item = entry(examples(), "HX0001")
    assert phonemic_outcome(item.attestations["komuheftic"]) == "iwwara"
    assert phonemic_outcome(item.attestations["sisengwigwo"]) == "iʋaːa"
    assert all(value.status == "attested" for value in item.attestations.values())


def test_extended_tegofarela_form_is_related_without_invented_segmentation():
    item = entry(examples(), "HX0004")
    assert item.related_to == "HX0001"
    assert item.morphology == "morphologically extended form"
    assert item.attestations["komuheftic"].status == "not_printed"
    assert phonemic_outcome(item.attestations["sisengwigwo"]) == "iʋajamija"


def test_all_meanings_are_recorded_as_not_supplied():
    for item in examples().entries:
        assert item.meaning is None
        assert item.meaning_status == "not_supplied"


def test_single_description_examples_mark_the_other_chain_not_printed():
    record = examples()
    for entry_id, branch_id in (
        ("HX0002", "sisengwigwo"),
        ("HX0003", "sisengwigwo"),
        ("HX0004", "komuheftic"),
    ):
        missing = entry(record, entry_id).attestations[branch_id]
        assert missing.status == "not_printed"
        assert missing.source_id is None
        assert missing.chain == ()


def test_declared_coverage_must_match_attestations(tmp_path):
    data = json.loads(EXAMPLES_PATH.read_text())
    data["entries"][0]["coverage"] = "one_description"
    changed = tmp_path / "examples.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="coverage disagrees"):
        load_historical_examples(changed, HISTORY)


def test_not_supplied_meaning_rejects_an_invented_value(tmp_path):
    data = json.loads(EXAMPLES_PATH.read_text())
    data["entries"][0]["meaning"] = "invented meaning"
    changed = tmp_path / "examples.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="meaning and meaning status disagree"):
        load_historical_examples(changed, HISTORY)


def test_attested_chain_must_begin_with_reconstruction(tmp_path):
    data = json.loads(EXAMPLES_PATH.read_text())
    data["entries"][0]["attestations"]["komuheftic"]["chain"][0]["form"] = "other"
    changed = tmp_path / "examples.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="chain must begin"):
        load_historical_examples(changed, HISTORY)
