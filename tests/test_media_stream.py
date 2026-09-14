from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from losica_engine.media_stream import import_real_media


def fixture(tmp_path: Path) -> Path:
    sample_rate = 8000
    t = np.arange(sample_rate * 2) / sample_rate
    waveform = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.sin(2 * np.pi * 997 * t)
    sf.write(tmp_path / "recording.wav", waveform.astype(np.float32), sample_rate)
    manifest = {
        "schema": "losica-real-media-manifest/1",
        "recordings": [{
            "recording_id": "recording:1", "source_id": "source:1",
            "source_recording_id": "clip:1", "path": "recording.wav", "media_type": "audio",
            "annotations": [{"external_id": "description:1", "expression": "externally authored wording"}],
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_real_audio_creates_strict_numeric_stream_and_separate_alignment(tmp_path):
    path = fixture(tmp_path)
    stream, records, attestation, report = import_real_media(path, fps=40)
    assert len(stream["frames"]) == 80
    assert len(stream["frames"][0]["samples"]) == 16
    assert records == [{
        "external_id": "description:1", "expression": "externally authored wording",
        "source_offset_ranges": [[0, 79]],
    }]
    assert attestation["source_sha256"] == stream["source_sha256"]
    assert attestation["input_kind"] == "general_acoustic_array"
    assert report["recordings"][0]["start_offset"] == 0
    assert report["recordings"][0]["end_offset"] == 79


def test_annotation_changes_have_zero_causal_effect(tmp_path):
    path = fixture(tmp_path)
    first, first_records, _, _ = import_real_media(path, fps=40)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["recordings"][0]["annotations"][0]["expression"] = "wholly different symbols"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    second, second_records, _, _ = import_real_media(path, fps=40)
    assert first == second
    assert first_records != second_records


def test_external_catalog_ranges_join_by_recording_and_time(tmp_path):
    path = fixture(tmp_path)
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({
        "source_id": "source:1", "external_id": "catalog:1", "expression": "timed description",
        "observation_ref": {"recording_id": "clip:1", "start_seconds": 0.5, "end_seconds": 1.0},
    }) + "\n", encoding="utf-8")
    _, records, _, report = import_real_media(path, fps=40, catalog_path=catalog)
    assert records[-1] == {
        "external_id": "source:1:catalog:1", "expression": "timed description",
        "source_offset_ranges": [[20, 39]],
    }
    assert report["catalog_records_examined"] == 1
    assert report["catalog_records_matched"] == 1
