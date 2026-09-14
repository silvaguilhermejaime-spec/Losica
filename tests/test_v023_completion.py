from pathlib import Path

from losica_engine.full_language import generate_complete_language
from losica_engine.grammar_v021 import semantic_equivalent
from losica_engine.surface_analysis import analyze_surface
from losica_engine.validation_v021 import validate_complete_language

ROOT = Path(__file__).resolve().parents[1]


def _covered(state, example):
    parsed = analyze_surface(state, example["orthographic_sentence"])
    return any(semantic_equivalent(example["semantic_graph"], graph) for graph in parsed["analyses"])


def test_seed_19020_surface_semantics_and_capability_probe():
    state = generate_complete_language(seed=19020, display_locale="en")
    assert all(_covered(state, example) for example in state["examples"])
    assert len(state["examples"]) == 18
    assert state["capability_probes"]
    assert all(probe["semantic_coverage"] for probe in state["capability_probes"])
    assert validate_complete_language(state)["status"] == "PASS"


def test_generated_profiles_share_surface_analysis_contract():
    for seed in (3, 8):
        state = generate_complete_language(seed=seed, vocabulary_scale="core", display_locale="en")
        assert all(_covered(state, example) for example in state["examples"])


def test_productive_category_change_is_materialized_across_open_class_roots():
    state = generate_complete_language(seed=19020)
    roots = [x for x in state["lexicon"] if x.get("formation") in {"semantic_region_lexicalization"}]
    expected = [x for x in roots if x["class"] in {"noun", "verb", "property"}]
    derived = [x for x in state["lexicon"] if x.get("formation") == "productive_derivation"]
    bases = {x["derivational_history"][0]["base_lexeme_id"] for x in derived}
    assert {x["lexeme_id"] for x in expected} <= bases
    for row in derived:
        category = row["class"]
        if category == "noun":
            assert row["distribution"]["heads_np"] is True
        elif category == "property":
            assert row["distribution"]["modifies_noun"] is True
        elif category == "adverb":
            assert row["distribution"]["modifies_clause"] is True


def test_surface_analysis_uses_written_form_only():
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    example = state["examples"][0]
    parsed = analyze_surface(state, example["orthographic_sentence"])
    assert "semantic_graph" not in {k for k in parsed if k != "analyses"}
    assert any(semantic_equivalent(example["semantic_graph"], graph) for graph in parsed["analyses"])
