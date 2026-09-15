import copy
import json

import pytest

from losica_engine.semantic_kernel import (
    PRIME_SPECS,
    PRIME_SOURCE,
    build_semantic_language,
    validate_semantic_language,
)
from losica_engine.working_language import DEFAULT_INVENTORY


@pytest.fixture(scope="module")
def language():
    return build_semantic_language()


def test_kernel_has_65_primes_four_structural_forms_and_three_classes(language):
    report = validate_semantic_language(language)
    assert report == {
        "status": "PASS",
        "kernel_forms": 69,
        "expanded_lexemes": 4033,
        "grammatical_classes": 3,
    }
    assert len(PRIME_SPECS) == 65
    assert language["semantic_kernel"]["prime_source"] == PRIME_SOURCE
    assert set(language["grammatical_system"]["classes"]) == {
        "root", "relator", "clause_operator",
    }


def test_kernel_only_artifact_contains_exactly_69_unique_forms():
    language = build_semantic_language(expanded=False)
    kernel = language["semantic_kernel"]
    rows = [*kernel["primes"], *kernel["structural_forms"]]
    assert len(rows) == 69
    assert len({row["semantic_id"] for row in rows}) == 69
    assert len({row["orthographic"] for row in rows}) == 69
    assert language["lexicon"] == []


def test_expansion_is_category_neutral_source_backed_and_non_fabricated(language):
    assert len(language["lexicon"]) == 4033
    assert {row["class"] for row in language["lexicon"]} == {"root"}
    assert {row["representation"] for row in language["lexicon"]} == {
        "lexicalized_source_concept"
    }
    assert {row["prime_decomposition"] for row in language["lexicon"]} == {
        "not_asserted"
    }
    assert all(row["links"][0]["namespace"] == "concepticon" for row in language["lexicon"])


def test_display_english_does_not_control_kernel_or_expanded_forms(tmp_path):
    inventory = json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))
    for row in inventory["concepts"]:
        row["gloss"] = f"changed display label {row['concepticon_id']}"
    path = tmp_path / "relabeled-inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    original = build_semantic_language()
    altered = build_semantic_language(inventory_path=path)
    assert [row["form"] for row in original["semantic_kernel"]["primes"]] == [
        row["form"] for row in altered["semantic_kernel"]["primes"]
    ]
    assert [row["form"] for row in original["lexicon"]] == [
        row["form"] for row in altered["lexicon"]
    ]


def test_validator_rejects_fabricated_decomposition_and_mutation(language):
    fabricated = copy.deepcopy(language)
    fabricated["lexicon"][0]["prime_decomposition"] = ["nsm:001"]
    with pytest.raises(ValueError, match="uncited prime decomposition"):
        validate_semantic_language(fabricated)

    mutated = copy.deepcopy(language)
    mutated["semantic_kernel"]["primes"][0]["source_exponent"]["en"] = "tampered"
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        validate_semantic_language(mutated)
