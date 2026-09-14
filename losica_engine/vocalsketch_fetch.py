from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

BASE = "https://raw.githubusercontent.com/interactiveaudiolab/VocalSketchDataSet/refs/heads/master"


def fetch_bytes(url: str) -> bytes:
    with urlopen(url) as r:
        return r.read()


def _download(url: str, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return True
    try:
        payload = fetch_bytes(url)
    except HTTPError as exc:
        if exc.code == 404:
            return False
        raise
    path.write_bytes(payload)
    return True


def _eligible_rows(raw: bytes):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    selected = []
    for r in rows:
        if r.get("stimulus_type", "").strip().lower() != "sound recording":
            continue
        if r.get("included", "").strip().lower() != "true":
            continue
        if r.get("draft", "").strip().lower() == "true" or r.get("training", "").strip().lower() == "true":
            continue
        if r.get("sound_recording", "").strip() and r.get("filename", "").strip():
            selected.append(r)
    return selected


def fetch_subset(out_dir: str | Path, *, max_referents: int = 40, imitations_per_referent: int = 8,
                 include_set2: bool = True):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    specs = [
        ("vocal_imitations.csv", "vocal_imitations/included", "set1"),
    ]
    if include_set2:
        specs.append(("vocal_imitaitons_set2.csv", "vocal_imitations_set2/included", "set2"))

    all_rows = []
    for csv_name, imitation_dir, source_set in specs:
        raw = fetch_bytes(BASE + "/" + csv_name)
        (out / csv_name).write_bytes(raw)
        for row in _eligible_rows(raw):
            all_rows.append((row, imitation_dir, source_set))

    by_ref = {}
    for row, imitation_dir, source_set in all_rows:
        ref = row["sound_recording"].strip()
        by_ref.setdefault(ref, []).append((row, imitation_dir, source_set))

    selected_refs = sorted(by_ref)
    if max_referents > 0:
        selected_refs = selected_refs[:max_referents]

    manifest = []
    unavailable_referents = []
    downloaded_refs = 0
    for ref in selected_refs:
        ref_url = BASE + "/sound_recordings/" + quote(ref)
        if not _download(ref_url, out / "sound_recordings" / ref):
            unavailable_referents.append(ref)
            continue
        downloaded_refs += 1
        rows = sorted(by_ref[ref], key=lambda x: (x[2], x[0]["id"]))
        if imitations_per_referent > 0:
            rows = rows[:imitations_per_referent]
        for row, imitation_dir, source_set in rows:
            im = row["filename"].strip()
            im_url = BASE + "/" + imitation_dir + "/" + quote(im)
            local = out / imitation_dir / im
            if _download(im_url, local):
                manifest.append({
                    "source_row_id": row["id"],
                    "source_set": source_set,
                    "referent": ref,
                    "imitation": im,
                })

    summary = {
        "schema": "losica-vocalsketch-fetch/1",
        "dataset": "VocalSketch",
        "source": "https://github.com/interactiveaudiolab/VocalSketchDataSet",
        "requested_referent_count": len(selected_refs),
        "downloaded_referent_count": downloaded_refs,
        "pair_count": len(manifest),
        "unavailable_referents": unavailable_referents,
        "pairs": manifest,
    }
    (out / "FETCHED.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-referents", type=int, default=40, help="0 selects every downloadable referent")
    ap.add_argument("--imitations-per-referent", type=int, default=8, help="0 selects every imitation")
    ap.add_argument("--set1-only", action="store_true")
    args = ap.parse_args(argv)
    result = fetch_subset(args.out, max_referents=args.max_referents,
                          imitations_per_referent=args.imitations_per_referent,
                          include_set2=not args.set1_only)
    print(json.dumps({k: result[k] for k in ["downloaded_referent_count", "pair_count"]} | {"out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
