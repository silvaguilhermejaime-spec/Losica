#!/usr/bin/env python3
"""Build a Losica media manifest using one deterministic EgoCom view per segment."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


def build_manifest(video_info: Path, media_root: Path, output: Path) -> dict:
    with video_info.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    selected = {}
    for row in rows:
        conversation_id = row["conversation_id"]
        rank = (int(row["video_speaker_id"]), int(row["video_id"]))
        if conversation_id not in selected or rank < selected[conversation_id][0]:
            selected[conversation_id] = (rank, row)

    by_stem: dict[str, list[Path]] = {}
    for path in media_root.rglob("*"):
        if path.is_file() and path.suffix.casefold() == ".mp4":
            by_stem.setdefault(path.stem, []).append(path.resolve())

    recordings = []
    for conversation_id, (_, row) in sorted(selected.items()):
        candidates = by_stem.get(row["video_name"], [])
        if len(candidates) != 1:
            raise ValueError(
                f"expected one MP4 for {row['video_name']!r}; found {len(candidates)} under {media_root}"
            )
        media_path = candidates[0]
        recordings.append({
            "recording_id": row["video_name"],
            "source_id": "egocom",
            "source_recording_id": conversation_id,
            "media_type": "video",
            "path": os.path.relpath(media_path, output.parent.resolve()),
        })
    if not recordings:
        raise ValueError("video_info contained no recordings")
    return {"schema": "losica-real-media-manifest/1", "recordings": recordings}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-info", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args.video_info.resolve(), args.media_root.resolve(), args.out.resolve())
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "recordings": len(manifest["recordings"]), "out": str(args.out)}))


if __name__ == "__main__":
    main()
