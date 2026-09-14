#!/usr/bin/env python3
"""Verify source identity, catalog shape, counts, and a transparent coverage audit."""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re


TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
AUDIT_FORMS = {
    "bread": {"bread"},
    "purchase": {"buy", "buys", "buying", "bought"},
    "same_day": {"today"},
    "inability": {"cannot", "can't", "couldn't", "unable"},
    "failed_result": {"fail", "fails", "failed", "failing"},
    "stated_intention": {"intend", "intends", "intended", "intending", "intention", "intentions", "want", "wants", "wanted", "wanting", "plan", "plans", "planned", "planning"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repos", type=Path)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if sha256(args.catalog) != lock["catalog"]["sha256"]:
        raise SystemExit("catalog digest differs from inputs.lock.json")
    verified_source_files = 0
    if args.repos is not None:
        included = set(lock["catalog"]["included_sources"])
        for source in lock["sources"]:
            if source["source_id"] not in included:
                continue
            directory = source.get("local_repository_dir")
            for relative, expected_digest in source.get("file_sha256", {}).items():
                if not directory:
                    raise SystemExit(f"{source['source_id']} has hashes without local_repository_dir")
                path = args.repos / directory / relative
                if sha256(path) != expected_digest:
                    raise SystemExit(f"source digest mismatch: {path}")
                verified_source_files += 1
    counts = Counter()
    seen = set()
    audit = {name: Counter() for name in AUDIT_FORMS}
    with args.catalog.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            required = {"schema", "source_id", "external_id", "expression", "expression_origin", "evidence_role", "observation_ref", "source_file"}
            if not required <= set(row) or row["schema"] != "losica-external-source-record/1":
                raise SystemExit(f"invalid record at line {line_number}")
            if not row["expression"].strip():
                raise SystemExit(f"empty expression at line {line_number}")
            identity = (row["source_id"], row["external_id"])
            if identity in seen:
                raise SystemExit(f"duplicate identity at line {line_number}: {identity}")
            seen.add(identity)
            counts[row["source_id"]] += 1
            tokens = {token.casefold().replace("’", "'") for token in TOKEN.findall(row["expression"])}
            for name, forms in AUDIT_FORMS.items():
                if tokens & forms:
                    audit[name][row["source_id"]] += 1
    expected = lock["catalog"]["record_count"]
    if sum(counts.values()) != expected:
        raise SystemExit(f"expected {expected} records; found {sum(counts.values())}")
    report = {
        "schema": "losica-source-catalog-verification/1",
        "catalog_sha256": sha256(args.catalog),
        "record_counts": dict(sorted(counts.items())),
        "total_record_count": sum(counts.values()),
        "verified_source_file_count": verified_source_files,
        "target_sentence_audit": {
            name: {
                "accepted_token_forms": sorted(AUDIT_FORMS[name]),
                "measurement_rule": "number of catalog records containing at least one exact case-folded token from accepted_token_forms",
                "record_counts_by_source": dict(sorted(values.items())),
                "record_count": sum(values.values()),
            }
            for name, values in audit.items()
        },
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verified": True, "records": sum(counts.values()), "sha256": report["catalog_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
