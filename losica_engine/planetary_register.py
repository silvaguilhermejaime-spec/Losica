"""A reversible, provenance-first Losica register for scalar planet claims.

This module does not infer a culture or a sensory world from physical data.
It gives a small set of sourced scalar records an exact spoken/written frame:

    CLAIM EVIDENCE SUBJECT QUANTITY NUMBER UNIT MODEL END

The frame is deliberately rigid.  Its useful idiosyncrasy is that provenance
must be said first; its useful guarantee is that decoding recovers the same
typed record, including every decimal digit.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from .config import PhonologyConfig, load_phonology
from .morphophonology import orthographic_form
from .phonology import generate_roots, is_legal_surface
from .semantic_kernel import build_semantic_language
from .working_language import DEFAULT_PHONOLOGY, DEFAULT_SEED


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLANETARY_SEED = ROOT / "config" / "planetary_register.json"
SCHEMA = "losica-planetary-register/1"
SEED_SCHEMA = "losica-planetary-seed/1"
VERSION = "0.31.0"

EVIDENCE = {
    "evidence:sampled": (
        "sampled",
        "the value is a retained or generated draw; this does not claim that its sampling law is calibrated",
    ),
    "evidence:derived": (
        "derived",
        "the value is calculated from other stated inputs under the named model",
    ),
    "evidence:modeled": (
        "modeled",
        "the value is an output or state of the named model, not a direct observation",
    ),
    "evidence:conditioned": (
        "conditioned",
        "the value has been selected or altered by a declared conditioning operation",
    ),
    "evidence:uncertain": (
        "uncertain",
        "the source commits to no value; the null is meaningful and must remain recoverable",
    ),
}

FRAME = {
    "frame:claim": "opens one typed scalar claim",
    "frame:end": "closes the claim and prevents silent attachment of further material",
}

NUMBER_MEANINGS = {
    **{f"num:{digit}": digit for digit in "0123456789"},
    "num:minus": "-",
    "num:plus": "+",
    "num:point": ".",
    "num:exponent": "e",
    "num:null": None,
}
CHARACTER_TO_NUMBER_ID = {
    value: semantic_id
    for semantic_id, value in NUMBER_MEANINGS.items()
    if value is not None
}
NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?\Z")


def _digest(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ranked(values, *, seed: int, namespace: str) -> list:
    return sorted(
        values,
        key=lambda value: (
            hashlib.sha256(f"{seed}|{namespace}|{value}".encode()).digest(),
            value,
        ),
    )


def _load_seed(path=DEFAULT_PLANETARY_SEED) -> dict:
    seed = json.loads(Path(path).read_text(encoding="utf-8"))
    if seed.get("schema") != SEED_SCHEMA:
        raise ValueError(f"planetary register requires {SEED_SCHEMA}")
    return seed


def _symbol_specs(seed: dict) -> list[dict]:
    rows = [
        {
            "semantic_id": semantic_id,
            "class": "clause_operator",
            "semantic_type": "frame",
            "display": label,
            "burden": burden,
        }
        for semantic_id, (label, burden) in {
            "frame:claim": ("claim", FRAME["frame:claim"]),
            "frame:end": ("end", FRAME["frame:end"]),
        }.items()
    ]
    rows.extend(
        {
            "semantic_id": semantic_id,
            "class": "root",
            "semantic_type": "evidence",
            "display": display,
            "burden": burden,
        }
        for semantic_id, (display, burden) in EVIDENCE.items()
    )
    rows.extend(
        {
            "semantic_id": row["id"],
            "class": "root",
            "semantic_type": "subject",
            "display": row["label"],
            "burden": f"identifies only {row['source_pointer']} in the pinned world-state document",
            "source_pointer": row["source_pointer"],
        }
        for row in seed["subjects"]
    )
    quantities = {}
    for fact in seed["facts"]:
        existing = quantities.setdefault(
            fact["quantity_id"],
            {
                "semantic_id": fact["quantity_id"],
                "class": "root",
                "semantic_type": "quantity",
                "display": fact["quantity_label"],
                "burden": f"selects the scalar field at {fact['source_pointer']}; it carries no value or unit",
                "source_pointer": fact["source_pointer"],
            },
        )
        if existing["source_pointer"] != fact["source_pointer"]:
            raise ValueError(f"quantity {fact['quantity_id']} has more than one source pointer")
    rows.extend(quantities.values())
    rows.extend(
        {
            "semantic_id": row["id"],
            "class": "root",
            "semantic_type": "unit",
            "display": row["symbol"],
            "burden": f"sets the numeric unit to {row['meaning']}; it carries no magnitude",
        }
        for row in seed["units"]
    )
    rows.extend(
        {
            "semantic_id": row["id"],
            "class": "root",
            "semantic_type": "model",
            "display": row["id"].split(":", 1)[1],
            "burden": f"attributes the claim to the model registry entry: {row['label']}",
        }
        for row in seed["models"]
    )
    rows.extend(
        {
            "semantic_id": semantic_id,
            "class": "root",
            "semantic_type": "number",
            "display": "null" if value is None else value,
            "burden": (
                "encodes an explicit null value"
                if value is None
                else f"encodes exactly the numeric character {value!r}"
            ),
        }
        for semantic_id, value in NUMBER_MEANINGS.items()
    )
    ids = [row["semantic_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("planetary symbol IDs must be unique")
    return rows


def _assign_forms(rows: list[dict], *, seed: int, semantic_language: dict) -> list[dict]:
    cfg_data = semantic_language["phonology"]
    cfg = PhonologyConfig(
        tuple(cfg_data["consonants"]),
        tuple(cfg_data["vowels"]),
        tuple(cfg_data["onsets"]),
        tuple(cfg_data["codas"]),
        cfg_data["syllable"],
    )
    spelling = semantic_language["orthography"]["segment_symbols"]
    used = {
        row["orthographic"]
        for row in (
            *semantic_language["semantic_kernel"]["primes"],
            *semantic_language["semantic_kernel"]["structural_forms"],
            *semantic_language["lexicon"],
        )
    }
    candidates = []
    seen = set()
    for root in generate_roots(cfg, [2]):
        if root.prominence != 0:
            continue
        written = orthographic_form(root.form, spelling, cfg)
        if written in used or written in seen:
            continue
        seen.add(written)
        candidates.append((root.form, written))
    candidates = _ranked(candidates, seed=seed, namespace="planetary-register")
    if len(candidates) < len(rows):
        raise ValueError("not enough collision-free forms for the planetary register")
    assigned = {
        semantic_id: form
        for semantic_id, form in zip(
            sorted(row["semantic_id"] for row in rows), candidates
        )
    }
    output = []
    for row in rows:
        phonemic, written = assigned[row["semantic_id"]]
        built = copy.deepcopy(row)
        built.update({
            "form": written,
            "phonemic": phonemic,
            "ipa": f"/{phonemic}/",
            "provenance": {
                "form_assignment": "stable semantic ID -> seed-ranked unused legal two-syllable form",
                "seed": seed,
                "display_label_used_for_form_assignment": False,
            },
        })
        output.append(built)
    return output


def _record_from_fact(fact: dict) -> dict:
    return {
        "evidence_id": fact["evidence_id"],
        "subject_id": fact["subject_id"],
        "quantity_id": fact["quantity_id"],
        "value": fact["value"],
        "unit_id": fact["unit_id"],
        "model_id": fact["model_id"],
    }


def build_planetary_register(
    *,
    seed_path=DEFAULT_PLANETARY_SEED,
    form_seed: int = DEFAULT_SEED,
) -> dict:
    """Build the finite v0.31 register from the pinned physical seed."""
    seed = _load_seed(seed_path)
    semantic_language = build_semantic_language(
        expanded=True,
        phonology_path=DEFAULT_PHONOLOGY,
        seed=form_seed,
    )
    forms = _assign_forms(
        _symbol_specs(seed), seed=form_seed, semantic_language=semantic_language
    )
    register = {
        "schema": SCHEMA,
        "version": VERSION,
        "form_seed": form_seed,
        "language_id": f"losica-planetary:{form_seed}:{seed['source']['world_id']}",
        "source": copy.deepcopy(seed["source"]),
        "design": {
            "claim_order": [
                "frame:claim", "evidence", "subject", "quantity",
                "number", "unit", "model", "frame:end",
            ],
            "evidence_position": "obligatory and first inside the claim frame",
            "number_encoding": (
                "compact writing uses one exact decimal literal; fully spoken form uses one "
                "reversible Losica word per character; null has its own word"
            ),
            "invertibility_contract": "decode(encode(normalize(record))) == normalize(record)",
            "semantic_burden": "one stable semantic ID per word; syntactic role is supplied by fixed position",
            "new_grammatical_classes": 0,
            "excluded_inferences": [
                "culture", "emotion", "sensory categories", "metaphor",
                "biosphere", "people", "acoustic adaptation",
            ],
        },
        "forms": forms,
        "facts": copy.deepcopy(seed["facts"]),
        "coverage": {
            "facts": len(seed["facts"]),
            "forms": len(forms),
            "evidence_values": len(EVIDENCE),
            "subjects": len(seed["subjects"]),
            "quantities": len({fact["quantity_id"] for fact in seed["facts"]}),
            "units": len(seed["units"]),
            "models": len(seed["models"]),
            "new_grammatical_classes": 0,
        },
    }
    register["canonical_sha256"] = _digest(register)
    validate_planetary_register(register, semantic_language=semantic_language)
    return register


def _indexes(register: dict) -> tuple[dict, dict]:
    by_id = {row["semantic_id"]: row for row in register["forms"]}
    by_form = {row["form"]: row for row in register["forms"]}
    return by_id, by_form


def normalize_record(record: dict, register: dict) -> dict:
    """Return the exact six-field semantic payload accepted by the codec."""
    expected = {
        "evidence_id", "subject_id", "quantity_id", "value", "unit_id", "model_id",
    }
    missing = expected - set(record)
    extra = set(record) - expected
    if missing or extra:
        raise ValueError(f"record fields differ: missing={sorted(missing)}, extra={sorted(extra)}")
    out = {key: record[key] for key in (
        "evidence_id", "subject_id", "quantity_id", "value", "unit_id", "model_id",
    )}
    if out["value"] is not None:
        if not isinstance(out["value"], str):
            raise ValueError("numeric value must be an exact decimal string, never a binary float")
        if not NUMBER_RE.fullmatch(out["value"]):
            raise ValueError(f"non-canonical exact decimal {out['value']!r}")
    by_id, _ = _indexes(register)
    expected_types = {
        "evidence_id": "evidence",
        "subject_id": "subject",
        "quantity_id": "quantity",
        "unit_id": "unit",
        "model_id": "model",
    }
    for field, semantic_type in expected_types.items():
        row = by_id.get(out[field])
        if row is None or row["semantic_type"] != semantic_type:
            raise ValueError(f"{field} is not a registered {semantic_type}: {out[field]!r}")
    if (out["value"] is None) != (out["evidence_id"] == "evidence:uncertain"):
        raise ValueError("null value and uncertain evidence must occur together")
    if out["value"] is None and out["unit_id"] != "unit:none":
        raise ValueError("a null value must use unit:none")
    return out


def encode_record(record: dict, register: dict, *, spoken_numbers: bool = False) -> str:
    """Encode a typed record; choose compact numerals or fully spoken digits."""
    record = normalize_record(record, register)
    by_id, _ = _indexes(register)
    prefix_ids = [
        "frame:claim", record["evidence_id"], record["subject_id"],
        record["quantity_id"],
    ]
    suffix_ids = [record["unit_id"], record["model_id"], "frame:end"]
    if record["value"] is None:
        number_tokens = [by_id["num:null"]["form"]]
    elif spoken_numbers:
        number_tokens = [
            by_id[CHARACTER_TO_NUMBER_ID[char]]["form"] for char in record["value"]
        ]
    else:
        number_tokens = [record["value"]]
    return " ".join([
        *(by_id[semantic_id]["form"] for semantic_id in prefix_ids),
        *number_tokens,
        *(by_id[semantic_id]["form"] for semantic_id in suffix_ids),
    ])


def decode_claim(text: str, register: dict) -> dict:
    """Decode one claim and reject omissions, additions and category swaps."""
    tokens = text.split()
    if len(tokens) < 8:
        raise ValueError("claim is too short for the fixed reversible frame")
    _, by_form = _indexes(register)
    fixed_tokens = [*tokens[:4], *tokens[-3:]]
    try:
        fixed_ids = [by_form[token]["semantic_id"] for token in fixed_tokens]
    except KeyError as exc:
        raise ValueError(f"unknown planetary-register form {exc.args[0]!r}") from None
    prefix_ids, suffix_ids = fixed_ids[:4], fixed_ids[4:]
    if prefix_ids[0] != "frame:claim" or suffix_ids[-1] != "frame:end":
        raise ValueError("claim boundary forms are missing or misplaced")
    number_tokens = tokens[4:-3]
    if not number_tokens:
        raise ValueError("claim contains no number or null token")
    compact_number = len(number_tokens) == 1 and bool(NUMBER_RE.fullmatch(number_tokens[0]))
    number_ids: list[str] = []
    if compact_number:
        value = number_tokens[0]
    else:
        try:
            number_ids = [by_form[token]["semantic_id"] for token in number_tokens]
        except KeyError as exc:
            raise ValueError(f"unknown number form {exc.args[0]!r}") from None
    if not compact_number and number_ids == ["num:null"]:
        value = None
    elif not compact_number:
        if "num:null" in number_ids:
            raise ValueError("null cannot be combined with numeric characters")
        try:
            value = "".join(NUMBER_MEANINGS[semantic_id] for semantic_id in number_ids)
        except (KeyError, TypeError):
            raise ValueError("number field contains a non-numeric form") from None
        if not NUMBER_RE.fullmatch(value):
            raise ValueError(f"decoded number is not canonical: {value!r}")
    record = {
        "evidence_id": prefix_ids[1],
        "subject_id": prefix_ids[2],
        "quantity_id": prefix_ids[3],
        "value": value,
        "unit_id": suffix_ids[0],
        "model_id": suffix_ids[1],
    }
    return normalize_record(record, register)


def describe_claim(text: str, register: dict) -> dict:
    """Decode a claim and expose the exact burden carried by every word."""
    record = decode_claim(text, register)
    by_id, by_form = _indexes(register)
    tokens = text.split()
    rows = []
    for index, token in enumerate(tokens):
        role = (
            "claim_open" if index == 0 else
            "evidence" if index == 1 else
            "subject" if index == 2 else
            "quantity" if index == 3 else
            "unit" if index == len(tokens) - 3 else
            "model" if index == len(tokens) - 2 else
            "claim_close" if index == len(tokens) - 1 else
            "number"
        )
        if role == "number" and NUMBER_RE.fullmatch(token):
            number_rows = [by_id[CHARACTER_TO_NUMBER_ID[char]] for char in token]
            rows.append({
                "position": index + 1,
                "form": token,
                "ipa": "/" + " ".join(row["phonemic"] for row in number_rows) + "/",
                "role": role,
                "semantic_id": f"numeric-literal:{token}",
                "display": token,
                "burden": "carries this exact decimal character sequence; no rounding or unit is implicit",
                "spoken_as": [row["form"] for row in number_rows],
            })
        else:
            row = by_form[token]
            rows.append({
                "position": index + 1,
                "form": token,
                "ipa": row["ipa"],
                "role": role,
                "semantic_id": row["semantic_id"],
                "display": row["display"],
                "burden": row["burden"],
            })
    quantity = by_id[record["quantity_id"]]
    ipa_words = []
    for token in tokens:
        if NUMBER_RE.fullmatch(token):
            ipa_words.extend(by_id[CHARACTER_TO_NUMBER_ID[char]]["phonemic"] for char in token)
        else:
            ipa_words.append(by_form[token]["phonemic"])
    return {
        "record": record,
        "source": {
            "document": register["source"]["document"],
            "pointer": quantity["source_pointer"],
            "archive_sha256": register["source"]["archive_sha256"],
        },
        "utterance": text,
        "ipa": "/" + " ".join(ipa_words) + "/",
        "words": rows,
    }


def fact_record(fact: dict) -> dict:
    return _record_from_fact(fact)


def find_fact(register: dict, fact_id: str) -> dict:
    matches = [fact for fact in register["facts"] if fact["id"] == fact_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate fact ID {fact_id!r}")
    return matches[0]


def validate_planetary_register(register: dict, *, semantic_language: dict | None = None) -> dict:
    if register.get("schema") != SCHEMA:
        raise ValueError(f"unsupported planetary-register schema; expected {SCHEMA}")
    canonical = copy.deepcopy(register)
    recorded_digest = canonical.pop("canonical_sha256", None)
    if recorded_digest != _digest(canonical):
        raise ValueError("planetary register canonical digest mismatch")
    forms = register["forms"]
    ids = [row["semantic_id"] for row in forms]
    written = [row["form"] for row in forms]
    if len(ids) != len(set(ids)) or len(written) != len(set(written)):
        raise ValueError("planetary register requires unique IDs and forms")
    if any(row["class"] not in {"root", "clause_operator"} for row in forms):
        raise ValueError("planetary register may not add a grammatical class")
    cfg = load_phonology(DEFAULT_PHONOLOGY)
    if any(not is_legal_surface(row["phonemic"], cfg) for row in forms):
        raise ValueError("planetary register contains an illegal phonological form")
    if semantic_language is None:
        semantic_language = build_semantic_language(
            expanded=True, seed=int(register["form_seed"])
        )
    semantic_forms = {
        row["orthographic"]
        for row in (
            *semantic_language["semantic_kernel"]["primes"],
            *semantic_language["semantic_kernel"]["structural_forms"],
            *semantic_language["lexicon"],
        )
    }
    collisions = semantic_forms & set(written)
    if collisions:
        raise ValueError(f"planetary forms collide with semantic language: {sorted(collisions)}")
    facts = register["facts"]
    if len({fact["id"] for fact in facts}) != len(facts):
        raise ValueError("fact IDs must be unique")
    for fact in facts:
        record = normalize_record(_record_from_fact(fact), register)
        if decode_claim(encode_record(record, register), register) != record:
            raise ValueError(f"non-invertible fact {fact['id']}")
        quantity = next(row for row in forms if row["semantic_id"] == fact["quantity_id"])
        if quantity["source_pointer"] != fact["source_pointer"]:
            raise ValueError(f"source pointer mismatch for {fact['id']}")
    return {
        "status": "PASS",
        "facts": len(facts),
        "forms": len(forms),
        "round_trips": len(facts),
        "new_grammatical_classes": 0,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Build the reversible Losica planetary register")
    parser.add_argument("--seed-data", default=str(DEFAULT_PLANETARY_SEED))
    parser.add_argument("--form-seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="planetary-register.json")
    args = parser.parse_args(argv)
    register = build_planetary_register(seed_path=args.seed_data, form_seed=args.form_seed)
    Path(args.out).write_text(
        json.dumps(register, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": args.out, **validate_planetary_register(register)}, indent=2, sort_keys=True))


def use_main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Use the reversible Losica planetary register")
    parser.add_argument("artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)
    say = subparsers.add_parser("say", help="encode one pinned fact")
    say.add_argument("fact_id")
    say.add_argument("--spoken-numbers", action="store_true")
    analyze = subparsers.add_parser("analyze", help="decode and explain every word")
    analyze.add_argument("utterance")
    args = parser.parse_args(argv)
    register = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    validate_planetary_register(register)
    if args.command == "say":
        fact = find_fact(register, args.fact_id)
        utterance = encode_record(
            fact_record(fact), register, spoken_numbers=args.spoken_numbers
        )
        print(json.dumps(describe_claim(utterance, register), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(describe_claim(args.utterance, register), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
