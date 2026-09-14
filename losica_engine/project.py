"""Preflight boundary for bounded immutable project values."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .schema import RelationPremise, OUTPUT_SCHEMA_VERSION, DIAGNOSTICS_SCHEMA_VERSION
from .lexical_history import (
    AcceptedLexeme, LexicalProcess, ProcessCandidate,
    load_lexicon, load_processes, validate_process_references, process_candidates,
)
from .config import (
    load_phonology, load_transition, validate_transition,
    PhonologyConfig, TransitionConfig,
)
from .project_data import load_stimuli, load_categories, measurement_catalog
from .relations import load_relations
from .phonology import estimate_root_count
from .validation import (
    require, MAX_ROOT_SYLLABLES, MAX_BUDGET,
    MAX_RELATION_EVALUATIONS, MAX_RELATION_MATCHES, MAX_OUTPUT_BYTES,
    read_text, INPUT_SNAPSHOT, deep_freeze, jsonable,
)

INPUT_OPTIONS = (
    "phonology", "transition", "stimuli", "categories",
    "relations", "lexicon", "lexical_processes",
)

@dataclass(frozen=True)
class ValidatedProject:
    phonology: PhonologyConfig
    transition: TransitionConfig
    stimuli: Mapping[str, Mapping]
    categories: tuple[Mapping, ...]
    relations: tuple[RelationPremise, ...]
    lexicon: Mapping[str, AcceptedLexeme]
    processes: tuple[LexicalProcess, ...]
    derived: tuple[ProcessCandidate, ...]
    counts: tuple[int, ...]
    primitive_count: int
    process_count: int
    relation_evaluation_upper_bound: int
    metadata: Mapping

def preflight(args):
    try:
        snapshot = {
            str(Path(getattr(args, name)).absolute()): read_text(getattr(args, name))
            for name in INPUT_OPTIONS
        }
        token = INPUT_SNAPSHOT.set(snapshot)
        try:
            return _preflight(args)
        finally:
            INPUT_SNAPSHOT.reset(token)
    except (TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise ValueError(f"project input: {exc}") from None

def _bounded_int(value, low, high, context):
    require(
        type(value) is int and low <= value <= high,
        f"{context}: resource limit must be {low}..{high}",
    )

def _preflight(args):
    _bounded_int(args.max_candidates, 1, MAX_BUDGET, "max_candidates")
    _bounded_int(
        args.max_historical_branches,
        1,
        MAX_BUDGET,
        "max_historical_branches",
    )
    _bounded_int(
        args.max_relation_evaluations,
        1,
        MAX_RELATION_EVALUATIONS,
        "max_relation_evaluations",
    )
    _bounded_int(
        args.max_relation_matches,
        1,
        MAX_RELATION_MATCHES,
        "max_relation_matches",
    )
    _bounded_int(
        args.max_output_bytes,
        1024,
        MAX_OUTPUT_BYTES,
        "max_output_bytes",
    )

    require(
        1 <= args.max_root_syllables <= MAX_ROOT_SYLLABLES,
        f"max_root_syllables: supported root limit is 1..{MAX_ROOT_SYLLABLES}",
    )
    require(
        len(args.syllables) <= 256,
        "syllable count specification too long",
    )

    counts = tuple(
        sorted({
            int(x.strip())
            for x in args.syllables.split(",")
        })
    )
    require(
        bool(counts) and min(counts) >= 1,
        "syllable count must be >= 1",
    )
    require(
        max(counts) <= args.max_root_syllables,
        "root syllable limit exceeded",
    )

    for output in (
        Path(args.out),
        Path(str(args.out) + ".diagnostics.json"),
    ):
        require(
            not output.is_dir(),
            f"output path is a directory: {output}",
        )

    outputs = {
        Path(args.out).resolve(),
        Path(str(args.out) + ".diagnostics.json").resolve(),
    }
    require(
        not outputs
        & {
            Path(getattr(args, name)).resolve()
            for name in INPUT_OPTIONS
        },
        "output path must differ from every input path",
    )

    fingerprints = {
        name: sha256(
            read_text(getattr(args, name)).encode()
        ).hexdigest()
        for name in INPUT_OPTIONS
    }

    cfg = load_phonology(args.phonology)
    tr = load_transition(args.transition)
    validate_transition(cfg, tr)

    stimuli_mut = load_stimuli(args.stimuli)
    categories_mut = load_categories(
        args.categories,
        set(stimuli_mut),
    )
    relations = load_relations(
        args.relations,
        cfg,
        measurement_catalog(stimuli_mut),
    )
    lexicon_mut = load_lexicon(args.lexicon, cfg)

    category_ids = {
        category["id"]
        for category in categories_mut
    }

    for lexeme in lexicon_mut.values():
        require(
            lexeme.category_id in category_ids,
            f"lexeme {lexeme.lexeme_id!r}: unknown category_id "
            f"{lexeme.category_id!r}",
        )
        require(
            lexeme.root.syllable_count <= args.max_root_syllables,
            f"lexeme {lexeme.lexeme_id!r}: root syllable limit exceeded",
        )

    processes = tuple(load_processes(args.lexical_processes))
    validate_process_references(
        processes,
        lexicon_mut,
        category_ids,
    )

    for process in processes:
        size = sum(
            lexicon_mut[source].root.syllable_count
            for source in process.source_lexeme_ids
        )
        if process.type == "reduplication":
            size *= 2
        require(
            size <= args.max_root_syllables,
            f"lexical process {process.id!r}: root syllable limit exceeded",
        )

    derived = tuple(
        process_candidates(
            None,
            processes,
            lexicon_mut,
        )
    )

    per_category = estimate_root_count(
        cfg,
        counts,
        cap=args.max_candidates,
    )
    primitive = per_category * len(categories_mut)
    count_qualifier = (
        "at least"
        if per_category > args.max_candidates
        else "estimated"
    )
    total = primitive + len(derived)

    require(
        total <= args.max_candidates,
        f"candidate budget exceeded: {count_qualifier} {total:,} candidates "
        f"({primitive:,} primitive + {len(derived):,} lexical-process); "
        f"--max-candidates={args.max_candidates}",
    )

    relation_evaluations = total * len(relations)
    require(
        relation_evaluations <= args.max_relation_evaluations,
        f"relation-evaluation budget exceeded: {total:,} candidates × "
        f"{len(relations):,} relations = {relation_evaluations:,}; "
        f"--max-relation-evaluations={args.max_relation_evaluations}",
    )

    from . import __version__

    meta = {
        "engine_version": __version__,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "fingerprints": fingerprints,
        "requested_syllable_counts": counts,
        "root_syllable_limit": args.max_root_syllables,
        "candidate_limit": args.max_candidates,
        "historical_branch_limit": args.max_historical_branches,
        "relation_evaluation_limit": args.max_relation_evaluations,
        "relation_match_limit": args.max_relation_matches,
        "output_byte_limit": args.max_output_bytes,
        "matched_only": args.matched_only,
        "relation_count": len(relations),
        "relation_evaluation_upper_bound": relation_evaluations,
    }

    code_hash = sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        code_hash.update(
            path.name.encode()
            + b"\0"
            + path.read_bytes()
        )
    meta["engine_code_sha256"] = code_hash.hexdigest()
    meta["run_id"] = sha256(
        json.dumps(
            jsonable(meta),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    stimuli = deep_freeze(stimuli_mut)
    categories = deep_freeze(categories_mut)
    lexicon = deep_freeze(lexicon_mut)
    metadata = deep_freeze(meta)

    return ValidatedProject(
        cfg,
        tr,
        stimuli,
        tuple(categories),
        relations,
        lexicon,
        processes,
        derived,
        counts,
        primitive,
        len(derived),
        relation_evaluations,
        metadata,
    )
