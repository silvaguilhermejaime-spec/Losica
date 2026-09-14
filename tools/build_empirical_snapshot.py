#!/usr/bin/env python3
"""Build Losica structural evidence from pinned cross-linguistic datasets."""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

csv.field_size_limit(64 * 1024 * 1024)

VERSIONS = {
    "Concepticon": {"version": "3.4.0", "commit": "918bc44e123952a6ab5733be36c2d463799c23b4"},
    "CLICS4": {"version": "1.0", "commit": "1ddece619d026d7fc11a4dcab3fa71ecd059efe7"},
    "Grambank": {"version": "1.0", "commit": "9e0f34194224204fa6a2058a2c12d43923e8715f"},
    "WALS": {"version": "2020.4", "commit": "3a9efd69074e1ced1da69e31b9aebfd55006eb70"},
    "PHOIBLE": {"version": "2.0", "commit": "862bec9af5db42e3c9ceedeaa378bf4c6fa0ec8b"},
}


def rows(path: Path, delimiter=","):
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter=delimiter)


def zip_rows(path: Path):
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))


def _n(row: dict, key: str) -> int:
    try:
        return int(row.get(key) or 0)
    except ValueError:
        return 0


def concept_snapshot(clics_root: Path, limit: int = 1000) -> list[dict]:
    """Select semantic probes from CLICS numeric coverage and stable IDs."""
    records = []
    for row in zip_rows(clics_root / "cldf/concepts.csv.zip"):
        cid = row.get("Concepticon_ID", "").strip()
        if not cid:
            continue
        records.append({
            "concepticon_id": cid,
            "form_count": _n(row, "Form_Count"),
            "variety_count": _n(row, "Variety_Count"),
            "language_count": _n(row, "Language_Count"),
            "family_count": _n(row, "Family_Count"),
            "community_id": row.get("Community") or None,
            "centrality_id": row.get("CentralConcept") or None,
        })
    records.sort(key=lambda r: (-r["family_count"], -r["language_count"], -r["variety_count"], -r["form_count"], int(r["concepticon_id"])))
    for rank, row in enumerate(records[:limit], 1):
        row["network_rank"] = rank
    return records[:limit]


WALS_STRUCTURE_CODES = {
    "81A-1": "SOV", "81A-2": "SVO", "81A-3": "VSO", "81A-4": "VOS", "81A-5": "OVS", "81A-6": "OSV", "81A-7": "ND",
    "85A-1": "POST", "85A-2": "PRE", "85A-3": "IN", "85A-4": "ND", "85A-5": "CASE",
    "86A-1": "G-N", "86A-2": "N-G", "86A-3": "ND",
    "87A-1": "A-N", "87A-2": "N-A", "87A-3": "ND", "87A-4": "PRED",
    "89A-1": "NUM-N", "89A-2": "N-NUM", "89A-3": "ND", "89A-4": "V-NUM",
}


def wals_joint(root: Path) -> tuple[list[dict], dict]:
    features = ["81A", "85A", "86A", "87A", "89A"]
    langs = {r["ID"]: r for r in rows(root / "cldf/languages.csv")}
    values, value_ids = defaultdict(dict), defaultdict(dict)
    for row in rows(root / "cldf/values.csv"):
        fid, code = row["Parameter_ID"], row.get("Code_ID")
        if fid in features and code in WALS_STRUCTURE_CODES:
            values[row["Language_ID"]][fid] = WALS_STRUCTURE_CODES[code]
            value_ids[row["Language_ID"]][fid] = row["ID"]
    grouped = defaultdict(list)
    for lid, vals in values.items():
        if all(fid in vals for fid in features):
            grouped[tuple(vals[fid] for fid in features)].append(lid)
    profiles = []
    for i, (key, lids) in enumerate(sorted(grouped.items(), key=lambda x: (-len(x[1]), x[0]))[:12], 1):
        sample = lids[:24]
        meta = [langs[x] for x in sample]
        profiles.append({
            "id": f"WALS-JOINT-{i:02d}", "weight": len(lids), "features": dict(zip(features, key)),
            "observation_ids": [value_ids[x][f] for x in sample for f in features], "language_ids": sample,
            "families": sorted({x.get("Family", "") for x in meta if x.get("Family")}),
            "macroareas": sorted({x.get("Macroarea", "") for x in meta if x.get("Macroarea")}), "observation_count": len(lids),
        })
    return profiles, {"features": features, "complete_joint_observations": sum(map(len, grouped.values()))}


def wals_audits(root: Path) -> dict:
    wanted = {"20A", "21A", "22A", "23A", "24A", "25A", "49A", "101A", "102A"}
    counts, observations = defaultdict(Counter), defaultdict(list)
    for row in rows(root / "cldf/values.csv"):
        if row["Parameter_ID"] in wanted and row.get("Code_ID"):
            counts[row["Parameter_ID"]][row["Code_ID"]] += 1
            if len(observations[row["Parameter_ID"]]) < 24:
                observations[row["Parameter_ID"]].append(row["ID"])
    return {fid: {"counts": dict(counts[fid]), "observation_ids": observations[fid]} for fid in sorted(wanted)}


