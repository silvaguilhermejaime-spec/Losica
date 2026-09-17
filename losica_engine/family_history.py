"""Validated comparative evidence for the Losican family history."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .config import PhonologyConfig, TransitionConfig
from .validation import identifier, keys, label, read_json, require, strings, text


RULE_STATUSES = frozenset({"documented", "provisional"})
RECONSTRUCTION_STATUSES = frozenset({"provisional", "established"})


@dataclass(frozen=True)
class SoundChange:
    id: str
    chain: tuple[str, ...]
    environment: str
    chronology: str
    source_section: str
    status: str


@dataclass(frozen=True)
class DaughterBranch:
    id: str
    ancestor: str
    descendant: str
    consonants: tuple[str, ...]
    vowels: tuple[str, ...]
    rules: tuple[SoundChange, ...]
    examples: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class FamilyHistory:
    schema: str
    split_year: int
    parent_stage: str
    daughter_stages: tuple[str, ...]
    proto_consonants: tuple[str, ...]
    proto_vowels: tuple[str, ...]
    reconstruction_status: str
    branches: Mapping[str, DaughterBranch]
    unresolved: tuple[str, ...]


def _unique(items):
    return tuple(dict.fromkeys(items))


def transition_output_inventory(
    phonology: PhonologyConfig,
    transition: TransitionConfig,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return all segment types available after the configured Proto transition."""
    consonants = _unique(
        phonology.consonants
        + (transition.p_result,)
        + tuple(transition.postnasal.values())
        + tuple(transition.glides.values())
        + tuple(transition.coalescence.values())
    )
    vowels = _unique(
        phonology.vowels
        + tuple(transition.vowel_lowering.values())
    )
    return frozenset(consonants), frozenset(vowels)


def _sound_change(value, branch_id):
    context = f"branch {branch_id} sound change"
    keys(
        value,
        {"id", "chain", "environment", "chronology", "source_section", "status"},
        context=context,
    )
    rule_id = identifier(value["id"], f"{context} id")
    chain = strings(value["chain"], f"sound change {rule_id} chain", max_items=12)
    require(len(chain) >= 2, f"sound change {rule_id}: chain requires at least two stages")
    status = text(value["status"], f"sound change {rule_id} status")
    require(status in RULE_STATUSES, f"sound change {rule_id}: unknown status {status!r}")
    return SoundChange(
        rule_id,
        chain,
        text(value["environment"], f"sound change {rule_id} environment"),
        text(value["chronology"], f"sound change {rule_id} chronology"),
        text(value["source_section"], f"sound change {rule_id} source_section"),
        status,
    )


def _branch(value):
    keys(
        value,
        {"id", "ancestor", "descendant", "inventory", "rules", "examples"},
        context="daughter branch",
    )
    branch_id = identifier(value["id"], "daughter branch id")
    inventory = value["inventory"]
    keys(inventory, {"consonants", "vowels"}, context=f"branch {branch_id} inventory")
    consonants = strings(inventory["consonants"], f"branch {branch_id} consonants")
    vowels = strings(inventory["vowels"], f"branch {branch_id} vowels")
    require(not set(consonants) & set(vowels), f"branch {branch_id}: inventories overlap")

    require(isinstance(value["rules"], list), f"branch {branch_id}: rules must be a list")
    require(1 <= len(value["rules"]) <= 64, f"branch {branch_id}: 1..64 rules required")
    rules = tuple(_sound_change(rule, branch_id) for rule in value["rules"])
    rule_ids = [rule.id for rule in rules]
    require(len(rule_ids) == len(set(rule_ids)), f"branch {branch_id}: duplicate rule id")

    require(isinstance(value["examples"], dict), f"branch {branch_id}: examples must be an object")
    require(len(value["examples"]) <= 32, f"branch {branch_id}: at most 32 examples")
    examples = {}
    for example_id, chain_value in value["examples"].items():
        identifier(example_id, f"branch {branch_id} example id")
        chain = strings(chain_value, f"branch {branch_id} example {example_id}", max_items=20)
        require(len(chain) >= 2, f"branch {branch_id} example {example_id}: chain too short")
        examples[example_id] = chain

    return DaughterBranch(
        branch_id,
        label(value["ancestor"], f"branch {branch_id} ancestor"),
        label(value["descendant"], f"branch {branch_id} descendant"),
        consonants,
        vowels,
        rules,
        MappingProxyType(examples),
    )


def load_family_history(path, phonology=None, transition=None):
    data = read_json(path)
    keys(
        data,
        {"schema", "split", "proto_reconstruction", "branches", "unresolved"},
        context="family history",
    )
    schema = text(data["schema"], "family history schema")
    require(schema == "losica-family-history/1", "unsupported family history schema")

    split = data["split"]
    keys(split, {"approximate_year", "parent_stage", "daughter_stages"}, context="family split")
    year = split["approximate_year"]
    require(type(year) is int and 0 <= year <= 10000, "family split year must be an integer from 0..10000")
    daughter_stages = strings(split["daughter_stages"], "daughter stages", max_items=8)
    require(len(daughter_stages) == 2, "family split requires exactly two daughter stages")

    proto = data["proto_reconstruction"]
    keys(proto, {"stage", "status", "consonants", "vowels"}, context="Proto-Losica reconstruction")
    proto_consonants = strings(proto["consonants"], "Proto-Losica consonants")
    proto_vowels = strings(proto["vowels"], "Proto-Losica vowels")
    require(not set(proto_consonants) & set(proto_vowels), "Proto-Losica inventories overlap")
    reconstruction_status = text(proto["status"], "Proto-Losica reconstruction status")
    require(
        reconstruction_status in RECONSTRUCTION_STATUSES,
        f"unknown reconstruction status {reconstruction_status!r}",
    )

    require(isinstance(data["branches"], list), "family history branches must be a list")
    branches_list = tuple(_branch(value) for value in data["branches"])
    require(len(branches_list) == 2, "family history requires exactly two branches")
    branches = {branch.id: branch for branch in branches_list}
    require(len(branches) == len(branches_list), "duplicate branch id")
    require(
        {branch.ancestor for branch in branches_list} == set(daughter_stages),
        "branch ancestors must match the split daughter stages",
    )

    unresolved = strings(data["unresolved"], "unresolved family-history questions", max_items=32)

    history = FamilyHistory(
        schema,
        year,
        label(split["parent_stage"], "family split parent stage"),
        daughter_stages,
        proto_consonants,
        proto_vowels,
        reconstruction_status,
        MappingProxyType(branches),
        unresolved,
    )

    if phonology is not None or transition is not None:
        require(
            phonology is not None and transition is not None,
            "phonology and transition must be supplied together",
        )
        consonants, vowels = transition_output_inventory(phonology, transition)
        require(set(history.proto_consonants) == consonants, "Proto consonants disagree with transition output")
        require(set(history.proto_vowels) == vowels, "Proto vowels disagree with transition output")

    return history
