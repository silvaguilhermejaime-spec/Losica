import io
import json

from external_sources.build_catalog import egocom
from external_sources.build_egocom_manifest import build_manifest


def test_egocom_copies_timestamped_speaker_utterances(tmp_path):
    path = tmp_path / "egocom" / "egocom_dataset" / "ground_truth_transcriptions.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "conversation_id,endTime,speaker_id,startTime,word\n"
        "conversation_1,0.40,1,0.10,Okay\n"
        "conversation_1,0.40,1,0.10,.\n"
        "conversation_1,,1,, \n"
        "conversation_1,0.80,1,0.60,I\n"
        "conversation_1,0.80,1,0.60,'\n"
        "conversation_1,0.80,1,0.60,ll\n"
        "conversation_1,,1,, \n"
        "conversation_1,1.10,1,0.90,start\n"
        "conversation_1,1.10,1,0.90,.\n",
        encoding="utf-8",
    )
    output = io.StringIO()
    assert egocom(tmp_path, output) == 2
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [row["expression"] for row in records] == ["Okay.", "I'll start."]
    assert records[1]["observation_ref"] == {
        "recording_id": "conversation_1",
        "speaker_id": "1",
        "start_seconds": 0.6,
        "end_seconds": 1.1,
    }


def test_egocom_manifest_selects_one_stable_view_per_segment(tmp_path):
    video_info = tmp_path / "video_info.csv"
    video_info.write_text(
        "video_id,conversation_id,video_speaker_id,video_name\n"
        "2,conversation_1,2,view_two\n"
        "1,conversation_1,1,view_one\n"
        "3,conversation_2,1,view_three\n",
        encoding="utf-8",
    )
    media = tmp_path / "media"
    media.mkdir()
    for name in ("view_one.MP4", "view_two.mp4", "view_three.mp4"):
        (media / name).write_bytes(b"fixture")
    output = tmp_path / "manifests" / "egocom.json"
    output.parent.mkdir()
    manifest = build_manifest(video_info, media, output)
    assert [row["recording_id"] for row in manifest["recordings"]] == ["view_one", "view_three"]
    assert [row["source_recording_id"] for row in manifest["recordings"]] == ["conversation_1", "conversation_2"]
