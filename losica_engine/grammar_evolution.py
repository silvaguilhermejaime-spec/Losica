from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .usage_history import UsageEvent

ATTACHMENT_RANK = {"independent": 0, "clitic": 1, "affix": 2}

@dataclass(frozen=True)
class MarkerState:
    marker_lexeme_id: str
    function_id: str
    attachment: str
    order: str
    position: int
    form: str
    token_frequency: int
    host_type_count: int
    construction_type_count: int
    generation_first: int
    generation_last: int
    pathway_ids: tuple[str, ...]
    observed_forms: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]


def infer_marker_states(events: list[UsageEvent]) -> list[MarkerState]:
    """Collapse longitudinal usage observations into current marker states.

    Function IDs and attachment states come from the usage history. Recurrence
    across hosts and constructions supplies productivity measures for each
    marker state.
    """
    groups = defaultdict(list)
    for e in events:
        groups[(e.marker_lexeme_id, e.function_id)].append(e)

    out: list[MarkerState] = []
    for (marker, function), rows in groups.items():
        rows = sorted(rows, key=lambda e: (e.generation, e.event_id))
        latest_generation = rows[-1].generation
        latest = [e for e in rows if e.generation == latest_generation]

        attachment_counts: Counter[str] = Counter()
        order_counts: Counter[str] = Counter()
        position_counts: Counter[int] = Counter()
        form_counts: Counter[str] = Counter()
        for e in latest:
            attachment_counts[e.attachment] += e.count
            order_counts[e.order] += e.count
            position_counts[e.position] += e.count
            form_counts[e.marker_form] += e.count

        attachment = max(
            attachment_counts,
            key=lambda x: (attachment_counts[x], ATTACHMENT_RANK[x]),
        )
        order = max(order_counts, key=lambda x: (order_counts[x], x))
        position = max(position_counts, key=lambda x: (position_counts[x], -abs(x), x))
        form = max(form_counts, key=lambda x: (form_counts[x], x))

        out.append(MarkerState(
            marker_lexeme_id=marker,
            function_id=function,
            attachment=attachment,
            order=order,
            position=position,
            form=form,
            token_frequency=sum(e.count for e in rows),
            host_type_count=len({e.host_lexeme_id for e in rows}),
            construction_type_count=len({e.construction_id for e in rows}),
            generation_first=min(e.generation for e in rows),
            generation_last=latest_generation,
            pathway_ids=tuple(sorted({e.pathway_id for e in rows if e.pathway_id})),
            observed_forms=tuple(sorted({e.marker_form for e in rows})),
            evidence_event_ids=tuple(e.event_id for e in rows),
        ))
    return sorted(out, key=lambda s: (s.position, s.function_id, s.marker_lexeme_id))


def active_affixes(states: list[MarkerState]) -> list[MarkerState]:
    return [s for s in states if s.attachment == "affix"]


def realize(
    stem: str,
    markers: list[MarkerState],
    marker_forms: dict[tuple[str, str], str] | None = None,
) -> str:
    """Concatenate bound morphemes before phonotactic parsing.

    `marker_forms` supplies host-conditioned forms from the current usage
    history. The returned segment string is the input to phonotactic parsing.
    """
    forms = marker_forms or {}

    def form(m: MarkerState) -> str:
        return forms.get((m.marker_lexeme_id, m.function_id), m.form).replace(".", "")

    before = sorted(
        (m for m in markers if m.attachment == "affix" and m.position < 0),
        key=lambda m: m.position,
    )
    after = sorted(
        (m for m in markers if m.attachment == "affix" and m.position > 0),
        key=lambda m: m.position,
    )
    return "".join(form(m) for m in before) + stem.replace(".", "") + "".join(form(m) for m in after)
