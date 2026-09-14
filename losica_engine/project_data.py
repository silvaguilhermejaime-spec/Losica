from pathlib import Path
import math

from .validation import (
    read_text, read_json, json_value, keys, require,
    identifier, text,
    MAX_STIMULI, MAX_CATEGORIES, MAX_CATEGORY_MEMBERS,
    MAX_MEASUREMENTS_PER_STIMULUS,
)

_OPTIONAL_STIMULUS_METADATA = {
    "region_id", "source_process", "temporal_support", "model", "status",
}

def _number(value, context):
    require(type(value) in {int, float} and math.isfinite(value), f"{context}: finite number required")
    return value

def _measurement_value(value, context):
    if type(value) in {int, float}:
        return _number(value, context)
    require(isinstance(value, list) and bool(value), f"{context}: finite number or non-empty numeric list required")
    require(len(value) <= 4096, f"{context}: numeric list too long")
    return tuple(_number(v, context) for v in value)

def load_stimuli(path: str | Path) -> dict[str, dict]:
    """Load quantitative stimulus records.

    A stimulus contains operational measurements with provenance metadata.
    The accepted shape is compatible with the world's quantitative observation
    handoff JSONL.
    """
    out = {}
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        require(len(out) < MAX_STIMULI, f"stimuli: at most {MAX_STIMULI} entries supported")
        item = json_value(line)
        keys(item, {"id", "measurements"}, _OPTIONAL_STIMULUS_METADATA, "stimulus")
        stimulus_id = identifier(item.get("id"), "stimulus id")
        require(stimulus_id not in out, f"stimuli line {line_number}: duplicate stimulus id {stimulus_id!r}")
        measurements = item.get("measurements")
        require(isinstance(measurements, list), f"stimulus {stimulus_id!r}: measurements must be a list")
        require(len(measurements) <= MAX_MEASUREMENTS_PER_STIMULUS,
                f"stimulus {stimulus_id!r}: at most {MAX_MEASUREMENTS_PER_STIMULUS} measurements supported")
        normalized = {}
        for measurement in measurements:
            keys(measurement, {"quantity_id", "value", "unit", "source", "model", "status"}, {"aggregation"}, "measurement")
            qid = identifier(measurement.get("quantity_id"), "measurement quantity_id")
            require(qid not in normalized, f"stimulus {stimulus_id!r}: duplicate measurement quantity_id {qid!r}")
            unit = text(measurement.get("unit"), "measurement unit", 128)
            source = text(measurement.get("source"), "measurement source", 2048)
            model = identifier(measurement.get("model"), "measurement model")
            status = identifier(measurement.get("status"), "measurement status")
            aggregation = measurement.get("aggregation")
            if aggregation is not None:
                aggregation = text(aggregation, "measurement aggregation", 256)
            normalized[qid] = {
                "value": _measurement_value(measurement.get("value"), f"measurement {qid!r} value"),
                "unit": unit,
                "source": source,
                "model": model,
                "status": status,
                **({"aggregation": aggregation} if aggregation is not None else {}),
            }
        out[stimulus_id] = {"id": stimulus_id, "measurements": normalized}
    return out

def load_categories(path: str | Path, stimulus_ids: set[str]) -> list[dict]:
    data = read_json(path)
    keys(data, {"categories"}, context="categories")
    categories = data["categories"]
    require(isinstance(categories, list), "categories must be a list")
    require(len(categories) <= MAX_CATEGORIES, f"categories: at most {MAX_CATEGORIES} entries supported")
    out = []
    seen = set()
    for category in categories:
        keys(category, {"id", "members"}, context="category")
        category_id = identifier(category.get("id"), "category id")
        require(category_id not in seen, f"duplicate category id {category_id!r}")
        seen.add(category_id)
        members = category.get("members")
        require(isinstance(members, list) and bool(members), f"category {category_id!r}: members must contain at least one stimulus ID")
        require(len(members) <= MAX_CATEGORY_MEMBERS, f"category {category_id!r}: at most {MAX_CATEGORY_MEMBERS} members supported")
        normalized_members = []
        member_seen = set()
        for member in members:
            normalized = identifier(member, "category member ID")
            require(normalized not in member_seen, f"category {category_id!r}: duplicate stimulus member")
            member_seen.add(normalized)
            normalized_members.append(normalized)
        missing = [x for x in normalized_members if x not in stimulus_ids]
        if missing:
            raise ValueError(f"category {category_id!r}: unknown stimulus ID(s): " + ", ".join(repr(x) for x in missing))
        out.append({"id": category_id, "members": tuple(normalized_members)})
    return out

def measurement_catalog(stimuli_by_id: dict[str, dict]) -> dict[str, str]:
    """Return quantity -> unit, rejecting silent unit changes under one identifier."""
    catalog = {}
    for stimulus in stimuli_by_id.values():
        for qid, measurement in stimulus["measurements"].items():
            unit = measurement["unit"]
            if qid in catalog:
                require(catalog[qid] == unit,
                        f"measurement {qid!r}: inconsistent units {catalog[qid]!r} and {unit!r}")
            else:
                catalog[qid] = unit
    return catalog
