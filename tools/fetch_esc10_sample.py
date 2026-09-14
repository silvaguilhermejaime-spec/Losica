#!/usr/bin/env python3
"""Fetch a pinned, attributed real-audio sample from the official ESC-50 repo."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen


REVISION = "33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6"
BASE = f"https://raw.githubusercontent.com/karolpiczak/ESC-50/{REVISION}"
OPENCV_REVISION = "cd3aa54bc773a90cb57d92192659083a70135d73"
OPENCV_VIDEO = f"https://raw.githubusercontent.com/opencv/opencv/{OPENCV_REVISION}/samples/data/vtest.avi"


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Losica/0.29 real-media importer"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/esc10-real"))
    parser.add_argument("--clips-per-category", type=int, default=2)
    parser.add_argument("--include-video", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.clips_per_category <= 40:
        parser.error("--clips-per-category must be between 1 and 40")
    root = args.out.resolve()
    media = root / "media"
    media.mkdir(parents=True, exist_ok=True)
    metadata_bytes = download(f"{BASE}/meta/esc50.csv")
    (root / "esc50.csv").write_bytes(metadata_bytes)
    rows = list(csv.DictReader(io.StringIO(metadata_bytes.decode("utf-8"))))
    selected, counts = [], {}
    for row in rows:
        if row["esc10"] != "True":
            continue
        category = row["category"]
        if counts.get(category, 0) >= args.clips_per_category:
            continue
        counts[category] = counts.get(category, 0) + 1
        selected.append(row)
    urls = [f"{BASE}/audio/{row['filename']}" for row in selected]
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(download, urls))
    recordings = []
    for row, payload in zip(selected, payloads):
        name = row["filename"]
        target = media / name
        target.write_bytes(payload)
        recordings.append({
            "recording_id": f"esc50:{row['src_file']}:{row['take']}",
            "path": f"media/{name}", "media_type": "audio",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "source_id": "esc10", "source_recording_id": row["src_file"],
            "annotations": [{
                "external_id": f"esc10:{row['src_file']}:{row['take']}",
                "expression": row["category"],
            }],
        })
    if args.include_video:
        payload = download(OPENCV_VIDEO)
        name = "opencv-vtest.avi"
        (media / name).write_bytes(payload)
        recordings.append({
            "recording_id": "opencv:vtest", "path": f"media/{name}",
            "media_type": "video", "sha256": hashlib.sha256(payload).hexdigest(),
            "source_id": "opencv-sample", "source_recording_id": "vtest",
            "annotations": [],
        })
    manifest = {
        "schema": "losica-real-media-manifest/1",
        "sources": [{
                "name": "ESC-10 subset of ESC-50", "revision": REVISION,
                "repository": "https://github.com/karolpiczak/ESC-50",
                "license": "CC BY 3.0; per-clip attribution is in the upstream LICENSE",
            }] + ([{
                "name": "OpenCV vtest sample video", "revision": OPENCV_REVISION,
                "repository": "https://github.com/opencv/opencv",
                "license": "Apache-2.0 repository sample",
            }] if args.include_video else []),
        "recordings": recordings,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "SOURCE.md").write_text(
        "# ESC-10 real-audio sample\n\n"
        f"Fetched from the official ESC-50 repository at `{REVISION}`. "
        "ESC-10 is CC BY 3.0; see the upstream LICENSE for per-clip attribution.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS", "recordings": len(recordings), "categories": counts,
        "video_recordings": int(args.include_video),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
