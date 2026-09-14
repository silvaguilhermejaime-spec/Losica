from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

SCHEMA = "losica-paired-vocal-imitation-index/1"


def _bool(v: str) -> bool:
    return str(v).strip().lower() == "true"


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_vocalsketch_index(dataset_root: str | Path, *, verify_files: bool = True) -> dict:
    """Build paired reference/imitation records from the VocalSketch release layout.

    Selection corresponds to recordings participants actually heard before imitating:
    stimulus_type='sound recording', included=True, draft=False, training=False.
    """
    root = Path(dataset_root)
    csv_specs = [
        (root / "vocal_imitations.csv", root / "vocal_imitations" / "included", "set1"),
        (root / "vocal_imitaitons_set2.csv", root / "vocal_imitations_set2" / "included", "set2"),
        (root / "vocal_imitations_set2.csv", root / "vocal_imitations_set2" / "included", "set2"),
    ]
    selected = []
    used_csv = []
    seen_rows = set()
    for csv_path, imitation_dir, source_set in csv_specs:
        if not csv_path.exists() or csv_path.name in used_csv:
            continue
        used_csv.append(csv_path.name)
        for row in _read_csv(csv_path):
            row_id = row.get("id", "").strip()
            if not row_id or row_id in seen_rows:
                continue
            if row.get("stimulus_type", "").strip().lower() != "sound recording":
                continue
            if not _bool(row.get("included", "")) or _bool(row.get("draft", "")) or _bool(row.get("training", "")):
                continue
            ref_name = row.get("sound_recording", "").strip()
            im_name = row.get("filename", "").strip()
            if not ref_name or not im_name:
                continue
            ref_path = root / "sound_recordings" / ref_name
            im_path = imitation_dir / im_name
            if verify_files and (not ref_path.is_file() or not im_path.is_file()):
                continue
            seen_rows.add(row_id)
            rec = {
                "pair_id": f"vocalsketch:{row_id}",
                "referent_id": f"vocalsketch:recording:{row.get('sound_recording_id','').strip() or ref_name}",
                "referent_waveform": str(ref_path.relative_to(root)),
                "imitation_id": f"vocalsketch:imitation:{row_id}",
                "imitation_waveform": str(im_path.relative_to(root)),
                "speaker_id": f"vocalsketch:participant:{row.get('participant_id','').strip()}",
                "source_set": source_set,
                "source_row_id": row_id,
            }
            if verify_files:
                rec["referent_sha256"] = _sha256(ref_path)
                rec["imitation_sha256"] = _sha256(im_path)
            selected.append(rec)
    selected.sort(key=lambda r: (r["referent_id"], r["imitation_id"]))
    return {
        "schema": SCHEMA,
        "dataset": {
            "id": "VocalSketch",
            "citation": "Cartwright & Pardo 2015, doi:10.1145/2702123.2702387",
            "source": "https://github.com/interactiveaudiolab/VocalSketchDataSet",
            "dataset_root": str(root.resolve()),
            "metadata_files": used_csv,
        },
        "pairs": selected,
    }


def write_index(index: dict, out: str | Path):
    Path(out).write_text(json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--metadata-only", action="store_true", help="retain rows even when waveform files are absent")
    args = ap.parse_args(argv)
    index = build_vocalsketch_index(args.dataset_root, verify_files=not args.metadata_only)
    write_index(index, args.out)
    print(json.dumps({"pairs": len(index["pairs"]), "out": args.out}, sort_keys=True))


if __name__ == "__main__":
    main()
