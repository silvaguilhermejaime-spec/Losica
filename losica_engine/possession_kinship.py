"""Validated Pre-Proto-Losica reference and clan evidence boundaries."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .phonology import is_legal_surface
from .validation import keys, label, read_json, require


@dataclass(frozen=True)
class DocumentedReferenceForm:
    semantic_id: str
    source_form: str
    form: str
    meaning: str
    distribution_status: str
    adaptation: Mapping[str, str]


@dataclass(frozen=True)
class PossessionKinshipBoundary:
    schema: str
    stage: str
    status: str
    reference_forms: Mapping[str, DocumentedReferenceForm]
    nominal_possession_status: str
    kin_relation_status: str
    social_principles: Mapping[str, str]
    vocabulary_policy: Mapping[str, str]


def _reference_form(value, phonology):
    keys(
        value,
        {
            "semantic_id", "source_form", "form", "meaning",
            "distribution_status", "adaptation",
        },
        context="documented reference form",
    )
    require(value["semantic_id"] == "ref:utterer",
            "the documented reference inventory currently contains only ref:utterer")
    require(value["source_form"] == "muto", "the documented source form must be muto")
    require(value["form"] == "mutu", "Pre-Proto adaptation of muto must be mutu")
    require(is_legal_surface(value["form"], phonology),
            "the adapted reference form must be legal Pre-Proto Losica")
    require(value["meaning"] == "current utterance source",
            "the documented meaning must identify the current utterance source")
    require(value["distribution_status"] == "ordinary_referring_expression",
            "mutu is licensed only as an ordinary referring expression")
    adaptation = value["adaptation"]
    keys(adaptation, {"input", "output", "scope"}, context="reference-form adaptation")
    require(adaptation == {
        "input": "o",
        "output": "u",
        "scope": "every documented form entering Pre-Proto-Losica",
    }, "documented-form adaptation must apply o > u consistently")
    return DocumentedReferenceForm(
        value["semantic_id"],
        value["source_form"],
        value["form"],
        value["meaning"],
        value["distribution_status"],
        MappingProxyType(dict(adaptation)),
    )


def load_possession_kinship(path, semantic_inventory, phonology):
    data = read_json(path)
    keys(
        data,
        {
            "schema", "stage", "status", "documented_reference_forms",
            "nominal_possession", "kin_relation_syntax", "social_principles",
            "vocabulary_policy",
        },
        context="possession/kinship evidence boundary",
    )
    require(data["schema"] == "losica-possession-kinship/2",
            "unsupported possession/kinship schema")
    require(data["stage"] == "Pre-Proto-Losica",
            "possession/kinship evidence must belong to Pre-Proto-Losica")
    require(data["status"] == "evidence_boundary",
            "possession/kinship status must identify an evidence boundary")

    require(isinstance(data["documented_reference_forms"], list),
            "documented_reference_forms list required")
    rows = tuple(_reference_form(value, phonology)
                 for value in data["documented_reference_forms"])
    references = {row.semantic_id: row for row in rows}
    require(len(references) == len(rows) == 1,
            "exactly one documented reference form is currently established")

    nominal = data["nominal_possession"]
    kin = data["kin_relation_syntax"]
    keys(nominal, {"status"}, context="nominal possession")
    keys(kin, {"status"}, context="kin relation syntax")
    require(nominal["status"] == "unresolved", "nominal possession must remain unresolved")
    require(kin["status"] == "unresolved", "kin relation syntax must remain unresolved")

    principles = data["social_principles"]
    keys(
        principles,
        {"matrilineal_clan_membership", "clan_exogamy", "communal_childcare"},
        context="clan social principles",
    )
    require(principles == {
        "matrilineal_clan_membership": "established",
        "clan_exogamy": "unresolved",
        "communal_childcare": "unresolved",
    }, "social principles exceed the established evidence")

    policy = data["vocabulary_policy"]
    keys(policy, {"authorization", "derived_clan_kin_terms"}, context="vocabulary policy")
    require(policy == {
        "authorization": "existing_documented_roots_only",
        "derived_clan_kin_terms": "unresolved",
    }, "vocabulary policy must preserve the documented-root boundary")

    return PossessionKinshipBoundary(
        data["schema"],
        label(data["stage"], "possession/kinship stage"),
        data["status"],
        MappingProxyType(references),
        nominal["status"],
        kin["status"],
        MappingProxyType(dict(principles)),
        MappingProxyType(dict(policy)),
    )
