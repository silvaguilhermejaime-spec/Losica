
from dataclasses import dataclass
from pathlib import Path
import csv, json

from .config import PhonologyConfig
from .phonology import Root, legal_syllables
from functools import lru_cache
from .schema import REGISTERED_PROCESS_TYPES
from .validation import (read_json, read_text, keys, require, text, identifier, provenance_text, MAX_PROCESSES, MAX_LEXEMES)
from io import StringIO

PROCESS_RULES = {"reduplication": (1, frozenset({"first_copy", "second_copy"})),
                 "compound": (2, frozenset({"left", "right"}))}

@dataclass(frozen=True)
class LexicalProcess:
    id: str
    type: str
    target_category: str
    source_lexeme_ids: tuple[str, ...]
    prominence_rule: str
    provenance: str = ""

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass(frozen=True)
class AcceptedLexeme:
    lexeme_id: str
    category_id: str
    root: Root
    provenance: str

@dataclass(frozen=True)
class ProcessCandidate:
    process_id: str
    process_type: str
    target_category: str
    root: Root
    provenance: str

@lru_cache(maxsize=1)
def _legal_set(cfg):
    return frozenset(legal_syllables(cfg))

def _validated_root(
    preproto_form: str,
    prominence_text: str,
    cfg: PhonologyConfig,
    *,
    lexeme_id: str,
) -> Root:
    syllables = tuple(preproto_form.split(".")) if preproto_form else ()
    if not syllables or any(not s for s in syllables):
        raise ValueError(
            f"lexeme {lexeme_id!r}: preproto_form must contain one or more syllables"
        )

    require(len(syllables) <= 12, f"lexeme {lexeme_id!r}: root syllable limit exceeded (12)")
    legal = _legal_set(cfg)
    invalid = [s for s in syllables if s not in legal]
    if invalid:
        raise ValueError(
            f"lexeme {lexeme_id!r}: illegal Pre-Proto syllable(s): "
            + ", ".join(repr(s) for s in invalid)
        )

    try:
        prominence = int(prominence_text)
    except (TypeError, ValueError):
        raise ValueError(
            f"lexeme {lexeme_id!r}: prominence must be an integer"
        ) from None

    if not 0 <= prominence < len(syllables):
        raise ValueError(
            f"lexeme {lexeme_id!r}: prominence {prominence} is outside "
            f"the {len(syllables)}-syllable root"
        )

    return Root(syllables, prominence)

def load_lexicon(
    path: str | Path,
    cfg: PhonologyConfig,
) -> dict[str, AcceptedLexeme]:
    out = {}

    with StringIO(read_text(path), newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"lexeme_id", "category_id", "preproto_form", "prominence"}
        fields = set(reader.fieldnames or ())
        require(len(reader.fieldnames or ()) == len(fields), "duplicate lexicon columns")
        allowed = required | {"provenance"}
        require(fields <= allowed, f"lexicon columns must be within {sorted(allowed)}")
        missing_columns = sorted(required - fields)
        if missing_columns:
            raise ValueError(
                "lexicon is missing required column(s): "
                + ", ".join(missing_columns)
            )

        for line_number, row in enumerate(reader, start=2):
            require(len(out) < MAX_LEXEMES, f"lexicon: at most {MAX_LEXEMES} entries supported")
            require(None not in row and all(v is not None for v in row.values()), f"lexicon line {line_number}: wrong column count")
            lexeme_id = identifier(row.get("lexeme_id"), "lexeme_id")
            identifier(row.get("category_id"), "lexeme category_id")
            if not lexeme_id:
                raise ValueError(
                    f"lexicon line {line_number}: lexeme_id is required"
                )
            if lexeme_id in out:
                raise ValueError(
                    f"lexicon line {line_number}: duplicate lexeme_id {lexeme_id!r}"
                )

            root = _validated_root(
                (row.get("preproto_form") or "").strip(),
                row.get("prominence"),
                cfg,
                lexeme_id=lexeme_id,
            )

            out[lexeme_id] = AcceptedLexeme(
                lexeme_id=lexeme_id,
                category_id=identifier((row.get("category_id") or "").strip(), "lexeme category_id"),
                root=root,
                provenance=("" if row.get("provenance", "") == "" else provenance_text(row["provenance"], "lexeme provenance")),
            )

    return out


