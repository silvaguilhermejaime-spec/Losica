#!/usr/bin/env python3
"""Normalize inspected, externally authored annotations without inventing labels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def emit(handle, row: dict) -> None:
    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def hms(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def epic_kitchens(root: Path, handle) -> int:
    count = 0
    for split in ("train", "validation"):
        path = root / "epic" / f"EPIC_100_{split}.csv"
        with path.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                emit(handle, {
                    "schema": "losica-external-source-record/1",
                    "source_id": "epic-kitchens-100",
                    "external_id": row["narration_id"],
                    "expression": row["narration"],
                    "expression_origin": "participant_narration",
                    "evidence_role": "observed_action_description",
                    "observation_ref": {
                        "recording_id": row["video_id"],
                        "start_seconds": hms(row["start_timestamp"]),
                        "end_seconds": hms(row["stop_timestamp"]),
                        "start_frame": int(row["start_frame"]),
                        "end_frame": int(row["stop_frame"]),
                    },
                    "source_file": str(path.relative_to(root)),
                })
                count += 1
    return count


def epic_sounds(root: Path, handle) -> int:
    count = 0
    for name in ("EPIC_Sounds_train.csv", "EPIC_Sounds_validation.csv", "sound_events_not_categorised.csv"):
        path = root / "epic_sounds" / name
        with path.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                if not row["description"].strip():
                    continue
                emit(handle, {
                    "schema": "losica-external-source-record/1",
                    "source_id": "epic-sounds",
                    "external_id": row["annotation_id"],
                    "expression": row["description"],
                    "expression_origin": "human_audio_description",
                    "evidence_role": "observed_sound_description",
                    "observation_ref": {
                        "recording_id": row["video_id"],
                        "start_seconds": hms(row["start_timestamp"]),
                        "end_seconds": hms(row["stop_timestamp"]),
                        "start_sample_24khz": int(row["start_sample"]),
                        "end_sample_24khz": int(row["stop_sample"]),
                    },
                    "source_file": str(path.relative_to(root)),
                })
                count += 1
    return count


def activitynet_entities(root: Path, handle) -> int:
    path = root / "activitynet_entities" / "data" / "anet_entities_cleaned_class_thresh50_trainval.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for video_id, video in sorted(data["annotations"].items()):
        for segment_id, segment in sorted(video["segments"].items(), key=lambda item: int(item[0])):
            emit(handle, {
                "schema": "losica-external-source-record/1",
                "source_id": "activitynet-entities",
                "external_id": f"{video_id}:{segment_id}",
                "expression": " ".join(segment["tokens"]),
                "expression_origin": "human_video_description",
                "evidence_role": "observed_video_description_with_grounded_phrases",
                "observation_ref": {
                    "recording_id": video_id,
                    "start_seconds": segment["timestamps"][0],
                    "end_seconds": segment["timestamps"][1],
                    "grounded_token_indexes": segment["process_idx"],
                    "sampled_frame_indexes": segment["frame_ind"],
                    "bounding_boxes_xyxy": segment["process_bnd_box"],
                },
                "source_file": str(path.relative_to(root)),
            })
            count += 1
    return count


def talk2car(root: Path, handle) -> int:
    count = 0
    for split in ("train", "val"):
        path = root / "talk2car" / "data" / "commands" / f"{split}_commands.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data["commands"]:
            emit(handle, {
                "schema": "losica-external-source-record/1",
                "source_id": "talk2car",
                "external_id": row["command_token"],
                "expression": row["command"],
                "expression_origin": "human_command",
                "evidence_role": "intended_action_and_referred_object",
                "observation_ref": {
                    "recording_id": row["scene_token"],
                    "sample_token": row["sample_token"],
                    "object_box_token": row["box_token"],
                    "bounding_box_xywh": row["2d_box"],
                },
                "source_file": str(path.relative_to(root)),
            })
            count += 1
    return count


def vlep(root: Path, handle) -> int:
    count = 0
    for split in ("train", "dev", "test"):
        path = root / "vlep" / "data" / f"vlep_{split}_release.jsonl"
        with path.open(encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                for candidate_index, expression in enumerate(row["events"]):
                    emit(handle, {
                        "schema": "losica-external-source-record/1",
                        "source_id": "vlep",
                        "external_id": f"{row['example_id']}:{candidate_index}",
                        "expression": expression,
                        "expression_origin": "human_future_event_candidate",
                        "evidence_role": "future_hypothesis",
                        "accepted_candidate": row.get("answer") == candidate_index if "answer" in row else None,
                        "observation_ref": {
                            "recording_id": row["vid_name"],
                            "premise_start_seconds": row["ts"][0],
                            "premise_end_seconds": row["ts"][1],
                        },
                        "source_file": str(path.relative_to(root)),
                    })
                    count += 1
    return count


def audiocaps(root: Path, handle) -> int:
    path = root / "aac_datasets" / "data" / "audiocaps" / "train_v2.csv"
    count = 0
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            emit(handle, {
                "schema": "losica-external-source-record/1",
                "source_id": "audiocaps",
                "external_id": row["audiocap_id"],
                "expression": row["caption"],
                "expression_origin": "human_audio_caption",
                "evidence_role": "observed_sound_description",
                "observation_ref": {
                    "recording_id": row["youtube_id"],
                    "start_seconds": float(row["start_time"]),
                    "end_seconds": float(row["start_time"]) + 10.0,
                },
                "source_file": str(path.relative_to(root)),
            })
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    with args.out.open("w", encoding="utf-8") as handle:
        counts["epic-kitchens-100"] = epic_kitchens(args.repos, handle)
        counts["epic-sounds"] = epic_sounds(args.repos, handle)
        counts["activitynet-entities"] = activitynet_entities(args.repos, handle)
        counts["talk2car"] = talk2car(args.repos, handle)
        counts["audiocaps"] = audiocaps(args.repos, handle)
    summary = {
        "schema": "losica-external-source-catalog-summary/1",
        "record_counts": counts,
        "total_record_count": sum(counts.values()),
        "catalog_sha256": digest(args.out),
        "rule": "Expressions are copied from inspected source annotations. No expression is written or paraphrased by Losica or by this collector.",
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
