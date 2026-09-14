"""Fail-closed projection of experience into Losica's causal input format.

The generator sees numeric transducer samples, opaque controls, time, and source
offsets.  Names, outcomes, supplied event boundaries, oracle state, and learned
semantic products have no representation in this schema.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable


SCHEMA = "losica-causal-stream/1"
TOP_LEVEL_FIELDS = frozenset({"schema", "frames", "source_sha256"})
FRAME_FIELDS = frozenset({"t", "samples", "controls", "source_offset"})
FORBIDDEN_KEY_PARTS = frozenset({
    "name", "label", "gloss", "text", "description", "concept", "class",
    "category", "task", "goal", "reward", "score", "success", "terminal",
    "termination", "done", "outcome", "episode", "boundary", "object",
    "material", "inventory", "predicate", "state", "pose", "velocity",
    "contact", "map", "recipe", "target", "molecule", "receptor", "emotion",
    "diagnosis", "mask", "box", "caption", "embedding", "checkpoint",
    "pretrained", "oracle", "semantic", "english", "language",
})


class CausalBoundaryError(ValueError):
    """An input attempted to cross the causal boundary."""


def _tokens(key: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in key)
    return set(normalized.split())


def _reject_interpreted_keys(value, path: str = "$" ) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _tokens(str(key)) & FORBIDDEN_KEY_PARTS:
                raise CausalBoundaryError(f"interpreted field is forbidden at {path}.{key}")
            _reject_interpreted_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_interpreted_keys(item, f"{path}[{index}]")


def _finite_number(value, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CausalBoundaryError(f"{path} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise CausalBoundaryError(f"{path} must be finite")
    return result


def flatten_numeric(value, path: str = "samples") -> list[float]:
    """Flatten an unnamed numeric tensor without importing dimension labels."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [_finite_number(value, path)]
    if not isinstance(value, list) or not value:
        raise CausalBoundaryError(f"{path} must be a non-empty numeric tensor")
    out: list[float] = []
    for index, item in enumerate(value):
        out.extend(flatten_numeric(item, f"{path}[{index}]"))
    return out


def _canonical_payload(stream: dict) -> bytes:
    return (json.dumps(stream, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def causal_stream_sha256(stream: dict) -> str:
    return hashlib.sha256(_canonical_payload(validate_causal_stream(stream))).hexdigest()


def validate_causal_stream(value: dict) -> dict:
    """Return a normalized stream or fail on every unrepresented input kind."""
    if not isinstance(value, dict):
        raise CausalBoundaryError("causal stream must be an object")
    _reject_interpreted_keys(value)
    extra = set(value) - TOP_LEVEL_FIELDS
    if extra:
        raise CausalBoundaryError(f"unregistered causal-stream fields: {sorted(extra)}")
    if value.get("schema") != SCHEMA:
        raise CausalBoundaryError(f"{SCHEMA} required")
    frames = value.get("frames")
    if not isinstance(frames, list) or len(frames) < 12:
        raise CausalBoundaryError("causal stream requires at least 12 ordered frames")

    normalized = []
    previous_t = -math.inf
    sample_width = control_width = None
    for index, frame in enumerate(frames):
        path = f"frames[{index}]"
        if not isinstance(frame, dict):
            raise CausalBoundaryError(f"{path} must be an object")
        extra = set(frame) - FRAME_FIELDS
        missing = {"t", "samples", "controls", "source_offset"} - set(frame)
        if extra or missing:
            raise CausalBoundaryError(f"{path} fields mismatch; extra={sorted(extra)} missing={sorted(missing)}")
        t = _finite_number(frame["t"], f"{path}.t")
        if t <= previous_t:
            raise CausalBoundaryError("frame times must increase strictly")
        previous_t = t
        offset = frame["source_offset"]
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CausalBoundaryError(f"{path}.source_offset must be a non-negative integer")
        samples = flatten_numeric(frame["samples"], f"{path}.samples")
        controls = flatten_numeric(frame["controls"], f"{path}.controls")
        sample_width = len(samples) if sample_width is None else sample_width
        control_width = len(controls) if control_width is None else control_width
        if len(samples) != sample_width or len(controls) != control_width:
            raise CausalBoundaryError("sample and control tensor widths must remain constant")
        normalized.append({"t": t, "samples": samples, "controls": controls, "source_offset": offset})

    source_sha256 = value.get("source_sha256")
    if source_sha256 is not None and (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in source_sha256)
    ):
        raise CausalBoundaryError("source_sha256 must be a lowercase SHA-256 digest")
    body = {"schema": SCHEMA, "frames": normalized}
    body["source_sha256"] = source_sha256 or hashlib.sha256(_canonical_payload(body)).hexdigest()
    return body


def load_causal_stream(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    obj = json.loads(raw)
    projected = validate_causal_stream(obj)
    supplied = obj.get("source_sha256")
    if supplied is None:
        projected["source_sha256"] = hashlib.sha256(raw).hexdigest()
    return projected


def make_causal_stream(frames: Iterable[dict], *, source_bytes: bytes | None = None) -> dict:
    """Build the strict schema from already-selected numeric frame records."""
    data = {"schema": SCHEMA, "frames": list(frames)}
    if source_bytes is not None:
        data["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    return validate_causal_stream(data)


def generation_materials(stream: dict) -> dict:
    stream = validate_causal_stream(stream)
    return {
        "schema": "losica-generation-materials/1",
        "materials": [{
            "kind": "causal_stream",
            "sha256": causal_stream_sha256(stream),
            "source_sha256": stream["source_sha256"],
            "frame_count": len(stream["frames"]),
            "sample_width": len(stream["frames"][0]["samples"]),
            "control_width": len(stream["frames"][0]["controls"]),
        }],
        "excluded_kinds": [
            "names", "labels", "targets", "authored_outcomes", "supplied_boundaries",
            "oracle_state", "target_specific_sensors", "pretrained_representations",
            "human_language_resources",
        ],
    }
