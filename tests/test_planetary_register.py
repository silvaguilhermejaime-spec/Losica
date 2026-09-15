import copy
import json

import pytest

from losica_engine.planetary_register import (
    DEFAULT_PLANETARY_SEED,
    build_planetary_register,
    decode_claim,
    describe_claim,
    encode_record,
    fact_record,
    find_fact,
    validate_planetary_register,
)
from losica_engine.semantic_kernel import build_semantic_language


@pytest.fixture(scope="module")
def register():
    return build_planetary_register()


def test_register_is_finite_grounded_and_adds_no_grammatical_class(register):
    assert validate_planetary_register(register) == {
        "status": "PASS",
        "facts": 22,
        "forms": 66,
        "round_trips": 22,
        "new_grammatical_classes": 0,
    }
    assert register["source"]["archive_sha256"] == (
        "8cf16f9cb6220dd5759da752c8f719d1561bba97bf63bd56f141716b45c0b0e1"
    )
    assert register["source"]["world_id"] == "losica-131757842"
    assert register["design"]["excluded_inferences"] == [
        "culture", "emotion", "sensory categories", "metaphor",
        "biosphere", "people", "acoustic adaptation",
    ]
    assert {row["class"] for row in register["forms"]} <= {
        "root", "clause_operator",
    }


def test_every_fact_round_trips_in_compact_and_fully_spoken_notation(register):
    for fact in register["facts"]:
        record = fact_record(fact)
        compact = encode_record(record, register)
        spoken = encode_record(record, register, spoken_numbers=True)
        assert decode_claim(compact, register) == record
        assert decode_claim(spoken, register) == record


def test_compact_claim_has_eight_slots_and_preserves_every_decimal(register):
    record = fact_record(find_fact(register, "fact:mean_solar_day"))
    utterance = encode_record(record, register)
    assert len(utterance.split()) == 8
    assert utterance.split()[4] == "8.556787177492277"
    explained = describe_claim(utterance, register)
    assert explained["record"] == record
    assert explained["source"]["pointer"] == (
        "/target_planet/orbit/mean_solar_day_hours"
    )
    assert explained["words"][1]["semantic_id"] == "evidence:derived"
    assert explained["words"][4]["burden"].startswith("carries this exact decimal")


def test_unknown_is_said_as_uncertain_plus_explicit_null(register):
    record = fact_record(find_fact(register, "fact:formation_cloud_unknown"))
    utterance = encode_record(record, register)
    assert len(utterance.split()) == 8
    assert decode_claim(utterance, register) == record
    assert record["evidence_id"] == "evidence:uncertain"
    assert record["value"] is None
    assert describe_claim(utterance, register)["source"]["pointer"] == (
        "/star/formation_cloud"
    )


def test_binary_floats_and_noncanonical_numbers_are_rejected(register):
    record = fact_record(find_fact(register, "fact:mean_solar_day"))
    record["value"] = 8.556787177492277
    with pytest.raises(ValueError, match="exact decimal string"):
        encode_record(record, register)
    record["value"] = "08.5"
    with pytest.raises(ValueError, match="non-canonical exact decimal"):
        encode_record(record, register)


def test_fixed_positions_reject_category_swaps_and_unknown_forms(register):
    utterance = encode_record(
        fact_record(find_fact(register, "fact:mean_solar_day")), register
    )
    tokens = utterance.split()
    tokens[3], tokens[5] = tokens[5], tokens[3]
    with pytest.raises(ValueError, match="quantity_id is not a registered quantity"):
        decode_claim(" ".join(tokens), register)
    tokens = utterance.split()
    tokens[2] = "notalosicaform"
    with pytest.raises(ValueError, match="unknown planetary-register form"):
        decode_claim(" ".join(tokens), register)


def test_display_labels_do_not_control_forms(tmp_path, register):
    seed = json.loads(DEFAULT_PLANETARY_SEED.read_text(encoding="utf-8"))
    for subject in seed["subjects"]:
        subject["label"] = "changed subject display"
    for fact in seed["facts"]:
        fact["quantity_label"] = "changed quantity display"
    path = tmp_path / "relabeled.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    relabeled = build_planetary_register(seed_path=path)
    assert {
        row["semantic_id"]: row["form"] for row in relabeled["forms"]
    } == {
        row["semantic_id"]: row["form"] for row in register["forms"]
    }


def test_domain_forms_do_not_collide_with_kernel_or_concepticon(register):
    semantic = build_semantic_language()
    semantic_forms = {
        row["orthographic"]
        for row in (
            *semantic["semantic_kernel"]["primes"],
            *semantic["semantic_kernel"]["structural_forms"],
            *semantic["lexicon"],
        )
    }
    assert semantic_forms.isdisjoint({row["form"] for row in register["forms"]})


def test_canonical_digest_detects_mutation(register):
    changed = copy.deepcopy(register)
    changed["facts"][0]["value"] = "2"
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        validate_planetary_register(changed)
