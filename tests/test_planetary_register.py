import copy
import json

import pytest

from losica_engine.planetary_register import (
    DEFAULT_PLANETARY_SEED,
    build_planetary_register,
    decode_claim,
    decode_expression,
    describe_claim,
    encode_record,
    fact_record,
    find_fact,
    find_quantity,
    render_expression,
    validate_planetary_register,
)
from losica_engine.semantic_kernel import build_semantic_language


@pytest.fixture(scope="module")
def register():
    return build_planetary_register()


def test_register_is_grounded_compositional_and_adds_no_class(register):
    assert validate_planetary_register(register) == {
        "status": "PASS",
        "facts": 22,
        "forms": 98,
        "quantity_expressions": 22,
        "opaque_quantity_roots": 0,
        "round_trips": 44,
        "new_grammatical_classes": 0,
    }
    assert register["source"]["archive_sha256"] == (
        "8cf16f9cb6220dd5759da752c8f719d1561bba97bf63bd56f141716b45c0b0e1"
    )
    assert register["source"]["world_id"] == "losica-131757842"
    assert register["coverage"]["reused_expression_forms"] == 19
    assert register["coverage"]["new_expression_forms"] == 37
    assert register["design"]["opaque_quantity_roots"] == 0
    assert {row["class"] for row in register["forms"]} <= {
        "root", "relator", "clause_operator",
    }


def test_no_quantity_has_a_word_and_every_expression_round_trips(register):
    assert not any(row["semantic_id"].startswith("quantity:") for row in register["forms"])
    for quantity in register["quantities"]:
        assert quantity["token_count"] > 1
        surface = render_expression(quantity["composition"], register)
        assert decode_expression(surface, register) == quantity["composition"]
        assert len(surface.split()) == quantity["token_count"]


def test_mass_reuses_parts_instead_of_coining_star_mass_and_planet_mass(register):
    star = find_quantity(register, "quantity:star_mass")
    planet = find_quantity(register, "quantity:planet_mass")
    assert star["prefix_semantic_ids"] == ["op:of", "property:mass", "entity:star"]
    assert planet["prefix_semantic_ids"] == ["op:of", "property:mass", "entity:planet"]
    assert star["prefix_semantic_ids"][:2] == planet["prefix_semantic_ids"][:2]


def test_orbital_definitions_reuse_nested_structure(register):
    semimajor = find_quantity(register, "quantity:semimajor_axis")["prefix_semantic_ids"]
    eccentricity = find_quantity(register, "quantity:eccentricity")["prefix_semantic_ids"]
    assert semimajor == [
        "op:half", "op:longest", "op:of", "property:diameter",
        "op:of", "entity:orbit", "entity:planet",
    ]
    assert all(symbol in eccentricity for symbol in semimajor)
    assert {"op:between", "entity:focus", "op:per"} <= set(eccentricity)


def test_flux_is_power_per_area_and_annual_temperature_has_two_means(register):
    flux = find_quantity(register, "quantity:mean_stellar_flux")["prefix_semantic_ids"]
    annual = find_quantity(
        register, "quantity:annual_mean_surface_temperature"
    )["prefix_semantic_ids"]
    assert {"property:power", "property:area", "op:per"} <= set(flux)
    assert annual.count("op:mean_over") == 2
    assert {"property:temperature", "property:area", "op:whole"} <= set(annual)


def test_every_fact_round_trips_in_compact_and_spoken_notation(register):
    for fact in register["facts"]:
        record = fact_record(fact, register)
        compact = encode_record(record, register)
        spoken = encode_record(record, register, spoken_numbers=True)
        assert decode_claim(compact, register) == record
        assert decode_claim(spoken, register) == record


def test_variable_expression_frame_preserves_every_decimal(register):
    record = fact_record(find_fact(register, "fact:mean_solar_day"), register)
    utterance = encode_record(record, register)
    quantity = find_quantity(register, "quantity:mean_solar_day")
    assert len(utterance.split()) == 7 + quantity["token_count"]
    assert utterance.split()[3 + quantity["token_count"]] == "8.556787177492277"
    explained = describe_claim(utterance, register)
    assert explained["record"] == record
    assert explained["source"]["pointer"] == "/target_planet/orbit/mean_solar_day_hours"
    assert explained["words"][1]["semantic_id"] == "evidence:derived"
    assert explained["words"][3]["role"] in {"quantity_operator", "quantity_atom"}
    assert next(row for row in explained["words"] if row["role"] == "number")["burden"].startswith("carries this exact decimal")