def grambank_records(root: Path) -> dict:
    wanted = ["GB024", "GB065", "GB066", "GB071", "GB072", "GB079", "GB080", "GB083", "GB084", "GB086", "GB089", "GB090", "GB091", "GB092", "GB093", "GB094", "GB095", "GB096", "GB103", "GB104", "GB105", "GB107", "GB108", "GB109", "GB110", "GB111", "GB117", "GB118", "GB119", "GB120", "GB121", "GB122", "GB123", "GB124", "GB130", "GB131", "GB132", "GB133", "GB134", "GB135", "GB136", "GB137", "GB138", "GB139", "GB140", "GB146", "GB147", "GB148", "GB149", "GB150", "GB151", "GB152", "GB155", "GB156", "GB165", "GB166", "GB167", "GB170", "GB171", "GB172", "GB177", "GB184", "GB185", "GB186", "GB192", "GB193", "GB196", "GB197", "GB198", "GB203", "GB204", "GB205", "GB257", "GB260", "GB262", "GB263", "GB264", "GB285", "GB286", "GB291", "GB297", "GB298", "GB299", "GB300", "GB301", "GB302", "GB303", "GB304", "GB305", "GB309", "GB312", "GB313", "GB314", "GB315", "GB316", "GB317", "GB318", "GB319", "GB320", "GB321", "GB322", "GB323", "GB324", "GB325", "GB326", "GB327", "GB328", "GB329", "GB330", "GB331", "GB333", "GB334", "GB335", "GB336", "GB408", "GB409", "GB410", "GB415", "GB422", "GB430", "GB431"]
    wanted = set(wanted); counts, examples = defaultdict(Counter), defaultdict(list)
    for row in rows(root / "cldf/values.csv"):
        pid = row["Parameter_ID"]
        if pid in wanted:
            counts[pid][row["Value"]] += 1
            if len(examples[pid]) < 12:
                examples[pid].append(row["ID"])
    return {pid: {"counts": dict(counts[pid]), "observation_ids": examples[pid]} for pid in sorted(wanted)}


def phoible_audit(root: Path) -> dict:
    wanted = {"p", "t", "k", "kʼ", "m", "n", "l", "r", "i", "a", "u"}
    inventories, features = defaultdict(set), {}
    with (root / "data/phoible.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle); feature_names = reader.fieldnames[12:]
        for row in reader:
            inventories[row["InventoryID"]].add(row["Phoneme"])
            if row["Phoneme"] in wanted and row["Phoneme"] not in features:
                features[row["Phoneme"]] = {k: row[k] for k in feature_names}
    return {
        "inventory_count": len(inventories),
        "segment_inventory_counts": {s: sum(s in inv for inv in inventories.values()) for s in sorted(wanted)},
        "exact_inventory_count": sum(inv == wanted for inv in inventories.values()), "features": features,
    }


def clics_edges(root: Path, concept_ids: set[str], limit: int = 256) -> list[dict]:
    """Construct colexification edges from Language_ID, Parameter_ID and Form."""
    parameter_to_concepticon = {}
    for row in zip_rows(root / "cldf/concepts.csv.zip"):
        cid = row.get("Concepticon_ID", "").strip()
        if cid in concept_ids:
            parameter_to_concepticon[row["ID"]] = cid
    language_meta = {r["ID"]: r for r in rows(root / "cldf/languages.csv")}
    buckets = defaultdict(set)
    for row in zip_rows(root / "cldf/forms.csv.zip"):
        cid = parameter_to_concepticon.get(row["Parameter_ID"])
        form = (row.get("Form") or "").strip()
        if cid and form:
            buckets[(row["Language_ID"], form)].add(cid)
    evidence = defaultdict(lambda: {"forms": set(), "varieties": set(), "languages": set(), "families": set()})
    for (variety, form), cids in buckets.items():
        if len(cids) < 2:
            continue
        meta = language_meta.get(variety, {})
        language = meta.get("Glottocode") or variety
        family = meta.get("Family") or meta.get("Family_Name") or ""
        for a, b in combinations(sorted(cids, key=int), 2):
            rec = evidence[(a, b)]; rec["forms"].add((variety, form)); rec["varieties"].add(variety); rec["languages"].add(language)
            if family: rec["families"].add(family)
    out = []
    for (a, b), ev in evidence.items():
        if len(ev["languages"]) < 3:
            continue
        family_count = len(ev["families"])
        out.append({
            "edge_id": f"{a}-{b}", "source_concepticon_id": a, "target_concepticon_id": b,
            "form_count": len(ev["forms"]), "variety_count": len(ev["varieties"]), "language_count": len(ev["languages"]),
            "family_count": family_count, "family_weight": float(family_count),
        })
    out.sort(key=lambda r: (-r["family_count"], -r["language_count"], r["edge_id"]))
    return out[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grambank", type=Path, required=True); ap.add_argument("--wals", type=Path, required=True)
    ap.add_argument("--clics", type=Path, required=True); ap.add_argument("--phoible", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    concepts = concept_snapshot(args.clics)
    profiles, wals_meta = wals_joint(args.wals)
    ids = [r["concepticon_id"] for r in concepts]
    obj = {
        "schema": "losica-empirical-source/3", "versions": VERSIONS,
        "semantic_probe_registry": {
            "registry": "Concepticon", "version": VERSIONS["Concepticon"]["version"],
            "selection_basis": "CLICS numeric cross-linguistic coverage", "concepticon_ids": ids,
        },
        "probe_evidence": {r["concepticon_id"]: {k: v for k, v in r.items() if k != "concepticon_id"} for r in concepts},
        "colexification_prior": {"source": "CLICS4", "version": VERSIONS["CLICS4"]["version"], "role": "structural semantic-association evidence"},
        "colexification_edges": clics_edges(args.clics, set(ids), limit=4096),
        "wals_joint_profiles": profiles, "wals_metadata": wals_meta,
        "wals_feature_audits": wals_audits(args.wals), "grambank_parameters": grambank_records(args.grambank),
        "phoible": phoible_audit(args.phoible),
        "missing_data_policy": "Source-coded uncertainty remains explicit in feature-specific empirical summaries.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"concepts": len(concepts), "edges": len(obj["colexification_edges"]), "profiles": len(profiles), "grambank_parameters": len(obj["grambank_parameters"])}, sort_keys=True))


if __name__ == "__main__":
    main()
