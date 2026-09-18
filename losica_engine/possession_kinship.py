"""Validated Late Pre-Proto-Losica possession and clan-kin constructions."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .validation import identifier, keys, label, read_json, require, text


@dataclass(frozen=True)
class ConventionalCompound:
    id: str
    meaning: str
    components: tuple[str, ...]
    head: str
    historical_path: str
    daughter_reflex_status: str


@dataclass(frozen=True)
class PossessionKinship:
    schema: str
    stage: str
    status: str
    nominal_possession: Mapping[str, object]
    kin_relation: Mapping[str, object]
    social_principles: Mapping[str, str]
    compounds: Mapping[str, ConventionalCompound]


def _semantic_ids(inventory: Mapping[str, object]) -> set[str]:
    return {f"c:{row['concepticon_id']}" for row in inventory["concepts"]}


def _compound(value, available_ids):
    keys(
        value,
        {
            "id", "meaning", "components", "head", "historical_path",
            "daughter_reflex_status",
        },
        context="possession/kinship compound",
    )
    compound_id = identifier(value["id"], "possession/kinship compound id")
    require(isinstance(value["components"], list), f"compound {compound_id}: components list required")
    components = tuple(value["components"])
    require(2 <= len(components) <= 4, f"compound {compound_id}: two to four components required")
    require(all(isinstance(item, str) and item in available_ids for item in components),
            f"compound {compound_id}: every component must reference the semantic inventory")
    head = text(value["head"], f"compound {compound_id} head")
    require(head == components[-1], f"compound {compound_id}: final component must be the head")
    require(value["daughter_reflex_status"] == "unresolved",
            f"compound {compound_id}: daughter reflexes must remain unresolved")
    return ConventionalCompound(
        compound_id,
        text(value["meaning"], f"compound {compound_id} meaning"),
        components,
        head,
        text(value["historical_path"], f"compound {compound_id} historical path"),
        value["daughter_reflex_status"],
    )


def load_possession_kinship(path, semantic_inventory):
    data = read_json(path)
    keys(
        data,
        {
            "schema", "stage", "status", "nominal_possession", "kin_relation",
            "social_principles", "conventional_compounds",
        },
        context="possession/kinship grammar",
    )
    require(data["schema"] == "losica-possession-kinship/1",
            "unsupported possession/kinship schema")
    require(data["stage"] == "Late Pre-Proto-Losica",
            "possession/kinship grammar must belong to Late Pre-Proto-Losica")
    require(data["status"] == "constructed_internal_grammar",
            "possession/kinship status must identify a constructed internal grammar")

    nominal = data["nominal_possession"]
    keys(nominal, {"strategy", "order", "possessor_omission"},
         context="nominal possession")
    require(nominal["strategy"] == "juxtaposition",
            "nominal possession must use juxtaposition")
    require(nominal["order"] == ["possessor", "head"],
            "nominal possession must use possessor-head order")
    require(nominal["possessor_omission"] == "discourse_recoverable_only",
            "possessor omission must be discourse-recoverable")

    kin = data["kin_relation"]
    keys(kin, {"order", "relation_is_head", "anchor_omission"}, context="kin relation")
    require(kin["order"] == ["anchor", "relation"], "kin relations must use anchor-relation order")
    require(kin["relation_is_head"] is True, "kin relation must be the nominal head")
    require(kin["anchor_omission"] == "discourse_recoverable_only",
            "kin anchor omission must be discourse-recoverable")

    principles = data["social_principles"]
    keys(principles, {"descent", "clan_membership_source", "partnership", "childcare"},
         context="clan social principles")
    expected = {
        "descent": "matrilineal",
        "clan_membership_source": "mother",
        "partnership": "clan_exogamous",
        "childcare": "communal",
    }
    require(principles == expected, "clan social principles disagree with the reference grammar")

    require(isinstance(data["conventional_compounds"], list),
            "conventional_compounds list required")
    rows = tuple(_compound(value, _semantic_ids(semantic_inventory))
                 for value in data["conventional_compounds"])
    compounds = {row.id: row for row in rows}
    require(len(compounds) == len(rows), "duplicate possession/kinship compound id")
    require(set(compounds) == {"mother_clan", "clan_peer", "partner_group", "communal_caregiver"},
            "possession/kinship grammar must define the four planned clan-kin concepts")
    return PossessionKinship(
        data["schema"],
        label(data["stage"], "possession/kinship stage"),
        data["status"],
        MappingProxyType(dict(nominal)),
        MappingProxyType(dict(kin)),
        MappingProxyType(dict(principles)),
        MappingProxyType(compounds),
    )


def possession_graph(possessor: str, head: str) -> dict:
    """Build an unmarked possessor-head nominal graph."""
    return {
        "type": "nominal_possession",
        "construction": "possessor_head",
        "possessor": {"semantic_id": possessor},
        "head": {"semantic_id": head},
    }


def kin_relation_graph(anchor: str, relation: str) -> dict:
    """Build an anchor-relation kin nominal graph."""
    return {
        "type": "kin_relation",
        "construction": "anchor_relation",
        "anchor": {"semantic_id": anchor},
        "relation": {"semantic_id": relation},
    }


def clan_kin_graph(anchor: str, compound_id: str, grammar: PossessionKinship) -> dict:
    """Build an anchored conventional clan-kin compound graph."""
    require(compound_id in grammar.compounds, f"unknown clan-kin compound {compound_id!r}")
    return {
        "type": "clan_kin",
        "construction": compound_id,
        "anchor": {"semantic_id": anchor},
        "components": list(grammar.compounds[compound_id].components),
    }


def nominal_sequence(graph: Mapping[str, object], grammar: PossessionKinship) -> tuple[tuple[str, str], ...]:
    """Return semantic IDs in the validated surface order for a nominal graph."""
    kind = graph.get("type")
    if kind == "nominal_possession":
        require(graph.get("construction") == "possessor_head", "unknown possession construction")
        return (
            (graph["possessor"]["semantic_id"], "POSSESSOR"),
            (graph["head"]["semantic_id"], "HEAD"),
        )
    if kind == "kin_relation":
        require(graph.get("construction") == "anchor_relation", "unknown kin construction")
        return (
            (graph["anchor"]["semantic_id"], "KIN_ANCHOR"),
            (graph["relation"]["semantic_id"], "HEAD"),
        )
    if kind == "clan_kin":
        compound_id = graph.get("construction")
        require(compound_id in grammar.compounds, f"unknown clan-kin compound {compound_id!r}")
        compound = grammar.compounds[compound_id]
        require(tuple(graph.get("components", ())) == compound.components,
                f"clan-kin compound {compound_id}: components disagree with grammar")
        return ((graph["anchor"]["semantic_id"], "KIN_ANCHOR"),) + tuple(
            (semantic_id, "HEAD" if semantic_id == compound.head else "COMPOUND_MODIFIER")
            for semantic_id in compound.components
        )
    require(False, f"unsupported nominal graph type {kind!r}")
