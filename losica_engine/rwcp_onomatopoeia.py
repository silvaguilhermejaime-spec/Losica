from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SCHEMA = "losica-rwcp-onomatopoeia-index/1"


def build_index(root: str | Path) -> dict:
    root = Path(root)
    records = []
    for ono in sorted(root.rglob("*.ono")):
        rel = ono.relative_to(root).as_posix()
        sound_id = ono.stem
        with ono.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            for line_no, row in enumerate(reader, 1):
                if len(row) < 4:
                    continue
                worker_id, item_id, form, confidence = row[:4]
                records.append({
                    "sound_id": sound_id,
                    "source_file": rel,
                    "line": line_no,
                    "worker_id": worker_id,
                    "item_id": item_id,
                    "form": form,
                    "self_confidence": confidence,
                    "population_observation": True,
                })
    judgments = []
    candidates = [p for p in root.rglob("*") if p.is_file() and "accept" in p.name.lower() and p.suffix.lower() in {".csv", ".tsv", ".txt"}]
    for source in sorted(candidates):
        with source.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            sample = handle.readline(); handle.seek(0)
            delimiter = "\t" if "\t" in sample else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            for line_no, row in enumerate(reader, 2):
                normalized = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
                judgments.append({
                    "judgment_id": normalized.get("id") or f"{source.relative_to(root).as_posix()}:{line_no}",
                    "sound_id": normalized.get("sound_id") or normalized.get("sound") or normalized.get("item_id"),
                    "form": normalized.get("form") or normalized.get("onomatopoeia") or normalized.get("response"),
                    "worker_id": normalized.get("worker_id") or normalized.get("worker") or normalized.get("participant_id"),
                    "accepted": normalized.get("accepted") or normalized.get("acceptance") or normalized.get("judgment"),
                    "source_file": source.relative_to(root).as_posix(),
                })
    return {
        "schema": SCHEMA,
        "dataset_root": str(root),
        "record_count": len(records),
        "records": records,
        "acceptance_judgment_count": len(judgments),
        "acceptance_judgments": judgments,
        "provenance": {
            "dataset": "RWCP-SSD-Onomatopoeia",
            "repository": "https://github.com/KeisukeImoto/RWCPSSD_Onomatopoeia",
            "use_terms": "research/personal; upstream redistribution restrictions apply",
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    obj = build_index(args.root)
    Path(args.out).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": obj["record_count"], "out": args.out}, sort_keys=True))

if __name__ == "__main__":
    main()