def load_processes(path: str | Path) -> list[LexicalProcess]:
    data = read_json(path)
    keys(data, {"processes"}, context="processes")
    processes = data["processes"]

    if not isinstance(processes, list):
        raise ValueError("processes must be a list")
    require(len(processes) <= MAX_PROCESSES, f"processes: at most {MAX_PROCESSES} entries supported")

    out = []
    seen = set()

    for index, process in enumerate(processes, start=1):
        keys(process, {"id", "type", "target_category", "source_lexeme_ids", "prominence_rule"}, {"provenance"}, "lexical process")
        process_id = identifier(process.get("id"), "process id")

        if not process_id:
            raise ValueError(
                f"process entry {index}: id is required"
            )
        if process_id in seen:
            raise ValueError(
                f"duplicate process id {process_id!r}"
            )
        seen.add(process_id)

        process_type = process.get("type")
        if process_type not in REGISTERED_PROCESS_TYPES:
            raise ValueError(
                f"lexical process {process_id!r}: unknown type {process_type!r}"
            )

        target_category = identifier(process.get("target_category"), "target_category")
        if not target_category:
            raise ValueError(
                f"lexical process {process_id!r}: target_category is required"
            )

        source_ids = process.get("source_lexeme_ids")
        if not isinstance(source_ids, list) or any(
            not isinstance(x, str) or not x.strip()
            for x in source_ids
        ):
            raise ValueError(
                f"lexical process {process_id!r}: source_lexeme_ids must be lexeme IDs"
            )

        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                f"lexical process {process_id!r}: duplicate source lexeme ID"
            )

        arity, rules = PROCESS_RULES[process_type]
        require(len(source_ids) == arity, f"lexical process {process_id!r}: {process_type} requires exactly {arity} source lexeme(s)")
        require(process["prominence_rule"] in rules, f"lexical process {process_id!r}: unknown prominence_rule")
        provenance_value = process.get("provenance", "")
        require(isinstance(provenance_value, str), "process provenance must be a string")
        provenance = ("" if provenance_value == "" else provenance_text(provenance_value, "process provenance"))
        out.append(LexicalProcess(process_id, process_type, target_category,
                                  tuple(identifier(x, "source lexeme ID") for x in source_ids), process["prominence_rule"], provenance))

    return out

def validate_process_references(
    processes: list[LexicalProcess],
    lexicon: dict[str, AcceptedLexeme],
    category_ids: set[str],
):
    for process in processes:
        process_id = process["id"]

        if process["target_category"] not in category_ids:
            raise ValueError(
                f"lexical process {process_id!r}: unknown target category "
                f"{process['target_category']!r}"
            )

        missing = [
            source_id
            for source_id in process["source_lexeme_ids"]
            if source_id not in lexicon
        ]
        if missing:
            raise ValueError(
                f"lexical process {process_id!r}: unknown source lexeme ID(s): "
                + ", ".join(repr(x) for x in missing)
            )

def _resolve_sources(
    process: dict,
    lexicon: dict[str, AcceptedLexeme],
) -> list[AcceptedLexeme]:
    return [
        lexicon[source_id]
        for source_id in process["source_lexeme_ids"]
    ]

def process_candidates(
    target_category: str,
    processes: list[LexicalProcess],
    lexicon: dict[str, AcceptedLexeme],
):
    for p in processes:
        if target_category is not None and p.get("target_category") != target_category:
            continue

        typ = p["type"]
        sources = _resolve_sources(p, lexicon)

        if typ == "reduplication":
            if len(sources) != 1:
                raise ValueError(
                    f"lexical process {p.get('id', '')!r}: "
                    "reduplication requires exactly one source lexeme"
                )

            src = sources[0].root
            syllables = src.syllables + src.syllables
            rule = p["prominence_rule"]

            if rule == "first_copy":
                prominence = src.prominence
            elif rule == "second_copy":
                prominence = len(src.syllables) + src.prominence
            else:
                raise ValueError(f"unknown prominence_rule {rule!r}")

            yield ProcessCandidate(
                p["id"],
                "reduplication",
                p["target_category"],
                Root(syllables, prominence),
                p.get("provenance", ""),
            )

        elif typ == "compound":
            if len(sources) != 2:
                raise ValueError(
                    f"lexical process {p.get('id', '')!r}: "
                    "compound requires exactly two source lexemes"
                )

            left, right = sources[0].root, sources[1].root
            syllables = left.syllables + right.syllables
            rule = p["prominence_rule"]

            if rule == "left":
                prominence = left.prominence
            elif rule == "right":
                prominence = len(left.syllables) + right.prominence
            else:
                raise ValueError(f"unknown prominence_rule {rule!r}")

            yield ProcessCandidate(
                p["id"],
                "compound",
                p["target_category"],
                Root(syllables, prominence),
                p.get("provenance", ""),
            )

        else:
            raise ValueError(f"unknown lexical process type {typ!r}")


def estimate_process_candidate_count(
    processes: list[LexicalProcess],
) -> int:
    return len(processes)
