from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "losica-usage-event/1"
ATTACHMENTS = {"independent", "clitic", "affix"}
ORDERS = {"before", "after"}

@dataclass(frozen=True)
class UsageEvent:
    event_id: str
    generation: int
    construction_id: str
    host_lexeme_id: str
    marker_lexeme_id: str
    function_id: str
    order: str
    attachment: str
    marker_form: str
    count: int
    position: int
    pathway_id: str
    provenance: str


def load_usage_events(path: str | Path) -> list[UsageEvent]:
    out = []
    seen = set()
    p = Path(path)
    if not p.exists():
        return out
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("schema") != SCHEMA:
            raise ValueError(f"{p}:{line_no}: schema must be {SCHEMA}")
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError(f"{p}:{line_no}: event_id required")
        if event_id in seen:
            raise ValueError(f"{p}:{line_no}: duplicate event_id {event_id!r}")
        seen.add(event_id)
        generation = row.get("generation")
        count = row.get("count", 1)
        if not isinstance(generation, int) or generation < 0:
            raise ValueError(f"{p}:{line_no}: nonnegative integer generation required")
        if not isinstance(count, int) or count < 1:
            raise ValueError(f"{p}:{line_no}: positive integer count required")
        order = row.get("order")
        attachment = row.get("attachment")
        if order not in ORDERS:
            raise ValueError(f"{p}:{line_no}: order must be before or after")
        if attachment not in ATTACHMENTS:
            raise ValueError(f"{p}:{line_no}: attachment must be independent, clitic, or affix")
        required = ["construction_id", "host_lexeme_id", "marker_lexeme_id", "function_id", "marker_form"]
        for key in required:
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"{p}:{line_no}: {key} required")
        position = row.get("position", -1 if order == "before" else 1)
        if not isinstance(position, int) or position == 0:
            raise ValueError(f"{p}:{line_no}: position must be a nonzero integer")
        if (position < 0) != (order == "before"):
            raise ValueError(f"{p}:{line_no}: position sign must match order")
        pathway_id = row.get("pathway_id", "")
        if pathway_id is not None and not isinstance(pathway_id, str):
            raise ValueError(f"{p}:{line_no}: pathway_id must be a string")
        out.append(UsageEvent(
            event_id=event_id,
            generation=generation,
            construction_id=row["construction_id"],
            host_lexeme_id=row["host_lexeme_id"],
            marker_lexeme_id=row["marker_lexeme_id"],
            function_id=row["function_id"],
            order=order,
            attachment=attachment,
            marker_form=row["marker_form"],
            count=count,
            position=position,
            pathway_id=pathway_id or "",
            provenance=str(row.get("provenance", "")),
        ))
    out.sort(key=lambda e: (e.generation, e.event_id))
    return out
