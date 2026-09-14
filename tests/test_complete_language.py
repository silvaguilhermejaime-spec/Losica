import json
from pathlib import Path

from losica_engine.config import load_phonology
from losica_engine.full_language import generate_complete_language
from losica_engine.phonology import is_legal_surface

ROOT = Path(__file__).resolve().parents[1]


def test_complete_language_is_reproducible_and_legal():
    a = generate_complete_language(
        phonology_path=ROOT / "config/preproto.json",
        profile_path=ROOT / "config/language_profile.json",
        seed=19020,
    )
    b = generate_complete_language(
        phonology_path=ROOT / "config/preproto.json",
        profile_path=ROOT / "config/language_profile.json",
        seed=19020,
    )
    assert a == b
    cfg = load_phonology(ROOT / "config/preproto.json")
    for row in a["lexicon"]:
        assert is_legal_surface(row["form"], cfg)
    for paradigm in a["paradigms"].values():
        for cell in paradigm:
            assert is_legal_surface(cell["form"], cfg)
    for ex in a["examples"]:
        for token in ex["tokens"]:
            assert is_legal_surface(token, cfg)


def test_complete_language_has_core_grammar():
    obj = generate_complete_language(
        phonology_path=ROOT / "config/preproto.json",
        profile_path=ROOT / "config/language_profile.json",
        seed=19020,
    )
    assert obj["syntax"]["clause_order"] == "SOV"
    assert obj["morphology"]["noun"]["template"] == "STEM-NUMBER-CASE"
    assert obj["morphology"]["verb"]["template"] == "STEM-POLARITY-ASPECT-TENSE-MOOD-SUBJECT"
    assert len(obj["paradigms"]["sample_noun"]) == len(obj["morphology"]["noun"]["number"]) * len(obj["morphology"]["noun"]["case"])
    verb = obj["morphology"]["verb"]
    expected = 1
    for dim in ("polarity", "aspect", "tense", "mood", "voice", "evidentiality", "subject_index"):
        expected *= max(1, len(verb[dim]))
    assert len(obj["paradigms"]["sample_verb"]) == expected
