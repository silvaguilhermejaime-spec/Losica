import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from pycldf import Dataset

from losica_engine.export_v021 import export_bundle
from losica_engine.full_language import generate_complete_language

ROOT = Path(__file__).resolve().parents[1]


def test_complete_state_conforms_to_v021_schema():
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    schema = json.loads((ROOT / "schemas/complete-language.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(state, schema)


def test_companion_exports_include_every_required_resource(tmp_path):
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    result = export_bundle(state, tmp_path / "language.json")
    root = Path(result["resources"])
    assert {"lexicon.tsv", "paradigms.tsv", "grammar.md", "examples.igt.txt", "provenance.json", "checksums.json"} <= {x.name for x in root.iterdir()}


def test_cldf_export_validates_with_pycldf(tmp_path):
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    result = export_bundle(state, tmp_path / "language.json")
    dataset = Dataset.from_metadata(result["cldf_metadata"])
    assert dataset.validate()
    assert {"forms.csv", "languages.csv", "parameters.csv", "examples.csv", "paradigms.csv", "features.csv", "provenance.csv", "history.csv"} <= {str(x.url) for x in dataset.tables}


def test_export_checksum_manifest_matches_every_listed_file(tmp_path):
    state = generate_complete_language(seed=19020, vocabulary_scale="core")
    result = export_bundle(state, tmp_path / "language.json")
    manifest = json.loads((Path(result["resources"]) / "checksums.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() == expected


def test_primary_command_runs_from_a_clean_external_directory(tmp_path):
    out = tmp_path / "generated.json"
    proc = subprocess.run([sys.executable, str(ROOT / "GENERATE_COMPLETE_LANGUAGE.py"), "--seed", "7", "--vocabulary-scale", "core", "--out", str(out)], cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert out.exists() and (tmp_path / "generated_resources/cldf/Wordlist-metadata.json").exists()