def test_unknown_is_uncertain_plus_explicit_null(register):
    record = fact_record(find_fact(register, "fact:formation_cloud_unknown"), register)
    utterance = encode_record(record, register)
    assert decode_claim(utterance, register) == record
    assert record["evidence_id"] == "evidence:uncertain"
    assert record["value"] is None
    assert describe_claim(utterance, register)["source"]["pointer"] == "/star/formation_cloud"


def test_old_opaque_forms_are_retired_not_reassigned(register):
    forms = {row["form"] for row in register["forms"]}
    retired = set(register["migration"]["retired_forms"])
    assert forms.isdisjoint(retired)
    with pytest.raises(ValueError, match="unknown planetary-register form"):
        decode_expression("luprat", register)


def test_binary_floats_noncanonical_numbers_and_wrong_tree_are_rejected(register):
    record = fact_record(find_fact(register, "fact:mean_solar_day"), register)
    record["value"] = 8.556787177492277
    with pytest.raises(ValueError, match="exact decimal string"):
        encode_record(record, register)
    record["value"] = "08.5"
    with pytest.raises(ValueError, match="non-canonical exact decimal"):
        encode_record(record, register)
    record = fact_record(find_fact(register, "fact:mean_solar_day"), register)
    record["quantity_expression"] = copy.deepcopy(
        find_quantity(register, "quantity:orbital_period")["composition"]
    )
    with pytest.raises(ValueError, match="does not match quantity_id"):
        encode_record(record, register)


def test_fixed_roles_reject_category_swaps_unknown_and_unregistered_trees(register):
    utterance = encode_record(
        fact_record(find_fact(register, "fact:planet_mass"), register), register
    )
    tokens = utterance.split()
    tokens[2] = "notalosicaform"
    with pytest.raises(ValueError, match="unknown planetary-register form"):
        decode_claim(" ".join(tokens), register)
    tokens = utterance.split()
    # Change star/planet mass into a grammatical but unregistered cloud mass.
    form_by_id = {row["semantic_id"]: row["form"] for row in register["forms"]}
    tokens[5] = form_by_id["entity:cloud"]
    with pytest.raises(ValueError, match="not a registered grounded field"):
        decode_claim(" ".join(tokens), register)
    record = fact_record(find_fact(register, "fact:planet_mass"), register)
    record["subject_id"] = "entity:star"
    with pytest.raises(ValueError, match="does not match the grounded quantity"):
        encode_record(record, register)


def test_display_labels_do_not_control_forms_or_compositions(tmp_path, register):
    seed = json.loads(DEFAULT_PLANETARY_SEED.read_text(encoding="utf-8"))
    for symbol in seed["symbols"]:
        symbol["display"] = "changed display"
    for quantity in seed["quantities"]:
        quantity["label"] = "changed quantity display"
    path = tmp_path / "relabeled.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    relabeled = build_planetary_register(seed_path=path)
    assert {row["semantic_id"]: row["form"] for row in relabeled["forms"]} == {
        row["semantic_id"]: row["form"] for row in register["forms"]
    }
    assert {row["id"]: row["composition"] for row in relabeled["quantities"]} == {
        row["id"]: row["composition"] for row in register["quantities"]
    }


def test_only_declared_semantic_forms_are_reused(register):
    semantic = build_semantic_language()
    semantic_by_form = {
        row["orthographic"]: row["semantic_id"]
        for row in (
            *semantic["semantic_kernel"]["primes"],
            *semantic["semantic_kernel"]["structural_forms"],
            *semantic["lexicon"],
        )
    }
    collisions = [row for row in register["forms"] if row["form"] in semantic_by_form]
    assert len(collisions) == 19
    for row in collisions:
        assert row["provenance"]["reuse_semantic_id"] == semantic_by_form[row["form"]]


def test_canonical_digest_detects_mutation(register):
    changed = copy.deepcopy(register)
    changed["quantities"][0]["composition"]["id"] = "property:mass"
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        validate_planetary_register(changed)
