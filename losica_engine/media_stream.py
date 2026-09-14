"""Project real audio and video into Losica's label-free causal stream."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import numpy as np
import soundfile as sf

from .causal_stream import validate_causal_stream


MANIFEST_SCHEMA = "losica-real-media-manifest/1"
REPORT_SCHEMA = "losica-real-media-import/1"
AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".aif", ".aiff"}


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _audio_windows(samples: np.ndarray, sample_rate: int, fps: float) -> list[np.ndarray]:
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    samples = np.asarray(samples, dtype=np.float64).reshape(-1)
    width = max(1, int(round(sample_rate / fps)))
    return [samples[start:start + width] for start in range(0, len(samples), width)]


def _audio_features(window: np.ndarray, sample_rate: int) -> list[float]:
    if window.size == 0:
        return [0.0] * 8
    window = np.nan_to_num(window.astype(np.float64), copy=False)
    rms = math.sqrt(float(np.mean(window * window)))
    zero_crossings = float(np.mean(np.signbit(window[1:]) != np.signbit(window[:-1]))) if window.size > 1 else 0.0
    spectrum = np.abs(np.fft.rfft(window * np.hanning(window.size))) ** 2
    frequencies = np.fft.rfftfreq(window.size, 1.0 / sample_rate)
    total = float(spectrum.sum())
    if total:
        centroid_hz = float(np.dot(frequencies, spectrum) / total)
        spread_hz = math.sqrt(float(np.dot((frequencies - centroid_hz) ** 2, spectrum) / total))
    else:
        centroid_hz = spread_hz = 0.0
    nyquist = sample_rate / 2.0
    epsilon = 1e-18
    flatness = float(np.exp(np.mean(np.log(spectrum + epsilon))) / (np.mean(spectrum) + epsilon))
    return [
        float(np.mean(window)), float(np.std(window)), rms,
        float(np.max(np.abs(window))), zero_crossings,
        centroid_hz / nyquist, spread_hz / nyquist, flatness,
    ]


def _visual_features(frame: np.ndarray, previous: np.ndarray | None) -> list[float]:
    value = frame.astype(np.float64) / 255.0
    dx = np.abs(np.diff(value, axis=1))
    dy = np.abs(np.diff(value, axis=0))
    motion = np.zeros_like(value) if previous is None else np.abs(value - previous.astype(np.float64) / 255.0)
    center = value[value.shape[0] // 4:3 * value.shape[0] // 4, value.shape[1] // 4:3 * value.shape[1] // 4]
    return [
        float(value.mean()), float(value.std()), float(dx.mean()), float(dy.mean()),
        float(motion.mean()), float(motion.std()),
        float(np.quantile(value, 0.25)), float(center.mean() - value.mean()),
    ]


def _ffmpeg_audio(path: Path, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
    command = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        return np.asarray([], dtype=np.float32), sample_rate
    return np.frombuffer(completed.stdout, dtype="<f4"), sample_rate


def _ffmpeg_video(path: Path, fps: float, size: int = 32) -> list[np.ndarray]:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for video ingestion")
    command = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path),
        "-an", "-vf", f"fps={fps},scale={size}:{size}:flags=area,format=gray",
        "-pix_fmt", "gray", "-f", "rawvideo", "-",
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    array = np.frombuffer(completed.stdout, dtype=np.uint8)
    frame_size = size * size
    if array.size % frame_size:
        raise ValueError(f"decoded video byte count is not divisible by {frame_size}")
    return [row.reshape(size, size) for row in array.reshape(-1, frame_size)]


def _recording_features(path: Path, media_type: str, fps: float) -> list[list[float]]:
    if media_type == "audio":
        samples, sample_rate = sf.read(path, always_2d=False)
        audio = [_audio_features(window, sample_rate) for window in _audio_windows(samples, sample_rate, fps)]
        return [row + [0.0] * 8 for row in audio]
    if media_type != "video":
        raise ValueError(f"unsupported media_type {media_type!r}")
    video = _ffmpeg_video(path, fps)
    samples, sample_rate = _ffmpeg_audio(path)
    audio = [_audio_features(window, sample_rate) for window in _audio_windows(samples, sample_rate, fps)]
    count = max(len(video), len(audio))
    rows: list[list[float]] = []
    previous = None
    for index in range(count):
        audio_row = audio[index] if index < len(audio) else [0.0] * 8
        if index < len(video):
            visual_row = _visual_features(video[index], previous)
            previous = video[index]
        else:
            visual_row = [0.0] * 8
        rows.append(audio_row + visual_row)
    return rows


def _manifest(path: str | Path) -> tuple[dict, Path]:
    target = Path(path).resolve()
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("schema") != MANIFEST_SCHEMA or not isinstance(value.get("recordings"), list):
        raise ValueError(f"{MANIFEST_SCHEMA} with recordings is required")
    if not value["recordings"]:
        raise ValueError("media manifest contains zero recordings")
    return value, target.parent


def _catalog_records(path: str | Path, spans: list[dict], fps: float) -> tuple[list[dict], dict]:
    lookup = {
        (row.get("source_id"), row.get("source_recording_id", row["recording_id"])): row
        for row in spans
    }
    records, examined, matched = [], 0, 0
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            examined += 1
            item = json.loads(line)
            ref = item.get("observation_ref") or {}
            span = lookup.get((item.get("source_id"), ref.get("recording_id")))
            if span is None or "start_seconds" not in ref or "end_seconds" not in ref:
                continue
            local_start = max(0, int(math.floor(float(ref["start_seconds"]) * fps)))
            local_end = max(local_start, int(math.ceil(float(ref["end_seconds"]) * fps)) - 1)
            start = min(span["end_offset"], span["start_offset"] + local_start)
            end = min(span["end_offset"], span["start_offset"] + local_end)
            records.append({
                "external_id": f"{item['source_id']}:{item['external_id']}",
                "expression": item["expression"],
                "source_offset_ranges": [[start, end]],
            })
            matched += 1
    return records, {"catalog_records_examined": examined, "catalog_records_matched": matched}


def import_real_media(
    manifest_path: str | Path, *, fps: float = 40.0, catalog_path: str | Path | None = None,
) -> tuple[dict, list[dict], dict, dict]:
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be positive and finite")
    manifest, base = _manifest(manifest_path)
    frames, records, spans = [], [], []
    source_digest = hashlib.sha256()
    has_audio = has_video = False
    offset = 0
    for index, item in enumerate(manifest["recordings"]):
        recording_id = str(item.get("recording_id", "")).strip()
        relative = item.get("path")
        if not recording_id or not isinstance(relative, str):
            raise ValueError(f"recording {index} requires recording_id and path")
        path = (base / relative).resolve()
        if not path.is_file() or base not in path.parents:
            raise ValueError(f"recording path is missing or escapes manifest directory: {relative}")
        media_type = item.get("media_type") or ("audio" if path.suffix.lower() in AUDIO_SUFFIXES else "video")
        has_audio |= media_type == "audio"
        has_video |= media_type == "video"
        actual_sha = _sha256(path)
        expected_sha = item.get("sha256")
        if expected_sha is not None and expected_sha != actual_sha:
            raise ValueError(f"recording checksum mismatch: {recording_id}")
        payload = path.read_bytes()
        source_digest.update(len(payload).to_bytes(8, "big"))
        source_digest.update(payload)
        features = _recording_features(path, media_type, fps)
        if not features:
            raise ValueError(f"recording decoded to zero frames: {recording_id}")
        start = offset
        for values in features:
            frames.append({
                "t": round(offset / fps, 9),
                "samples": [round(float(value), 9) for value in values],
                "controls": [0.0],
                "source_offset": offset,
            })
            offset += 1
        end = offset - 1
        span = {
            "recording_id": recording_id, "source_id": item.get("source_id"),
            "source_recording_id": item.get("source_recording_id", recording_id),
            "path": relative, "media_type": media_type, "sha256": actual_sha,
            "start_offset": start, "end_offset": end, "frame_count": len(features),
        }
        spans.append(span)
        for annotation in item.get("annotations", []):
            if set(annotation) != {"external_id", "expression"}:
                raise ValueError(f"recording {recording_id} has an invalid annotation")
            records.append({
                "external_id": str(annotation["external_id"]),
                "expression": str(annotation["expression"]),
                "source_offset_ranges": [[start, end]],
            })
    stream = validate_causal_stream({
        "schema": "losica-causal-stream/1", "frames": frames,
        "source_sha256": source_digest.hexdigest(),
    })
    catalog_report = {"catalog_records_examined": 0, "catalog_records_matched": 0}
    if catalog_path is not None:
        imported, catalog_report = _catalog_records(catalog_path, spans, fps)
        records.extend(imported)
    input_kind = "mixed_general_transducers" if has_audio and has_video else (
        "general_optical_array" if has_video else "general_acoustic_array"
    )
    attestation = {
        "schema": "losica-collection-attestation/1",
        "source_sha256": stream["source_sha256"],
        "input_kind": input_kind,
        "selection_basis": "physical_channel_without_named_target",
        "generation_projection": "samples_controls_time_offsets_only",
        "reviewer_record": "automated-media-boundary-audit:" + hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    report = {
        "schema": REPORT_SCHEMA, "manifest_schema": MANIFEST_SCHEMA, "fps": fps,
        "source_sha256": stream["source_sha256"], "recording_count": len(spans),
        "frame_count": len(frames), "alignment_record_count": len(records),
        "feature_layout": [
            "audio_mean", "audio_std", "audio_rms", "audio_peak", "audio_zero_crossing",
            "audio_spectral_centroid", "audio_spectral_spread", "audio_spectral_flatness",
            "visual_mean", "visual_std", "visual_edge_x", "visual_edge_y",
            "visual_motion_mean", "visual_motion_std", "visual_lower_quartile", "visual_center_contrast",
        ],
        "recordings": spans, **catalog_report,
    }
    return stream, records, attestation, report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Import real audio/video without exposing labels to generation")
    parser.add_argument("manifest")
    parser.add_argument("--catalog")
    parser.add_argument("--fps", type=float, default=40.0)
    parser.add_argument("--stream-out", required=True)
    parser.add_argument("--records-out", required=True)
    parser.add_argument("--attestation-out", required=True)
    parser.add_argument("--report-out", required=True)
    args = parser.parse_args(argv)
    stream, records, attestation, report = import_real_media(args.manifest, fps=args.fps, catalog_path=args.catalog)
    outputs = {
        args.stream_out: stream, args.records_out: records,
        args.attestation_out: attestation, args.report_out: report,
    }
    for name, value in outputs.items():
        target = Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "recordings": report["recording_count"],
        "frames": report["frame_count"], "alignment_records": len(records),
        "source_sha256": stream["source_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
