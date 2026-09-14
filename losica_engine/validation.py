"""Bounded input language and immutable validated values."""
import json
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path
from types import MappingProxyType

INPUT_SNAPSHOT = ContextVar("input_snapshot", default=None)

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_ROOT_SYLLABLES = 12

MAX_BUDGET = 10_000_000
MAX_RELATION_EVALUATIONS = 100_000_000
MAX_RELATION_MATCHES = 10_000_000
MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024

MAX_ID_CHARS = 128
MAX_LABEL_CHARS = 128
MAX_TEXT_CHARS = 256
MAX_DESCRIPTION_CHARS = 4096
MAX_PROVENANCE_CHARS = 2048

MAX_STIMULI = 100_000
MAX_CATEGORIES = 10_000
MAX_CATEGORY_MEMBERS = 10_000
MAX_MEASUREMENTS_PER_STIMULUS = 128
MAX_RELATIONS = 1024
MAX_PROPERTY_ITEMS = 64
MAX_PROCESSES = 10_000
MAX_LEXEMES = 100_000

def require(ok, context):
    if not ok:
        raise ValueError(context)

def text(value, context, max_chars=MAX_TEXT_CHARS):
    require(
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and not any(ord(c) < 32 for c in value),
        f"{context}: trimmed printable string required",
    )
    require(
        len(value) <= max_chars,
        f"{context}: length exceeds {max_chars} characters",
    )
    return value

def identifier(value, context):
    return text(value, context, MAX_ID_CHARS)

def label(value, context):
    return text(value, context, MAX_LABEL_CHARS)

def description(value, context):
    return text(value, context, MAX_DESCRIPTION_CHARS)

def provenance_text(value, context):
    return text(value, context, MAX_PROVENANCE_CHARS)

def keys(obj, required, optional=(), context="object"):
    require(isinstance(obj, dict), f"{context}: object required")
    require(
        not (set(required) - obj.keys()),
        f"{context}: missing fields {sorted(set(required) - obj.keys())}",
    )
    allowed = set(required) | set(optional)
    require(
        obj.keys() <= allowed,
        f"{context}: fields must be within {sorted(allowed)}",
    )

def strings(value, context, empty=False, max_items=64, max_chars=MAX_TEXT_CHARS):
    require(isinstance(value, list), f"{context}: list required")
    require(len(value) <= max_items, f"{context}: at most {max_items} values supported")
    for item in value:
        if empty and item == "":
            continue
        text(item, context, max_chars)
    require(len(value) == len(set(value)), f"{context}: duplicate values")
    return tuple(value)

def read_text(path):
    path = Path(path)
    snapshot = INPUT_SNAPSHOT.get()
    if snapshot is not None:
        return snapshot[str(path.absolute())]
    with path.open("rb") as f:
        raw = f.read(MAX_INPUT_BYTES + 1)
    require(
        len(raw) <= MAX_INPUT_BYTES,
        f"{path}: input exceeds {MAX_INPUT_BYTES} bytes",
    )
    return raw.decode("utf-8")

def _object(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, f"duplicate JSON key {k!r}")
        result[k] = v
    return result

def json_value(raw):
    return json.loads(
        raw,
        object_pairs_hook=_object,
        parse_constant=lambda x: require(False, f"invalid JSON constant {x}"),
    )

def read_json(path):
    return json_value(read_text(path))

def deep_freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({
            k: deep_freeze(v)
            for k, v in value.items()
        })
    if isinstance(value, list):
        return tuple(deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(deep_freeze(v) for v in value)
    if isinstance(value, frozenset):
        return frozenset(deep_freeze(v) for v in value)
    return value

def jsonable(value):
    """Return a deterministic JSON-compatible copy."""
    if isinstance(value, Mapping):
        return {
            str(k): jsonable(v)
            for k, v in value.items()
        }
    if isinstance(value, tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, frozenset):
        return [jsonable(v) for v in sorted(value)]
    if hasattr(value, "serialize") and callable(value.serialize):
        return jsonable(value.serialize())
    return value
