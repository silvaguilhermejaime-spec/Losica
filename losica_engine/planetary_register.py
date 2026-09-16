"""A reversible Losica register whose quantities are compositional expressions.

A claim has this shape (the expression has variable length):

    CLAIM EVIDENCE SUBJECT PREFIX-QUANTITY-EXPRESSION NUMBER UNIT MODEL END

Expression operators have declared arities, so the decoder can recover an
exact tree without punctuation or an opaque word for each database field.
Source-level molecules are conveniences only: they are fully expanded before
a register is emitted and never receive surface forms.
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
SCHEMA = "losica-planetary-register/2"
SEED_SCHEMA = "losica-planetary-seed/2"
VERSION = "0.32.0"

EVIDENCE = {
    "evidence:sampled": ("sampled", "the value is a retained or generated draw; this does not claim that its sampling law is calibrated"),
    "evidence:derived": ("derived", "the value is calculated from other stated inputs under the named model"),
    "evidence:modeled": ("modeled", "the value is an output or state of the named model, not a direct observation"),
    "evidence:conditioned": ("conditioned", "the value has been selected or altered by a declared conditioning operation"),
    "evidence:uncertain": ("uncertain", "the source commits to no value; the null is meaningful and must remain recoverable"),
}
FRAME = {
    "frame:claim": "opens one typed scalar claim",
    "frame:end": "closes the claim and prevents silent attachment of further material",
}
NUMBER_MEANINGS = {
    **{f"num:{digit}": digit for digit in "0123456789"},
    "num:minus": "-", "num:plus": "+", "num:point": ".",
    "num:exponent": "e", "num:null": None,
}
CHARACTER_TO_NUMBER_ID = {value: semantic_id for semantic_id, value in NUMBER_MEANINGS.items() if value is not None}
NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?\Z")
RECORD_FIELDS = ("evidence_id", "subject_id", "quantity_id", "quantity_expression", "value", "unit_id", "model_id")


def _digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _ranked(values, *, seed: int, namespace: str) -> list:
    return sorted(values, key=lambda value: (hashlib.sha256(f"{seed}|{namespace}|{value}".encode()).digest(), value))


def _load_seed(path=DEFAULT_PLANETARY_SEED) -> dict:
    seed = json.loads(Path(path).read_text(encoding="utf-8"))
    if seed.get("schema") != SEED_SCHEMA:
        raise ValueError(f"planetary register requires {SEED_SCHEMA}")
    return seed


def _semantic_rows(language: dict) -> list[dict]:
    return [*language["semantic_kernel"]["primes"], *language["semantic_kernel"]["structural_forms"], *language["lexicon"]]


def _symbol_specs(seed: dict) -> list[dict]:
    rows = [{
        "semantic_id": semantic_id, "class": "clause_operator", "semantic_type": "frame",
        "display": label, "burden": burden, "arity": 0,
    } for semantic_id, (label, burden) in {
        "frame:claim": ("claim", FRAME["frame:claim"]),
        "frame:end": ("end", FRAME["frame:end"]),
    }.items()]
    rows.extend({
        "semantic_id": semantic_id, "class": "root", "semantic_type": "evidence",
        "display": display, "burden": burden, "arity": 0,
    } for semantic_id, (display, burden) in EVIDENCE.items())
    for symbol in seed["symbols"]:
        arity = int(symbol["arity"])
        if arity not in {0, 1, 2}:
            raise ValueError(f"unsupported expression arity for {symbol['id']}: {arity}")
        row = {
            "semantic_id": symbol["id"],
            "class": "root" if arity == 0 else ("clause_operator" if arity == 1 else "relator"),
            "semantic_type": "expression_atom" if arity == 0 else "expression_operator",
            "display": symbol["display"], "burden": f"{symbol['definition']} (prefix arity {arity})",
            "definition": symbol["definition"], "kind": symbol["kind"], "arity": arity,
        }
        if symbol.get("reuse"):
            row["reuse"] = symbol["reuse"]
        rows.append(row)
    rows.extend({
        "semantic_id": unit["id"], "class": "root", "semantic_type": "unit",
        "display": unit["symbol"], "burden": f"sets the numeric unit to {unit['meaning']}; it carries no magnitude", "arity": 0,
    } for unit in seed["units"])
    rows.extend({
        "semantic_id": model["id"], "class": "root", "semantic_type": "model",
        "display": model["id"].split(":", 1)[1],
        "burden": f"attributes the claim to the model registry entry: {model['label']}", "arity": 0,
    } for model in seed["models"])
    rows.extend({
        "semantic_id": semantic_id, "class": "root", "semantic_type": "number",
        "display": "null" if value is None else value,
        "burden": "encodes an explicit null value" if value is None else f"encodes exactly the numeric character {value!r}",
        "arity": 0,
    } for semantic_id, value in NUMBER_MEANINGS.items())
    ids = [row["semantic_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("planetary symbol IDs must be unique")
    return rows


def _assign_forms(rows: list[dict], *, seed: int, semantic_language: dict, retired_forms: set[str]) -> list[dict]:
    semantic_rows = _semantic_rows(semantic_language)
    semantic_by_id = {row["semantic_id"]: row for row in semantic_rows}
    semantic_forms = {row["orthographic"] for row in semantic_rows}
    output, new_rows, used = [], [], set()
    for row in rows:
        if not row.get("reuse"):
            new_rows.append(row)
            continue
        source = semantic_by_id.get(row["reuse"])
        if source is None:
            raise ValueError(f"unknown semantic reuse {row['reuse']!r} for {row['semantic_id']}")
        written = source["orthographic"]
        if written in used:
            raise ValueError(f"reused form {written!r} is assigned more than once")
        used.add(written)
        built = copy.deepcopy(row)
        built.update({
            "form": written, "phonemic": source["form"], "ipa": f"/{source['form']}/",
            "provenance": {"form_assignment": "reused existing semantic-language form", "reuse_semantic_id": row["reuse"], "display_label_used_for_form_assignment": False},
        })
        built.pop("reuse", None)
        output.append(built)
    cfg_data = semantic_language["phonology"]
    cfg = PhonologyConfig(tuple(cfg_data["consonants"]), tuple(cfg_data["vowels"]), tuple(cfg_data["onsets"]), tuple(cfg_data["codas"]), cfg_data["syllable"])
    spelling = semantic_language["orthography"]["segment_symbols"]
    candidates, seen = [], set()
    for root in generate_roots(cfg, [2]):
        if root.prominence != 0:
            continue
        written = orthographic_form(root.form, spelling, cfg)
        if written in semantic_forms or written in retired_forms or written in used or written in seen:
            continue
        seen.add(written)
        candidates.append((root.form, written))
    candidates = _ranked(candidates, seed=seed, namespace="planetary-register-v2")
    if len(candidates) < len(new_rows):
        raise ValueError("not enough collision-free forms for the planetary register")
    assigned = {semantic_id: form for semantic_id, form in zip(sorted(row["semantic_id"] for row in new_rows), candidates)}
    for row in new_rows:
        phonemic, written = assigned[row["semantic_id"]]
        built = copy.deepcopy(row)
        built.update({
            "form": written, "phonemic": phonemic, "ipa": f"/{phonemic}/",
            "provenance": {"form_assignment": "stable semantic ID -> seed-ranked unused legal two-syllable form", "seed": seed, "display_label_used_for_form_assignment": False},
        })
        output.append(built)
    return sorted(output, key=lambda row: row["semantic_id"])


def expand_expression(node: dict, molecules: dict[str, dict], stack: tuple[str, ...] = ()) -> dict:
    """Expand all source macros; the returned tree contains only symbol IDs."""
    if set(node) == {"ref"}:
        ref = node["ref"]
        if ref not in molecules:
            raise ValueError(f"unknown expression molecule {ref!r}")
        if ref in stack:
            raise ValueError(f"cyclic expression molecule: {' -> '.join((*stack, ref))}")
        return expand_expression(molecules[ref], molecules, (*stack, ref))
    if set(node) not in ({"id"}, {"id", "args"}):
        raise ValueError(f"malformed expression node {node!r}")
    return {"id": node["id"], "args": [expand_expression(child, molecules, stack) for child in node.get("args", [])]}


def validate_expression(node: dict, symbol_index: dict[str, dict]) -> None:
    if set(node) != {"id", "args"} or not isinstance(node["args"], list):
        raise ValueError(f"non-canonical expression node {node!r}")
    symbol = symbol_index.get(node["id"])
    if symbol is None or symbol["semantic_type"] not in {"expression_atom", "expression_operator"}:
        raise ValueError(f"unknown expression symbol {node['id']!r}")
    if len(node["args"]) != symbol["arity"]:
        raise ValueError(f"{node['id']} takes {symbol['arity']} arguments, got {len(node['args'])}")
    for child in node["args"]:
        validate_expression(child, symbol_index)


def flatten_expression(node: dict) -> list[str]:
    return [node["id"], *(item for child in node["args"] for item in flatten_expression(child))]


def _expression_key(node: dict) -> str:
    return json.dumps(node, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _build_quantities(seed: dict, symbol_index: dict[str, dict]) -> list[dict]:
    molecules = seed["molecules"]
    subjects_by_quantity: dict[str, set[str]] = {}
    for fact in seed["facts"]:
        subjects_by_quantity.setdefault(fact["quantity_id"], set()).add(fact["subject_id"])
    quantities, keys = [], set()
    for source in seed["quantities"]:
        subjects = subjects_by_quantity.get(source["id"], set())
        if len(subjects) != 1:
            raise ValueError(f"quantity must have exactly one grounded subject: {source['id']}")
        composition = expand_expression(source["composition"], molecules)
        validate_expression(composition, symbol_index)
        key = _expression_key(composition)
        if key in keys:
            raise ValueError(f"duplicate quantity composition for {source['id']}")
        keys.add(key)
        prefix = flatten_expression(composition)
        quantities.append({
            "id": source["id"], "label": source["label"], "subject_id": next(iter(subjects)),
            "source_pointer": source["source_pointer"],
            "composition": composition, "prefix_semantic_ids": prefix, "token_count": len(prefix),
            "composition_sha256": _digest(composition),
        })
    return quantities


def build_planetary_register(*, seed_path=DEFAULT_PLANETARY_SEED, form_seed: int = DEFAULT_SEED) -> dict:
    """Build the finite v0.32 compositional register from the pinned seed."""
    seed = _load_seed(seed_path)
    semantic_language = build_semantic_language(expanded=True, phonology_path=DEFAULT_PHONOLOGY, seed=form_seed)
    forms = _assign_forms(_symbol_specs(seed), seed=form_seed, semantic_language=semantic_language, retired_forms=set(seed["migration"]["retired_forms"]))
    symbol_index = {row["semantic_id"]: row for row in forms}
    quantities = _build_quantities(seed, symbol_index)
    expression_forms = [row for row in forms if row["semantic_type"].startswith("expression_")]
    reused = sum(row.get("provenance", {}).get("form_assignment") == "reused existing semantic-language form" for row in expression_forms)
    register = {
        "schema": SCHEMA, "version": VERSION, "form_seed": form_seed,
        "language_id": f"losica-planetary:{form_seed}:{seed['source']['world_id']}",
        "source": copy.deepcopy(seed["source"]), "research_sources": copy.deepcopy(seed["research_sources"]),
        "design": {
            "claim_order": ["frame:claim", "evidence", "subject", "quantity_expression", "number", "unit", "model", "frame:end"],
            "quantity_representation": "deterministic prefix expression with fixed operator arities",
            "molecules": "source-only macros expanded before surface rendering; zero macro surface forms",
            "evidence_position": "obligatory and first inside the claim frame",
            "number_encoding": "compact writing uses one exact decimal literal; fully spoken form uses one reversible Losica word per character; null has its own word",
            "invertibility_contract": "decode(encode(normalize(record))) == normalize(record)",
            "semantic_burden": "each word denotes a reusable atom or operator; the tree carries the field meaning",
            "opaque_quantity_roots": 0, "new_grammatical_classes": 0,
            "excluded_inferences": ["culture", "emotion", "sensory categories", "metaphor", "biosphere", "people", "acoustic adaptation"],
        },
        "forms": forms, "quantities": quantities, "facts": copy.deepcopy(seed["facts"]),
        "migration": copy.deepcopy(seed["migration"]),
        "coverage": {
            "facts": len(seed["facts"]), "forms": len(forms), "evidence_values": len(EVIDENCE),
            "quantity_expressions": len(quantities), "expression_symbols": len(expression_forms),
            "reused_expression_forms": reused, "new_expression_forms": len(expression_forms) - reused,
            "opaque_quantity_roots": 0, "units": len(seed["units"]), "models": len(seed["models"]), "new_grammatical_classes": 0,
        },
    }
    register["canonical_sha256"] = _digest(register)
    validate_planetary_register(register, semantic_language=semantic_language)
    return register


def _indexes(register: dict) -> tuple[dict, dict]:
    return ({row["semantic_id"]: row for row in register["forms"]}, {row["form"]: row for row in register["forms"]})


def _quantity_indexes(register: dict) -> tuple[dict, dict]:
    return ({row["id"]: row for row in register["quantities"]}, {_expression_key(row["composition"]): row for row in register["quantities"]})


def render_expression(expression: dict, register: dict) -> str:
    by_id, _ = _indexes(register)
    validate_expression(expression, by_id)
    return " ".join(by_id[semantic_id]["form"] for semantic_id in flatten_expression(expression))


def _parse_expression_tokens(tokens: list[str], start: int, register: dict) -> tuple[dict, int]:
    _, by_form = _indexes(register)
    if start >= len(tokens):
        raise ValueError("quantity expression ends before an expected argument")
    token = tokens[start]
    symbol = by_form.get(token)
    if symbol is None:
        raise ValueError(f"unknown planetary-register form {token!r}")
    if symbol["semantic_type"] not in {"expression_atom", "expression_operator"}:
        raise ValueError(f"form {token!r} is not valid inside a quantity expression")
    next_index, args = start + 1, []
    for _ in range(symbol["arity"]):
        child, next_index = _parse_expression_tokens(tokens, next_index, register)
        args.append(child)
    return {"id": symbol["semantic_id"], "args": args}, next_index


def decode_expression(text: str, register: dict) -> dict:
    tokens = text.split()
    if not tokens:
        raise ValueError("quantity expression is empty")
    expression, next_index = _parse_expression_tokens(tokens, 0, register)
    if next_index != len(tokens):
        raise ValueError("quantity expression has trailing material")
    return expression


def fact_record(fact: dict, register: dict) -> dict:
    quantity_by_id, _ = _quantity_indexes(register)
    quantity = quantity_by_id.get(fact["quantity_id"])
    if quantity is None:
        raise ValueError(f"unknown quantity ID {fact['quantity_id']!r}")
    return {
        "evidence_id": fact["evidence_id"], "subject_id": fact["subject_id"],
        "quantity_id": fact["quantity_id"], "quantity_expression": copy.deepcopy(quantity["composition"]),
        "value": fact["value"], "unit_id": fact["unit_id"], "model_id": fact["model_id"],
    }


def normalize_record(record: dict, register: dict) -> dict:
    """Return the exact seven-field semantic payload accepted by the codec."""
    expected = set(RECORD_FIELDS)
    missing, extra = expected - set(record), set(record) - expected
    if missing or extra:
        raise ValueError(f"record fields differ: missing={sorted(missing)}, extra={sorted(extra)}")
    out = {key: copy.deepcopy(record[key]) for key in RECORD_FIELDS}
    if out["value"] is not None:
        if not isinstance(out["value"], str):
            raise ValueError("numeric value must be an exact decimal string, never a binary float")
        if not NUMBER_RE.fullmatch(out["value"]):
            raise ValueError(f"non-canonical exact decimal {out['value']!r}")
    by_id, _ = _indexes(register)
    for field, semantic_type in {"evidence_id": "evidence", "subject_id": "expression_atom", "unit_id": "unit", "model_id": "model"}.items():
        row = by_id.get(out[field])
        if row is None or row["semantic_type"] != semantic_type:
            raise ValueError(f"{field} is not a registered {semantic_type}: {out[field]!r}")
    if by_id[out["subject_id"]].get("kind") != "entity":
        raise ValueError("subject_id must denote an entity")
    quantity_by_id, _ = _quantity_indexes(register)
    quantity = quantity_by_id.get(out["quantity_id"])
    if quantity is None:
        raise ValueError(f"quantity_id is not a registered quantity expression: {out['quantity_id']!r}")
    validate_expression(out["quantity_expression"], by_id)
    if out["quantity_expression"] != quantity["composition"]:
        raise ValueError("quantity_expression does not match quantity_id")
    if out["subject_id"] != quantity["subject_id"]:
        raise ValueError("subject_id does not match the grounded quantity")
    if (out["value"] is None) != (out["evidence_id"] == "evidence:uncertain"):
        raise ValueError("null value and uncertain evidence must occur together")
    if out["value"] is None and out["unit_id"] != "unit:none":
        raise ValueError("a null value must use unit:none")
    return out


def encode_record(record: dict, register: dict, *, spoken_numbers: bool = False) -> str:
    record = normalize_record(record, register)
    by_id, _ = _indexes(register)
    expression_tokens = render_expression(record["quantity_expression"], register).split()
    if record["value"] is None:
        number_tokens = [by_id["num:null"]["form"]]
    elif spoken_numbers:
        number_tokens = [by_id[CHARACTER_TO_NUMBER_ID[char]]["form"] for char in record["value"]]
    else:
        number_tokens = [record["value"]]
    return " ".join([
        by_id["frame:claim"]["form"], by_id[record["evidence_id"]]["form"], by_id[record["subject_id"]]["form"],
        *expression_tokens, *number_tokens, by_id[record["unit_id"]]["form"], by_id[record["model_id"]]["form"], by_id["frame:end"]["form"],
    ])


def _decode_number(tokens: list[str], by_form: dict) -> str | None:
    if not tokens:
        raise ValueError("claim contains no number or null token")
    if len(tokens) == 1 and NUMBER_RE.fullmatch(tokens[0]):
        return tokens[0]
    try:
        ids = [by_form[token]["semantic_id"] for token in tokens]
    except KeyError as exc:
        raise ValueError(f"unknown number form {exc.args[0]!r}") from None
    if ids == ["num:null"]:
        return None
    if "num:null" in ids:
        raise ValueError("null cannot be combined with numeric characters")
    try:
        value = "".join(NUMBER_MEANINGS[semantic_id] for semantic_id in ids)
    except (KeyError, TypeError):
        raise ValueError("number field contains a non-numeric form") from None
    if not NUMBER_RE.fullmatch(value):
        raise ValueError(f"decoded number is not canonical: {value!r}")
    return value


def decode_claim(text: str, register: dict) -> dict:
    tokens = text.split()
    if len(tokens) < 8:
        raise ValueError("claim is too short for the reversible frame")
    _, by_form = _indexes(register)
    for token in [*tokens[:3], *tokens[-3:]]:
        if token not in by_form:
            raise ValueError(f"unknown planetary-register form {token!r}")
    if by_form[tokens[0]]["semantic_id"] != "frame:claim" or by_form[tokens[-1]]["semantic_id"] != "frame:end":
        raise ValueError("claim boundary forms are missing or misplaced")
    expression, next_index = _parse_expression_tokens(tokens, 3, register)
    if next_index > len(tokens) - 3:
        raise ValueError("quantity expression consumes the unit, model, or closing frame")
    value = _decode_number(tokens[next_index:-3], by_form)
    _, quantity_by_expression = _quantity_indexes(register)
    quantity = quantity_by_expression.get(_expression_key(expression))
    if quantity is None:
        raise ValueError("quantity expression is grammatical but is not a registered grounded field")
    return normalize_record({
        "evidence_id": by_form[tokens[1]]["semantic_id"], "subject_id": by_form[tokens[2]]["semantic_id"],
        "quantity_id": quantity["id"], "quantity_expression": expression, "value": value,
        "unit_id": by_form[tokens[-3]]["semantic_id"], "model_id": by_form[tokens[-2]]["semantic_id"],
    }, register)


def describe_claim(text: str, register: dict) -> dict:
    record = decode_claim(text, register)
    by_id, by_form = _indexes(register)
    quantity_by_id, _ = _quantity_indexes(register)
    quantity = quantity_by_id[record["quantity_id"]]
    tokens = text.split()
    _, expression_end = _parse_expression_tokens(tokens, 3, register)
    rows = []
    for index, token in enumerate(tokens):
        if index == 0: role = "claim_open"
        elif index == 1: role = "evidence"
        elif index == 2: role = "subject"
        elif 3 <= index < expression_end: role = "quantity_operator" if by_form[token]["arity"] else "quantity_atom"
        elif index == len(tokens) - 3: role = "unit"
        elif index == len(tokens) - 2: role = "model"
        elif index == len(tokens) - 1: role = "claim_close"
        else: role = "number"
        if role == "number" and NUMBER_RE.fullmatch(token):
            number_rows = [by_id[CHARACTER_TO_NUMBER_ID[char]] for char in token]
            rows.append({
                "position": index + 1, "form": token,
                "ipa": "/" + " ".join(row["phonemic"] for row in number_rows) + "/",
                "role": role, "semantic_id": f"numeric-literal:{token}", "display": token,
                "burden": "carries this exact decimal character sequence; no rounding or unit is implicit",
                "spoken_as": [row["form"] for row in number_rows],
            })
        else:
            row = by_form[token]
            item = {"position": index + 1, "form": token, "ipa": row["ipa"], "role": role, "semantic_id": row["semantic_id"], "display": row["display"], "burden": row["burden"]}
            if role.startswith("quantity_"):
                item.update({"arity": row["arity"], "expression_index": index - 2})
            rows.append(item)
    ipa_words = []
    for token in tokens:
        if NUMBER_RE.fullmatch(token):
            ipa_words.extend(by_id[CHARACTER_TO_NUMBER_ID[char]]["phonemic"] for char in token)
        else:
            ipa_words.append(by_form[token]["phonemic"])
    return {
        "record": record, "quantity": copy.deepcopy(quantity),
        "source": {"document": register["source"]["document"], "pointer": quantity["source_pointer"], "archive_sha256": register["source"]["archive_sha256"]},
        "utterance": text, "ipa": "/" + " ".join(ipa_words) + "/", "words": rows,
    }


def find_fact(register: dict, fact_id: str) -> dict:
    matches = [fact for fact in register["facts"] if fact["id"] == fact_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate fact ID {fact_id!r}")
    return matches[0]


def find_quantity(register: dict, quantity_id: str) -> dict:
    matches = [row for row in register["quantities"] if row["id"] == quantity_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate quantity ID {quantity_id!r}")
    return matches[0]


def validate_planetary_register(register: dict, *, semantic_language: dict | None = None) -> dict:
    if register.get("schema") != SCHEMA:
        raise ValueError(f"unsupported planetary-register schema; expected {SCHEMA}")
    canonical = copy.deepcopy(register)
    recorded_digest = canonical.pop("canonical_sha256", None)
    if recorded_digest != _digest(canonical):
        raise ValueError("planetary register canonical digest mismatch")
    forms = register["forms"]
    ids, written = [row["semantic_id"] for row in forms], [row["form"] for row in forms]
    if len(ids) != len(set(ids)) or len(written) != len(set(written)):
        raise ValueError("planetary register requires unique IDs and forms")
    if any(row["class"] not in {"root", "relator", "clause_operator"} for row in forms):
        raise ValueError("planetary register may not add a grammatical class")
    if any(row["semantic_id"].startswith("quantity:") or row["semantic_type"] == "quantity" for row in forms):
        raise ValueError("quantities may not be lexicalized as opaque register forms")
    if set(register["migration"]["retired_forms"]) & set(written):
        raise ValueError("a retired opaque quantity form was reassigned")
    cfg = load_phonology(DEFAULT_PHONOLOGY)
    if any(not is_legal_surface(row["phonemic"], cfg) for row in forms):
        raise ValueError("planetary register contains an illegal phonological form")
    if semantic_language is None:
        semantic_language = build_semantic_language(expanded=True, seed=int(register["form_seed"]))
    semantic_rows = _semantic_rows(semantic_language)
    semantic_by_id = {row["semantic_id"]: row for row in semantic_rows}
    semantic_by_form = {row["orthographic"]: row for row in semantic_rows}
    for row in forms:
        collision = semantic_by_form.get(row["form"])
        reuse = row["provenance"].get("reuse_semantic_id")
        if collision is None and reuse is not None:
            raise ValueError(f"declared semantic reuse has no form collision: {row['semantic_id']}")
        if collision is not None and (reuse != collision["semantic_id"] or semantic_by_id[reuse]["form"] != row["phonemic"]):
            raise ValueError(f"undeclared or incorrect semantic form reuse: {row['semantic_id']}")
    by_id, _ = _indexes(register)
    quantities = register["quantities"]
    if len({row["id"] for row in quantities}) != len(quantities):
        raise ValueError("quantity IDs must be unique")
    if len({_expression_key(row["composition"]) for row in quantities}) != len(quantities):
        raise ValueError("quantity expressions must be unique")
    for quantity in quantities:
        validate_expression(quantity["composition"], by_id)
        prefix = flatten_expression(quantity["composition"])
        if quantity["prefix_semantic_ids"] != prefix or quantity["token_count"] != len(prefix):
            raise ValueError(f"quantity prefix metadata mismatch: {quantity['id']}")
        if quantity["composition_sha256"] != _digest(quantity["composition"]):
            raise ValueError(f"quantity composition digest mismatch: {quantity['id']}")
        if quantity["token_count"] <= 1:
            raise ValueError(f"quantity remains an opaque one-word expression: {quantity['id']}")
        if decode_expression(render_expression(quantity["composition"], register), register) != quantity["composition"]:
            raise ValueError(f"non-invertible quantity expression: {quantity['id']}")
    facts = register["facts"]
    if len({fact["id"] for fact in facts}) != len(facts):
        raise ValueError("fact IDs must be unique")
    quantity_by_id, _ = _quantity_indexes(register)
    for fact in facts:
        record = normalize_record(fact_record(fact, register), register)
        for spoken in (False, True):
            if decode_claim(encode_record(record, register, spoken_numbers=spoken), register) != record:
                raise ValueError(f"non-invertible fact {fact['id']}")
        if quantity_by_id[fact["quantity_id"]]["source_pointer"] != fact["source_pointer"]:
            raise ValueError(f"source pointer mismatch for {fact['id']}")
    return {"status": "PASS", "facts": len(facts), "forms": len(forms), "quantity_expressions": len(quantities), "opaque_quantity_roots": 0, "round_trips": len(facts) * 2, "new_grammatical_classes": 0}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Build the compositional Losica planetary register")
    parser.add_argument("--seed-data", default=str(DEFAULT_PLANETARY_SEED))
    parser.add_argument("--form-seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="planetary-register.json")
    args = parser.parse_args(argv)
    register = build_planetary_register(seed_path=args.seed_data, form_seed=args.form_seed)
    Path(args.out).write_text(json.dumps(register, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": args.out, **validate_planetary_register(register)}, indent=2, sort_keys=True))


def use_main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Use the compositional Losica planetary register")
    parser.add_argument("artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)
    say = subparsers.add_parser("say", help="encode one pinned fact")
    say.add_argument("fact_id")
    say.add_argument("--spoken-numbers", action="store_true")
    analyze = subparsers.add_parser("analyze", help="decode and explain every word")
    analyze.add_argument("utterance")
    expression = subparsers.add_parser("expression", help="show a quantity composition")
    expression.add_argument("quantity_id")
    args = parser.parse_args(argv)
    register = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    validate_planetary_register(register)
    if args.command == "say":
        fact = find_fact(register, args.fact_id)
        utterance = encode_record(fact_record(fact, register), register, spoken_numbers=args.spoken_numbers)
        print(json.dumps(describe_claim(utterance, register), ensure_ascii=False, indent=2))
    elif args.command == "analyze":
        print(json.dumps(describe_claim(args.utterance, register), ensure_ascii=False, indent=2))
    else:
        quantity = find_quantity(register, args.quantity_id)
        print(json.dumps({**copy.deepcopy(quantity), "utterance": render_expression(quantity["composition"], register)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
