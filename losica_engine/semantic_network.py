"""Generated lexical-semantic regions over structural cross-linguistic evidence.

The core consumes stable probe identifiers plus numeric graph structure.  A semantic
region is a Losica-internal object.  External Concepticon identifiers are anchors
used to locate the region from adapters and documentation.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import random

from .semantic_core import concepticon_link, meaning_region_id


MEMBERSHIP_ALGORITHM = "colex-region-v1"


def _stable_float(*parts: object) -> float:
    payload = "|".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _score(row: dict) -> tuple:
    return (
        int(row.get("network_rank") or 10**9),
        -int(row.get("family_count") or row.get("family_frequency") or 0),
        -int(row.get("language_count") or row.get("language_frequency") or 0),
        -int(row.get("graph_degree") or row.get("degree") or 0),
        int(row["concepticon_id"]),
    )


def select_probes(snapshot: dict, target: int, seed: int) -> list[dict]:
    """Select broad graph coverage, then fill by structural rank.

    Community coverage is allocated before within-community depth.  Seeded jitter
    changes which peripheral probes participate while preserving structural support.
    """
    rows = list(snapshot["concepts"])
    if target >= len(rows):
        return sorted(rows, key=_score)
    communities: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        communities[str(row.get("community_id") or f"isolated:{row['concepticon_id']}")].append(row)
    for cid in communities:
        communities[cid].sort(key=_score)

    chosen: list[dict] = []
    # One evidence-weighted anchor per community when capacity permits.
    # Structural rank supplies the prior; seeded jitter samples among nearby members.
    anchors = []
    for group in communities.values():
        candidate = min(
            group,
            key=lambda r: (
                int(r.get("network_rank") or 10**9) * (0.72 + 0.56 * _stable_float("community-anchor", seed, r["concepticon_id"])),
                int(r["concepticon_id"]),
            ),
        )
        anchors.append(candidate)
    anchors.sort(key=lambda r: (int(r.get("network_rank") or 10**9), _stable_float("anchor-order", seed, r["concepticon_id"])))
    chosen.extend(anchors[:target])
    chosen_ids = {r["concepticon_id"] for r in chosen}
    if len(chosen) < target:
        remaining = [r for r in rows if r["concepticon_id"] not in chosen_ids]
        remaining.sort(key=lambda r: (
            int(r.get("network_rank") or 10**9) * (0.78 + 0.44 * _stable_float("probe", seed, r["concepticon_id"])),
            int(r["concepticon_id"]),
        ))
        chosen.extend(remaining[: target - len(chosen)])
    return sorted(chosen, key=_score)


def _edge_map(snapshot: dict) -> dict[frozenset[str], dict]:
    return {
        frozenset((str(e["source_concepticon_id"]), str(e["target_concepticon_id"]))): e
        for e in snapshot.get("colexification_edges", [])
    }


def _edge_rows(evidence) -> list[dict]:
    if isinstance(evidence, dict):
        rows = evidence.get("colexification_edges", evidence.get("edges", []))
        if isinstance(rows, dict):
            rows = list(rows.values())
        return list(rows)
    return list(evidence)


def replay_membership(record: dict, evidence) -> bool:
    """Validate and replay a lexical membership threshold decision."""
    required = {"algorithm", "evidence_edge_ids", "seed", "draw", "threshold", "accepted"}
    missing = required - set(record)
    if missing:
        raise ValueError(f"membership record is missing {sorted(missing)}")
    if record["algorithm"] != MEMBERSHIP_ALGORITHM:
        raise ValueError(f"unsupported membership algorithm {record['algorithm']!r}")
    available = {str(row["edge_id"]) for row in _edge_rows(evidence) if row.get("edge_id") is not None}
    unknown = set(map(str, record["evidence_edge_ids"])) - available
    if unknown:
        raise ValueError(f"membership record names unknown evidence edges: {sorted(unknown)}")
    replayed = float(record["draw"]) <= float(record["threshold"])
    if replayed is not bool(record["accepted"]):
        raise ValueError("membership record's accepted value does not match its draw and threshold")
    return replayed


def _membership_record(*, seed: int, evidence_edge_ids: list[str], draw: float = 0.0, threshold: float = 0.0) -> dict:
    return {
        "algorithm": MEMBERSHIP_ALGORITHM,
        "evidence_edge_ids": sorted(set(map(str, evidence_edge_ids))),
        "seed": seed,
        "draw": draw,
        "threshold": threshold,
        "accepted": draw <= threshold,
    }


def _supporting_edge_ids(cid: str, direct: dict, preferred: list[dict] | None = None) -> list[str]:
    rows = preferred or [edge for pair, edge in direct.items() if cid in pair]
    return [str(edge["edge_id"]) for edge in rows if edge.get("edge_id") is not None]


def _chunk_size(rng: random.Random, group_size: int) -> int:
    if group_size <= 1:
        return 1
    # Singleton lexicalizations remain possible; multi-probe regions are common.
    return rng.choices([1, 2, 3, 4], weights=[0.28, 0.42, 0.22, 0.08], k=1)[0]


def generate_semantic_regions(snapshot: dict, target: int, seed: int) -> tuple[list[dict], list[dict]]:
    """Generate Losica lexical regions from graph topology before forms exist."""
    selected = select_probes(snapshot, target, seed)
    selected_ids = {str(r["concepticon_id"]) for r in selected}
    by_id = {str(r["concepticon_id"]): r for r in selected}
    direct = _edge_map(snapshot)
    by_community: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        by_community[str(row.get("community_id") or f"isolated:{row['concepticon_id']}")].append(str(row["concepticon_id"]))

    regions: list[dict] = []
    decisions: list[dict] = []
    rng = random.Random(seed ^ 0x53454D52)
    for community_id in sorted(by_community, key=lambda x: (x.startswith("isolated:"), int(x.split(":")[-1]) if x.split(":")[-1].isdigit() else x)):
        members = by_community[community_id]
        members.sort(key=lambda cid: _score(by_id[cid]))
        # Direct colexification edges pull endpoints together before the remaining
        # community is partitioned.
        unused = set(members)
        ordered_pairs = []
        for pair, edge in direct.items():
            endpoints = list(pair)
            if len(endpoints) == 2 and all(x in unused and x in selected_ids for x in endpoints):
                a, b = endpoints
                if str(by_id[a].get("community_id")) == community_id and str(by_id[b].get("community_id")) == community_id:
                    ordered_pairs.append((-(int(edge.get("family_count") or 0)), -(int(edge.get("language_count") or 0)), min(map(int, endpoints)), max(map(int, endpoints)), edge))
        for _, _, _, _, edge in sorted(ordered_pairs):
            a, b = str(edge["source_concepticon_id"]), str(edge["target_concepticon_id"])
            if a in unused and b in unused:
                rid = meaning_region_id(f"{len(regions)+1:04d}")
                regions.append(_region_record(rid, community_id, [a, b], by_id, seed, direct))
                unused.remove(a); unused.remove(b)
        rest = [cid for cid in members if cid in unused]
        while rest:
            size = min(_chunk_size(rng, len(rest)), len(rest))
            chunk = rest[:size]
            rest = rest[size:]
            rid = meaning_region_id(f"{len(regions)+1:04d}")
            regions.append(_region_record(rid, community_id, chunk, by_id, seed, direct))

    # High-connectivity probes can participate in a second lexical region in the
    # same community, creating lexical overlap rather than a partition-only system.
    overlap_count = 0
    by_probe: dict[str, list[dict]] = defaultdict(list)
    for region in regions:
        for anchor in region["anchors"]:
            by_probe[anchor["concepticon_id"]].append(region)
    community_sizes = {cid: len(rows) for cid, rows in by_community.items()}
    candidates = sorted(selected, key=lambda r: (_score(r), int(r["concepticon_id"])))
    for row in candidates:
        cid = str(row["concepticon_id"])
        community_id = str(row.get("community_id") or f"isolated:{cid}")
        draw = _stable_float("overlap", seed, cid)
        if community_sizes.get(community_id, 1) < 3 or draw > 0.14:
            continue
        other = next((r for r in regions if r["community_id"] == community_id and all(a["concepticon_id"] != cid for a in r["anchors"])), None)
        if other is None:
            continue
        record = _membership_record(seed=seed, evidence_edge_ids=_supporting_edge_ids(cid, direct), draw=draw, threshold=0.14)
        other["anchors"].append(_anchor(
            row,
            membership=round(0.35 + 0.35 * _stable_float("weight", seed, cid, other["region_id"]), 6),
            membership_record=record,
        ))
        overlap_count += 1

    for region in regions:
        region["anchors"].sort(key=lambda a: (-a["membership"], int(a["concepticon_id"])))
        region["prototype_probe_id"] = region["anchors"][0]["probe_id"]
        region["semantic_mode"], region["frame_id"] = _semantic_mode(region, seed)
    _ensure_grammar_coverage(regions, seed)
    decisions.append({
        "feature": "lexical_semantic_regions",
        "value": {"region_count": len(regions), "probe_count": len(selected), "overlap_links": overlap_count},
        "source": snapshot.get("colexification_prior", {}).get("source", "structural semantic graph"),
        "source_ids": [str(r["concepticon_id"]) for r in selected],
        "sampling_method": "community-stratified probe selection, supported-edge binding, seeded within-community region generation, connectivity-conditioned overlap",
        "seed": seed,
        "evidence_kind": "cross_linguistic_structural_evidence",
        "inference_kind": "generated_semantic_partition",
        "choice_kind": "generated_choice",
    })
    return regions, decisions


def _anchor(row: dict, membership: float = 1.0, membership_record: dict | None = None) -> dict:
    object_id = str(row["concepticon_id"])
    return {
        "concepticon_id": object_id,
        "links": [concepticon_link(object_id)],
        "probe_id": f"c:{row['concepticon_id']}",
        "membership": membership,
        "membership_record": membership_record,
        "structural_evidence": {
            k: row[k] for k in (
                "network_rank", "community_id", "graph_degree", "weighted_family_degree",
                "weighted_language_degree", "family_frequency", "language_frequency"
            ) if k in row
        },
    }


def _region_record(rid: str, community_id: str, members: list[str], by_id: dict[str, dict], seed: int, direct: dict) -> dict:
    traced = []
    for i, a in enumerate(members):
        for b in members[i+1:]:
            edge = direct.get(frozenset((a, b)))
            if edge:
                traced.append(edge)
    anchors = []
    for index, cid in enumerate(members):
        row = by_id[cid]
        degree = int(row.get("graph_degree") or row.get("degree") or 0)
        weight = 1.0 if index == 0 else round(0.58 + min(0.35, degree / 30.0) + 0.05 * _stable_float("member", seed, rid, cid), 6)
        preferred = [edge for edge in traced if cid in {str(edge["source_concepticon_id"]), str(edge["target_concepticon_id"])}]
        record = _membership_record(seed=seed, evidence_edge_ids=_supporting_edge_ids(cid, direct, preferred or None))
        anchors.append(_anchor(row, min(weight, 0.96), record))
    return {
        "region_id": rid,
        "community_id": community_id,
        "anchors": anchors,
        "direct_edge_evidence": traced,
    }


def _semantic_mode(region: dict, seed: int) -> tuple[str, str | None]:
    """Create Losica's own lexical-semantic construal for a region.

    The mode is internal generated semantics. External probes locate the region but
    do not dictate its noun/verb/property status.
    """
    u = _stable_float("mode", seed, region["region_id"], region["community_id"])
    if u < 0.46:
        return "entity", None
    if u < 0.66:
        return "state", None
    frames = ["f:theme1", "f:agent1", "f:patient2", "f:transfer3", "f:content2"]
    weights = [0.24, 0.08, 0.46, 0.10, 0.12]
    rng = random.Random(int(_stable_float("frame", seed, region["region_id"]) * 2**53))
    return "event", rng.choices(frames, weights=weights, k=1)[0]


def _ensure_grammar_coverage(regions: list[dict], seed: int) -> None:
    """Ensure the generated lexicon can instantiate the grammar's core event schemas.

    Coverage is assigned by internal region IDs.  External probe anchors play no role
    in selecting these grammatical construals.
    """
    order = sorted(regions, key=lambda r: (_stable_float("coverage", seed, r["region_id"]), r["region_id"]))
    frames = ["f:theme1", "f:patient2", "f:transfer3", "f:content2"]
    for region, frame in zip(order[:4], frames):
        region["semantic_mode"] = "event"
        region["frame_id"] = frame
    for region in order[4:9]:
        region["semantic_mode"] = "entity"
        region["frame_id"] = None
    if len(order) > 9:
        order[9]["semantic_mode"] = "state"
        order[9]["frame_id"] = None


def region_class(region: dict) -> str:
    return {"entity": "noun", "state": "property", "event": "verb"}[region["semantic_mode"]]
