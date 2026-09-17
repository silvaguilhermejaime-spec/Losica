import json
from pathlib import Path

import pytest

from losica_engine.comparative_lexicon import load_comparative_lexicon
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
LEXICON_PATH = ROOT / "data/losican_cognates.json"


def lexicon():
    return load_comparative_lexicon(LEXICON_PATH, HISTORY)


def entry(record, entry_id):
    return next(item for item in record.entries if item.id == entry_id)


def phonemic_outcome(attestation):
    return next(stage.form for stage in reversed(attestation.chain) if stage.notation == "phonemic")


def test_seed_register_contains_every_supplied_lexical_derivation():
    record = lexicon()
    assert [item.id for item in record.entries] == ["CG0001", "CG0002", "CG0003", "CG0004"]
    assert len(record.complete_entries) == 1
    assert record.complete_entries[0].reconstruction_form == "igwara"


def test_igwara_is_the_only_two_branch_comparison():
    item = entry(lexicon(), "CG0001")
    assert phonemic_outcome(item.attestations["komuheftic"]) == "iwwara"
    assert phonemic_outcome(item.attestations["sisengwigwo"]) == "iʋaːa"
    assert all(value.status == "attested" for value in item.attestations.values())


def test_extended_tegofarela_form_is_related_without_invented_segmentation():
    item = entry(lexicon(), "CG0004")
    assert item.related_to == "CG0001"
    assert item.morphology == "morphologically extended form"
    assert item.attestations["komuheftic"].status == "missing_evidence"
    assert phonemic_outcome(item.attestations["sisengwigwo"]) == "iʋajamija"


def test_all_meanings_remain_unresolved():
    for item in lexicon().entries:
        assert item.gloss is None
        assert item.semantic_status == "unresolved"


def test_partial_entries_use_missing_evidence_not_empty_attestations():
    record = lexicon()
    for entry_id, branch_id in (
        ("CG0002", "sisengwigwo"),
        ("CG0003", "sisengwigwo"),
        ("CG0004", "komuheftic"),
    ):
        missing = entry(record, entry_id).attestations[branch_id]
        assert missing.status == "missing_evidence"
        assert missing.source_id is None
        assert missing.chain == ()


def test_declared_coverage_must_match_attestations(tmp_path):
    data = json.loads(LEXICON_PATH.read_text())
    data["entries"][0]["coverage"] = "partial"
    changed = tmp_path / "cognates.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="coverage disagrees"):
        load_comparative_lexicon(changed, HISTORY)


def test_unresolved_meaning_rejects_an_invented_gloss(tmp_path):
    data = json.loads(LEXICON_PATH.read_text())
    data["entries"][0]["gloss"] = "invented meaning"
    changed = tmp_path / "cognates.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="gloss and semantic status disagree"):
        load_comparative_lexicon(changed, HISTORY)


def test_attested_chain_must_begin_with_reconstruction(tmp_path):
    data = json.loads(LEXICON_PATH.read_text())
    data["entries"][0]["attestations"]["komuheftic"]["chain"][0]["form"] = "other"
    changed = tmp_path / "cognates.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="chain must begin"):
        load_comparative_lexicon(changed, HISTORY)
