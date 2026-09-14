"""Bounded deterministic execution with transactional publication."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

from .project import preflight
from .phonology import generate_roots
from .relations import matched_relations, CategoryPredicateCounts
from .legacy_history_v018 import proto_forms, historical_branch_count
from .publication import transaction
from .diagnostics import StreamingDiagnostics
from .schema import OUTPUT_SCHEMA_VERSION
from .validation import jsonable

DEFAULT_MAX_CANDIDATES = 1_000_000
DEFAULT_MAX_HISTORICAL_BRANCHES = 1_000_000
DEFAULT_MAX_ROOT_SYLLABLES = 12
DEFAULT_MAX_RELATION_EVALUATIONS = 10_000_000
DEFAULT_MAX_RELATION_MATCHES = 1_000_000
DEFAULT_MAX_OUTPUT_BYTES = 256 * 1024 * 1024

FIELDS = (
    "schema_version",
    "run_id",
    "candidate_id",
    "category_id",
    "source_type",
    "source_id",
    "preproto_form",
    "prominence",
    "annotated_form",
    "morphological_provenance",
    "historical_branches",
    "proto_forms",
    "matched_relations",
    "provenance",
)

def canonical(value):
    return json.dumps(
        jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

def parse_counts(value):
    return sorted({
        int(x.strip())
        for x in value.split(",")
    })

class HistoricalBudget:
    def __init__(self, limit):
        if limit < 1:
            raise ValueError(
                "historical branch limit must be >= 1"
            )
        self.limit = limit
        self.used = 0

    def reserve(self, root, branches, source_type):
        if branches < 1:
            raise ValueError(
                "historical branch count must be >= 1"
            )
        projected = self.used + branches
        if projected > self.limit:
            raise ValueError(
                f"historical branch budget exceeded: used {self.used}, "
                f"next root {root.annotated_form!r} ({source_type}) "
                f"requires {branches}; limit={self.limit}"
            )
        self.used = projected

class RelationBudget:
    def __init__(self, evaluation_limit, match_limit):
        self.evaluation_limit = evaluation_limit
        self.match_limit = match_limit
        self.evaluations = 0
        self.matches = 0

    def reserve_evaluations(self, amount):
        projected = self.evaluations + amount
        if projected > self.evaluation_limit:
            raise ValueError(
                f"relation-evaluation budget exceeded during execution: "
                f"{projected}>{self.evaluation_limit}"
            )
        self.evaluations = projected

    def reserve_matches(self, amount):
        projected = self.matches + amount
        if projected > self.match_limit:
            raise ValueError(
                f"relation-match budget exceeded: "
                f"{projected}>{self.match_limit}"
            )
        self.matches = projected

class OutputBudget:
    def __init__(self, limit):
        self.limit = limit
        self.used = 0

    def reserve(self, amount):
        projected = self.used + amount
        if projected > self.limit:
            raise ValueError(
                f"serialized-output budget exceeded: "
                f"{projected}>{self.limit} bytes"
            )
        self.used = projected

class BudgetedTextFile:
    def __init__(self, path, budget):
        self._raw = Path(path).open("wb")
        self._budget = budget

    def write(self, text):
        data = text.encode("utf-8")
        self._budget.reserve(len(data))
        self._raw.write(data)
        return len(text)

    def flush(self):
        self._raw.flush()

    def close(self):
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

def candidate_inputs(project, category_id, derived, processes):
    for pc in derived.get(category_id, ()):
        process = processes[pc.process_id]
        morphology = {
            "process_id": pc.process_id,
            "process_type": pc.process_type,
            "source_lexeme_ids": process.source_lexeme_ids,
            "prominence_rule": process.prominence_rule,
        }
        yield (
            pc.root,
            "lexical_process",
            pc.process_id,
            morphology,
            pc.provenance,
        )

    for root in generate_roots(
        project.phonology,
        project.counts,
    ):
        yield root, "primitive", "", None, ""

def _stable_diagnostics_bytes(diagnostics):
    """Resolve the serialized-byte total to a fixed point."""
    current = dict(diagnostics)
    current["serialized_output_bytes"] = 0

    for _ in range(16):
        payload = (
            canonical(current) + "\n"
        ).encode("utf-8")
        total = (
            current["candidate_tsv_bytes"]
            + len(payload)
        )
        if current["serialized_output_bytes"] == total:
            return payload, total
        current["serialized_output_bytes"] = total

    raise ValueError(
        "serialized output accounting failed to converge"
    )

def execute(project, args, stage):
    cfg = project.phonology
    tr = project.transition

    history_budget = HistoricalBudget(
        args.max_historical_branches
    )
    relation_budget = RelationBudget(
        args.max_relation_evaluations,
        args.max_relation_matches,
    )
    output_budget = OutputBudget(
        args.max_output_bytes
    )

    diag = StreamingDiagnostics(
        stage / "diagnostics.sqlite",
        project.categories,
        [relation.id for relation in project.relations],
    )

    traversed = 0
    derived = {}

    for pc in project.derived:
        derived.setdefault(
            pc.target_category,
            [],
        ).append(pc)

    processes = {
        process.id: process
        for process in project.processes
    }

    try:
        with BudgetedTextFile(
            stage / "candidates.tsv",
            output_budget,
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=FIELDS,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()

            for category in project.categories:
                members = CategoryPredicateCounts.from_members([
                    project.stimuli[stimulus_id]
                    for stimulus_id in category["members"]
                ], project.relations)

                for (
                    root,
                    source,
                    source_id,
                    morphology,
                    provenance,
                ) in candidate_inputs(
                    project,
                    category["id"],
                    derived,
                    processes,
                ):
                    traversed += 1
                    if traversed > args.max_candidates:
                        raise ValueError(
                            "candidate budget exceeded during enumeration"
                        )

                    relation_budget.reserve_evaluations(
                        len(project.relations)
                    )

                    matches = matched_relations(
                        root,
                        cfg,
                        members,
                        project.relations,
                        morphological_process=(
                            morphology["process_type"]
                            if morphology
                            else None
                        ),
                    )

                    relation_budget.reserve_matches(
                        len(matches)
                    )

                    if args.matched_only and not matches:
                        continue

                    branches = historical_branch_count(
                        root,
                        cfg,
                        tr,
                    )
                    history_budget.reserve(
                        root,
                        branches,
                        source,
                    )
                    protos = proto_forms(
                        root,
                        cfg,
                        tr,
                    )

                    identity = [
                        category["id"],
                        source,
                        source_id,
                        root.syllables,
                        root.prominence,
                        morphology,
                    ]
                    candidate_id = hashlib.sha256(
                        canonical(identity).encode()
                    ).hexdigest()

                    writer.writerow({
                        "schema_version": OUTPUT_SCHEMA_VERSION,
                        "run_id": project.metadata["run_id"],
                        "candidate_id": candidate_id,
                        "category_id": category["id"],
                        "source_type": source,
                        "source_id": source_id,
                        "preproto_form": root.form,
                        "prominence": root.prominence,
                        "annotated_form": root.annotated_form,
                        "morphological_provenance": canonical(morphology),
                        "historical_branches": branches,
                        "proto_forms": canonical(protos),
                        "matched_relations": canonical([
                            match.serialize()
                            for match in matches
                        ]),
                        "provenance": provenance,
                    })

                    diag.add(
                        category["id"],
                        candidate_id,
                        root.annotated_form,
                        protos,
                        branches,
                        source,
                        matches,
                    )

        if traversed != (
            project.primitive_count
            + project.process_count
        ):
            raise ValueError(
                "candidate estimator invariant failed"
            )

        if relation_budget.evaluations != project.relation_evaluation_upper_bound:
            raise ValueError(
                "relation-evaluation estimator invariant failed"
            )

        summaries = diag.summarize()

        with (
            stage / "candidates.tsv"
        ).open("rb") as f:
            tsv_hash = hashlib.file_digest(
                f,
                "sha256",
            ).hexdigest()

        candidate_tsv_bytes = (
            stage / "candidates.tsv"
        ).stat().st_size

        diagnostics = {
            **project.metadata,
            "tsv_sha256": tsv_hash,
            "legal_syllables": cfg.legal_syllable_count,
            "primitive_candidate_count": project.primitive_count,
            "lexical_process_candidate_count": project.process_count,
            "traversed_candidate_count": traversed,
            "historical_branch_count": history_budget.used,
            "relation_evaluation_count": relation_budget.evaluations,
            "relation_match_count": relation_budget.matches,
            "emitted_row_count": sum(diag.total.values()),
            "emitted_source_counts": dict(diag.sources),
            "relation_match_counts": dict(diag.matches),
            "proto_collision_group_count": sum(
                category["proto_collision_group_count"]
                for category in summaries
            ),
            "historically_ambiguous_count": sum(
                diag.ambiguous.values()
            ),
            "derivationally_ambiguous_count": sum(
                diag.derivation_ambiguous.values()
            ),
            "relation_premises": [
                relation.serialize()
                for relation in project.relations
            ],
            "candidate_tsv_bytes": candidate_tsv_bytes,
            "categories": summaries,
        }

        diagnostics_payload, serialized_total = (
            _stable_diagnostics_bytes(diagnostics)
        )
        output_budget.reserve(
            len(diagnostics_payload)
        )

        (stage / "diagnostics.json").write_bytes(
            diagnostics_payload
        )

        if output_budget.used != serialized_total:
            raise ValueError(
                "serialized output accounting invariant failed"
            )

    finally:
        diag.close()
        (
            stage / "diagnostics.sqlite"
        ).unlink(missing_ok=True)

def parser():
    ap = argparse.ArgumentParser()

    for name in (
        "stimuli",
        "categories",
        "syllables",
        "out",
    ):
        ap.add_argument(
            "--" + name,
            required=True,
        )

    for name, default in (
        ("phonology", "config/preproto.json"),
        ("transition", "config/transition.json"),
        ("relations", "config/iconic_relations.json"),
        ("lexical-processes", "config/lexical_processes.json"),
        ("lexicon", "data/lexicon.tsv"),
    ):
        ap.add_argument(
            "--" + name,
            default=default,
        )

    ap.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
    )
    ap.add_argument(
        "--max-historical-branches",
        type=int,
        default=DEFAULT_MAX_HISTORICAL_BRANCHES,
    )
    ap.add_argument(
        "--max-root-syllables",
        type=int,
        default=DEFAULT_MAX_ROOT_SYLLABLES,
    )
    ap.add_argument(
        "--max-relation-evaluations",
        type=int,
        default=DEFAULT_MAX_RELATION_EVALUATIONS,
    )
    ap.add_argument(
        "--max-relation-matches",
        type=int,
        default=DEFAULT_MAX_RELATION_MATCHES,
    )
    ap.add_argument(
        "--max-output-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_BYTES,
    )
    ap.add_argument(
        "--matched-only",
        action="store_true",
    )

    return ap

def main(argv=None):
    args = parser().parse_args(argv)

    try:
        project = preflight(args)

        with transaction(
            Path(args.out),
            project.metadata["run_id"],
        ) as stage:
            execute(
                project,
                args,
                stage,
            )

    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        sqlite3.Error,
    ) as exc:
        raise SystemExit(
            f"error: {exc}"
        ) from None

    print(
        f"completed {project.metadata['run_id']}: "
        f"{args.out}"
    )

if __name__ == "__main__":
    main()
